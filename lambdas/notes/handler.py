"""
Notes Lambda - v2.0
Handles:
  GET    /applications/{appId}/notes          - list all notes for an application
  POST   /applications/{appId}/notes          - add a new note
  DELETE /applications/{appId}/notes/{noteId} - delete a specific note

DynamoDB entity:
  PK          = APP#appId
  SK          = NOTE#timestamp#noteId
  userId      = owner (used for auth check)
  content     = note text
  createdAt   = ISO timestamp
  entityType  = NOTE

Auth: every operation verifies the application belongs to the calling user
by checking the APPLICATION record exists under USER#userId before acting.
"""
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, field_validator
from typing import Optional

from shared.middleware import resp, get_user_id, parse_body, now_iso

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ["TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))

MAX_NOTE_LENGTH = 2000


class CreateNoteRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be empty")
        if len(v) > MAX_NOTE_LENGTH:
            raise ValueError(f"content must be {MAX_NOTE_LENGTH} characters or less")
        return v


@tracer.capture_method
def verify_application_owner(user_id: str, app_id: str) -> bool:
    """Check APPLICATION record exists under USER#userId to confirm ownership."""
    result = table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
        ProjectionExpression="appId",
    )
    return "Item" in result


@tracer.capture_method
def list_notes(app_id: str) -> list[dict]:
    """List all notes for an application, sorted oldest first."""
    result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"APP#{app_id}") &
            Key("SK").begins_with("NOTE#")
        ),
        FilterExpression=Attr("entityType").eq("NOTE"),
        ScanIndexForward=True,  # oldest first
    )
    return result.get("Items", [])


@tracer.capture_method
def create_note(app_id: str, user_id: str, content: str) -> dict:
    """Write a new NOTE record under APP#appId."""
    note_id = str(uuid.uuid4())
    ts = now_iso()

    item = {
        "PK": f"APP#{app_id}",
        "SK": f"NOTE#{ts}#{note_id}",
        "noteId": note_id,
        "appId": app_id,
        "userId": user_id,
        "content": content,
        "createdAt": ts,
        "entityType": "NOTE",
    }
    table.put_item(Item=item)
    return item


@tracer.capture_method
def delete_note(app_id: str, note_id: str, user_id: str) -> bool:
    """
    Delete a specific note by noteId.
    Scans NOTE# items for the app to find the correct SK (which includes timestamp).
    Returns True if deleted, False if not found.
    """
    # Query to find the note SK - noteId alone isn't enough since SK includes timestamp
    result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"APP#{app_id}") &
            Key("SK").begins_with("NOTE#")
        ),
        FilterExpression=Attr("noteId").eq(note_id) & Attr("entityType").eq("NOTE"),
    )
    items = result.get("Items", [])
    if not items:
        return False

    note = items[0]
    # Verify ownership - only the user who created the note can delete it
    if note.get("userId") != user_id:
        return False

    table.delete_item(Key={"PK": f"APP#{app_id}", "SK": note["SK"]})
    return True


def _clean_note(item: dict) -> dict:
    """Return only fields the frontend needs."""
    return {
        "noteId": item.get("noteId"),
        "appId": item.get("appId"),
        "content": item.get("content"),
        "createdAt": item.get("createdAt"),
    }


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
    note_id = path_params.get("noteId")

    if not app_id:
        return resp(400, {"error": "appId is required"}, event)

    try:

        # GET /applications/{appId}/notes
        if method == "GET" and path.endswith("/notes"):
            if not verify_application_owner(user_id, app_id):
                return resp(404, {"error": "Application not found"}, event)
            notes = list_notes(app_id)
            cleaned = [_clean_note(n) for n in notes]
            return resp(200, {"notes": cleaned, "count": len(cleaned)}, event)

        # POST /applications/{appId}/notes
        if method == "POST" and path.endswith("/notes"):
            try:
                req = CreateNoteRequest(**body)
            except Exception as e:
                return resp(400, {"error": f"Validation error: {e}"}, event)

            if not verify_application_owner(user_id, app_id):
                return resp(404, {"error": "Application not found"}, event)

            note = create_note(app_id, user_id, req.content)
            logger.info("Note created", extra={"app_id": app_id, "note_id": note["noteId"]})
            return resp(201, {"note": _clean_note(note)}, event)

        # DELETE /applications/{appId}/notes/{noteId}
        if method == "DELETE" and note_id:
            if not verify_application_owner(user_id, app_id):
                return resp(404, {"error": "Application not found"}, event)

            deleted = delete_note(app_id, note_id, user_id)
            if not deleted:
                return resp(404, {"error": "Note not found"}, event)

            logger.info("Note deleted", extra={"app_id": app_id, "note_id": note_id})
            return resp(200, {"message": "Deleted", "noteId": note_id}, event)

        return resp(404, {"error": "Route not found"}, event)

    except Exception:
        logger.exception("Unhandled error in notes handler")
        return resp(500, {"error": "Internal server error"}, event)
