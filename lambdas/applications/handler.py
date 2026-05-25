"""
Applications Lambda - v2.0
Handles: GET/POST /applications, GET/PUT/DELETE /applications/{appId},
         POST /applications/{appId}/status, POST /resumes/upload-url, GET /resumes/list

v2.0 change: followUpDate field added to CreateApplicationRequest and UpdateApplicationRequest.
"""
import os
import uuid

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, field_validator
from typing import Optional, Literal

from shared.middleware import resp, get_user_id, parse_body, now_iso

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

TABLE_NAME = os.environ["TABLE_NAME"]
RESUME_BUCKET = os.environ["RESUME_BUCKET"]
table = dynamodb.Table(TABLE_NAME)

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))
tracer = Tracer(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))


class CreateApplicationRequest(BaseModel):
    company: str
    role: str
    status: Literal["applied", "screened", "interview", "offer", "rejected", "withdrawn"]
    dateApplied: Optional[str] = None
    resumeVersion: Optional[str] = "default"
    source: Optional[Literal["linkedin", "referral", "cold", "job-board", "unknown"]] = "unknown"
    jobDescUrl: Optional[str] = ""
    companySize: Optional[Literal["startup", "mid", "enterprise", ""]] = ""
    notes: Optional[str] = ""
    followUpDate: Optional[str] = None  # v2.0: YYYY-MM-DD, nullable

    @field_validator("company", "role")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("followUpDate")
    @classmethod
    def valid_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            from datetime import datetime
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("followUpDate must be YYYY-MM-DD format")
        return v


class UpdateApplicationRequest(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    jobDescUrl: Optional[str] = None
    resumeVersion: Optional[str] = None
    source: Optional[str] = None
    companySize: Optional[str] = None
    notes: Optional[str] = None
    dateApplied: Optional[str] = None
    followUpDate: Optional[str] = None  # v2.0: can update or clear (pass null to clear)

    @field_validator("followUpDate")
    @classmethod
    def valid_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            from datetime import datetime
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("followUpDate must be YYYY-MM-DD format")
        return v


class UpdateStatusRequest(BaseModel):
    status: Literal["applied", "screened", "interview", "offer", "rejected", "withdrawn"]
    notes: Optional[str] = ""


class UploadUrlRequest(BaseModel):
    filename: str
    versionName: Optional[str] = "v1"
    contentType: Optional[str] = "application/pdf"

    @field_validator("filename")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


@tracer.capture_method
def list_applications(user_id: str):
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
        ScanIndexForward=False,
    )
    return result["Items"], result["Count"]


@tracer.capture_method
def create_application(user_id: str, body: dict, event: dict) -> dict:
    try:
        req = CreateApplicationRequest(**body)
    except Exception as e:
        return resp(400, {"error": f"Validation error: {e}"}, event)

    app_id = str(uuid.uuid4())
    ts = now_iso()

    item = {
        "PK": f"USER#{user_id}", "SK": f"APP#{app_id}",
        "GSI1PK": f"USER#{user_id}", "GSI1SK": f"DATE#{ts}",
        "appId": app_id, "userId": user_id,
        "company": req.company, "role": req.role, "status": req.status,
        "dateApplied": req.dateApplied or ts[:10],
        "resumeVersion": req.resumeVersion, "source": req.source,
        "jobDescUrl": req.jobDescUrl, "companySize": req.companySize,
        "notes": req.notes,
        "followUpDate": req.followUpDate,  # v2.0
        "createdAt": ts, "updatedAt": ts,
        "entityType": "APPLICATION",
    }

    table.put_item(Item=item)
    _write_status_event(app_id, user_id, None, req.status, ts)
    logger.info("Created application", extra={"app_id": app_id})
    return resp(201, {"application": item}, event)


@tracer.capture_method
def get_application(user_id: str, app_id: str, event: dict) -> dict:
    result = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"})
    item = result.get("Item")
    if not item:
        return resp(404, {"error": "Application not found"}, event)
    return resp(200, {"application": item}, event)


@tracer.capture_method
def update_application(user_id: str, app_id: str, body: dict, event: dict) -> dict:
    try:
        req = UpdateApplicationRequest(**body)
    except Exception as e:
        return resp(400, {"error": f"Validation error: {e}"}, event)

    allowed = [
        "company", "role", "jobDescUrl", "resumeVersion", "source",
        "companySize", "notes", "dateApplied", "followUpDate",  # v2.0
    ]
    updates = {k: v for k, v in req.model_dump(exclude_none=True).items() if k in allowed}

    # v2.0: support explicitly clearing followUpDate by passing null in body
    # model_dump(exclude_none=True) skips None, so we check raw body separately
    if "followUpDate" in body and body["followUpDate"] is None:
        updates["followUpDate"] = None

    if not updates:
        return resp(400, {"error": "No valid fields to update"}, event)

    updates["updatedAt"] = now_iso()
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates)
    names = {f"#{k}": k for k in updates}
    values = {f":{k}": v for k, v in updates.items()}

    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ConditionExpression="attribute_exists(PK)",
    )
    return resp(200, {"message": "Updated", "appId": app_id}, event)


@tracer.capture_method
def delete_application(user_id: str, app_id: str, event: dict) -> dict:
    table.delete_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
        ConditionExpression="attribute_exists(PK)",
    )
    logger.info("Deleted application", extra={"app_id": app_id})
    return resp(200, {"message": "Deleted", "appId": app_id}, event)


@tracer.capture_method
def update_status(user_id: str, app_id: str, body: dict, event: dict) -> dict:
    try:
        req = UpdateStatusRequest(**body)
    except Exception as e:
        return resp(400, {"error": f"Validation error: {e}"}, event)

    result = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"})
    item = result.get("Item")
    if not item:
        return resp(404, {"error": "Application not found"}, event)

    old_status = item.get("status")
    ts = now_iso()

    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
        UpdateExpression="SET #status = :status, updatedAt = :ts",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": req.status, ":ts": ts},
    )
    _write_status_event(app_id, user_id, old_status, req.status, ts, req.notes or "")
    return resp(200, {"message": "Status updated", "from": old_status, "to": req.status}, event)


def _write_status_event(app_id, user_id, from_status, to_status, ts, notes=""):
    event_id = str(uuid.uuid4())
    table.put_item(Item={
        "PK": f"APP#{app_id}", "SK": f"EVENT#{ts}#{event_id}",
        "userId": user_id, "fromStatus": from_status, "toStatus": to_status,
        "notes": notes, "createdAt": ts, "entityType": "STATUS_EVENT",
    })


@tracer.capture_method
def get_upload_url(user_id: str, body: dict, event: dict) -> dict:
    try:
        req = UploadUrlRequest(**body)
    except Exception as e:
        return resp(400, {"error": f"Validation error: {e}"}, event)

    s3_key = f"resumes/{user_id}/{req.versionName}/{req.filename}"
    url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": RESUME_BUCKET, "Key": s3_key, "ContentType": req.contentType},
        ExpiresIn=300,
    )
    return resp(200, {"uploadUrl": url, "s3Key": s3_key, "versionName": req.versionName}, event)


@tracer.capture_method
def list_resumes(user_id: str, event: dict) -> dict:
    prefix = f"resumes/{user_id}/"
    result = s3_client.list_objects_v2(Bucket=RESUME_BUCKET, Prefix=prefix)
    resumes = []
    for obj in result.get("Contents", []):
        key = obj["Key"]
        parts = key.replace(prefix, "").split("/")
        if len(parts) >= 2:
            resumes.append({
                "versionName": parts[0], "filename": parts[1],
                "uploadedAt": obj["LastModified"].strftime("%Y-%m-%d"), "s3Key": key,
            })
    resumes.sort(key=lambda x: x["uploadedAt"], reverse=True)
    return resp(200, {"resumes": resumes}, event)


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

    try:
        if method == "POST" and path.endswith("/upload-url"):
            return get_upload_url(user_id, body, event)
        if method == "GET" and path.endswith("/resumes/list"):
            return list_resumes(user_id, event)
        if method == "POST" and app_id and path.endswith("/status"):
            return update_status(user_id, app_id, body, event)
        if path.endswith("/applications"):
            if method == "GET":
                items, count = list_applications(user_id)
                return resp(200, {"applications": items, "count": count}, event)
            if method == "POST":
                return create_application(user_id, body, event)
        if app_id:
            if method == "GET":
                return get_application(user_id, app_id, event)
            if method == "PUT":
                return update_application(user_id, app_id, body, event)
            if method == "DELETE":
                return delete_application(user_id, app_id, event)
        return resp(404, {"error": "Route not found"}, event)

    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return resp(404, {"error": "Item not found"}, event)
        logger.exception("DynamoDB error")
        return resp(500, {"error": "Database error"}, event)
    except Exception:
        logger.exception("Unhandled error")
        return resp(500, {"error": "Internal server error"}, event)
