"""
Interview Prep Lambda - v3.0
Handles:
  POST /applications/{appId}/interview-prep/generate
      Fetches job description URL (if present), passes role + company + JD text
      to Bedrock Nova Lite, generates 10 interview questions, stores result.
  GET  /applications/{appId}/interview-prep
      Returns stored questions for an application.
  PUT  /applications/{appId}/interview-prep/{questionId}
      Updates a single question - mark as practiced, save user answer.

DynamoDB entity:
  PK  = APP#{appId}
  SK  = PREP#v1          (single record per app, overwritten on regenerate)
  questions = [           (list of question objects)
    { id, text, practiced, answer }
  ]
  generatedAt = ISO timestamp
  entityType  = INTERVIEW_PREP

Auth: every operation verifies the application belongs to the calling user
by checking the APPLICATION record exists under USER#{userId} before acting.

Job description fetching:
  - urllib.request fetches the URL with a 5s timeout
  - Basic HTML tag stripping, first 3000 chars passed to Bedrock
  - If fetch fails for any reason, falls back to role + company name only
  - Never blocks the user on URL fetch failure
"""
import json
import os
import re
import uuid
from html.parser import HTMLParser
from urllib import request as urllib_request
from urllib.error import URLError

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, field_validator
from typing import Optional

from shared.middleware import resp, get_user_id, parse_body, now_iso

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")

TABLE_NAME = os.environ["TABLE_NAME"]
MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))

JD_MAX_CHARS = 3000
FETCH_TIMEOUT = 5  # seconds
NUM_QUESTIONS = 10


class UpdateQuestionRequest(BaseModel):
    practiced: Optional[bool] = None
    answer: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def answer_not_too_long(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 5000:
            raise ValueError("answer must be 5000 characters or less")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

@tracer.capture_method
def verify_application_owner(user_id: str, app_id: str) -> Optional[dict]:
    """
    Returns the application item if it exists and belongs to user_id,
    None otherwise. Caller gets role, company, jobDescUrl for free.
    """
    result = table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
    )
    return result.get("Item")

class _TextExtractor(HTMLParser):
    """
    Extracts visible text from HTML, dropping script/style content entirely.
    Uses stdlib's tokenizing parser instead of regex - CodeQL flagged the old
    regex approach (py/bad-tag-filter) because <(script|style)[^>]*>.*?</...>
    does not match malformed-but-browser-accepted close tags such as
    </script foo="bar">.
    """
    _SKIP_TAGS = {"script", "style"}

    def __init__(self):
        super().__init__()
        # HTMLParser's default CDATA mode for script/style only recognizes a
        # literal "</script>" (no attributes) as the end tag - a malformed
        # close tag like </script foo="bar"> would never match, causing the
        # parser to silently swallow everything after it as "script content".
        # Disabling CDATA mode and tracking skip state via normal start/end
        # tag events lets the parser's tolerant end-tag matching (which does
        # accept trailing attributes, whitespace, and mixed case) do the work.
        self.CDATA_CONTENT_ELEMENTS = ()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(raw: str) -> str:
    """Strip HTML tags and script/style content, collapse whitespace."""
    if not raw:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        logger.warning("HTML parsing failed - returning partial text")
    collapsed = re.sub(r"\s+", " ", parser.get_text())
    return collapsed.strip()


@tracer.capture_method
def fetch_job_description(url: str) -> str:
    """
    Fetches job description text from a URL.
    Returns up to JD_MAX_CHARS of stripped text.
    Returns empty string on any failure - caller falls back gracefully.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        req = urllib_request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Applytic/3.0)"},
        )
        with urllib_request.urlopen(req, timeout=FETCH_TIMEOUT) as response:
            raw = response.read(50_000).decode("utf-8", errors="ignore")
        return _strip_html(raw)[:JD_MAX_CHARS]
    except Exception as e:
        logger.warning("JD fetch failed - using fallback", extra={"url": url, "error": str(e)})
        return ""


@tracer.capture_method
def generate_questions_with_bedrock(role: str, company: str, jd_text: str) -> list[dict]:
    """
    Calls Bedrock Nova Lite to generate NUM_QUESTIONS interview questions.
    Returns a list of question dicts: {id, text, practiced, answer}.
    Falls back to a generic set if Bedrock fails.
    """
    jd_section = (
        f"\n\nJob description excerpt:\n{jd_text}"
        if jd_text
        else f"\n\n(No job description available - generate questions based on the role title and company.)"
    )

    prompt = (
        f"You are an expert interview coach. Generate exactly {NUM_QUESTIONS} interview questions "
        f"for a candidate interviewing for the role of {role} at {company}.{jd_section}\n\n"
        f"Rules:\n"
        f"- Mix of behavioural (3-4), technical (3-4), and role-specific (2-3) questions\n"
        f"- Each question on its own line, numbered 1-{NUM_QUESTIONS}\n"
        f"- No preamble, no explanations, just the numbered questions\n"
        f"- Questions should be specific to the role and company where possible\n\n"
        f"Questions:"
    )

    if "anthropic" in MODEL_ID:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        body = {
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 1024},
        }

    try:
        response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
        result = json.loads(response["body"].read())
        if "anthropic" in MODEL_ID:
            raw_text = result["content"][0]["text"]
        else:
            raw_text = result["output"]["message"]["content"][0]["text"]

        # Parse numbered lines into question objects
        lines = [
            re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            for line in raw_text.strip().splitlines()
            if re.match(r"^\d+[\.\)]", line.strip())
        ]

        # If parsing got fewer than expected, include whatever we got
        questions = [
            {
                "id": str(uuid.uuid4()),
                "text": line,
                "practiced": False,
                "answer": "",
            }
            for line in lines
            if line
        ]

        logger.info("Generated interview questions", extra={
            "count": len(questions),
            "role": role,
            "company": company,
        })
        return questions

    except Exception as e:
        logger.error("Bedrock call failed for interview prep", extra={"error": str(e)})
        # Fallback: generic questions so the user always gets something
        fallback_texts = [
            f"Tell me about your experience relevant to the {role} role.",
            "Describe a challenging project you worked on and how you handled it.",
            "How do you prioritise when you have multiple deadlines?",
            f"Why are you interested in joining {company}?",
            "Describe a time you disagreed with a team member. How did you resolve it?",
            "Walk me through your approach to debugging a difficult problem.",
            "How do you stay up to date with developments in your field?",
            "Describe a time you had to learn something quickly under pressure.",
            f"What do you know about {company}'s products or services?",
            "Where do you see yourself in 3-5 years?",
        ]
        return [
            {"id": str(uuid.uuid4()), "text": t, "practiced": False, "answer": ""}
            for t in fallback_texts
        ]


# ── DynamoDB operations ───────────────────────────────────────────────────────

@tracer.capture_method
def store_prep(app_id: str, user_id: str, questions: list[dict]) -> dict:
    """Writes (or overwrites) the PREP#v1 record for an application."""
    ts = now_iso()
    item = {
        "PK": f"APP#{app_id}",
        "SK": "PREP#v1",
        "appId": app_id,
        "userId": user_id,
        "questions": questions,
        "generatedAt": ts,
        "updatedAt": ts,
        "entityType": "INTERVIEW_PREP",
    }
    table.put_item(Item=item)
    return item


@tracer.capture_method
def get_prep(app_id: str) -> Optional[dict]:
    """Returns the PREP#v1 record or None if not yet generated."""
    result = table.get_item(
        Key={"PK": f"APP#{app_id}", "SK": "PREP#v1"},
    )
    return result.get("Item")


@tracer.capture_method
def update_question_in_prep(app_id: str, question_id: str, practiced: Optional[bool], answer: Optional[str]) -> bool:
    """
    Updates a single question within the PREP#v1 questions list.
    DynamoDB doesn't support list-element updates by value, so we:
      1. Fetch the full item
      2. Find the question by id
      3. Apply updates
      4. Put the whole item back
    Returns True if question found and updated, False if not found.
    """
    item = get_prep(app_id)
    if not item:
        return False

    questions = item.get("questions", [])
    found = False
    for q in questions:
        if q.get("id") == question_id:
            if practiced is not None:
                q["practiced"] = practiced
            if answer is not None:
                q["answer"] = answer
            found = True
            break

    if not found:
        return False

    item["questions"] = questions
    item["updatedAt"] = now_iso()
    table.put_item(Item=item)
    return True


def _clean_prep(item: dict) -> dict:
    """Strip DynamoDB-internal fields before returning to client."""
    return {
        "appId": item.get("appId"),
        "questions": item.get("questions", []),
        "generatedAt": item.get("generatedAt"),
        "updatedAt": item.get("updatedAt"),
    }


# ── Lambda handler ────────────────────────────────────────────────────────────

@logger.inject_lambda_context(correlation_id_path="requestContext.requestId")
@tracer.capture_lambda_handler
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}

    body, parse_error = parse_body(event)
    if parse_error:
        return parse_error

    try:
        user_id = get_user_id(event)
    except (KeyError, TypeError):
        return resp(401, {"error": "Unauthorized"}, event)

    app_id = path_params.get("appId")
    question_id = path_params.get("questionId")

    if not app_id:
        return resp(400, {"error": "appId is required"}, event)

    try:
        # ── POST /applications/{appId}/interview-prep/generate ─────────────────
        if method == "POST" and path.endswith("/generate"):
            app = verify_application_owner(user_id, app_id)
            if not app:
                return resp(404, {"error": "Application not found"}, event)

            role = app.get("role", "Software Engineer")
            company = app.get("company", "the company")
            job_desc_url = app.get("jobDescUrl", "")

            jd_text = fetch_job_description(job_desc_url)
            questions = generate_questions_with_bedrock(role, company, jd_text)
            prep = store_prep(app_id, user_id, questions)

            logger.info("Interview prep generated", extra={
                "app_id": app_id,
                "question_count": len(questions),
                "used_jd": bool(jd_text),
            })
            return resp(201, {"prep": _clean_prep(prep)}, event)

        # ── GET /applications/{appId}/interview-prep ───────────────────────────
        if method == "GET" and path.endswith("/interview-prep"):
            app = verify_application_owner(user_id, app_id)
            if not app:
                return resp(404, {"error": "Application not found"}, event)

            prep = get_prep(app_id)
            if not prep:
                return resp(200, {"prep": None}, event)

            return resp(200, {"prep": _clean_prep(prep)}, event)

        # ── PUT /applications/{appId}/interview-prep/{questionId} ──────────────
        if method == "PUT" and question_id and "/interview-prep/" in path:
            try:
                req = UpdateQuestionRequest(**body)
            except Exception as e:
                return resp(400, {"error": f"Validation error: {e}"}, event)

            if req.practiced is None and req.answer is None:
                return resp(400, {"error": "At least one of practiced or answer must be provided"}, event)

            app = verify_application_owner(user_id, app_id)
            if not app:
                return resp(404, {"error": "Application not found"}, event)

            updated = update_question_in_prep(app_id, question_id, req.practiced, req.answer)
            if not updated:
                return resp(404, {"error": "Question not found"}, event)

            logger.info("Interview question updated", extra={
                "app_id": app_id,
                "question_id": question_id,
            })
            return resp(200, {"message": "Updated", "questionId": question_id}, event)

        return resp(404, {"error": "Route not found"}, event)

    except Exception:
        logger.exception("Unhandled error in interview prep handler")
        return resp(500, {"error": "Internal server error"}, event)
