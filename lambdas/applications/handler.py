"""
Applications Lambda
Handles: GET/POST /applications, GET/PUT/DELETE /applications/{appId},
         POST /applications/{appId}/status, POST /resumes/upload-url
"""
import json
import os
import uuid
import boto3
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

TABLE_NAME = os.environ["TABLE_NAME"]
RESUME_BUCKET = os.environ["RESUME_BUCKET"]
table = dynamodb.Table(TABLE_NAME)


# ── Helpers ────────────────────────────────────────────────────────────────────

def resp(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }

def get_user_id(event: dict) -> str:
    return event["requestContext"]["authorizer"]["claims"]["sub"]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Application CRUD ───────────────────────────────────────────────────────────

def list_applications(user_id: str) -> dict:
    result = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"USER#{user_id}"),
        ScanIndexForward=False,  # newest first
    )
    return resp(200, {"applications": result["Items"], "count": result["Count"]})


def create_application(user_id: str, body: dict) -> dict:
    app_id = str(uuid.uuid4())
    ts = now_iso()

    required = ["company", "role", "status"]
    if missing := [f for f in required if f not in body]:
        return resp(400, {"error": f"Missing required fields: {missing}"})

    item = {
        "PK": f"USER#{user_id}",
        "SK": f"APP#{app_id}",
        "GSI1PK": f"USER#{user_id}",
        "GSI1SK": f"DATE#{ts}",
        "appId": app_id,
        "userId": user_id,
        "company": body["company"],
        "role": body["role"],
        "status": body["status"],  # applied|screened|interview|offer|rejected
        "dateApplied": body.get("dateApplied", ts[:10]),
        "resumeVersion": body.get("resumeVersion", "default"),
        "source": body.get("source", "unknown"),  # linkedin|referral|cold|job-board
        "jobDescUrl": body.get("jobDescUrl", ""),
        "companySize": body.get("companySize", ""),  # startup|mid|enterprise
        "notes": body.get("notes", ""),
        "createdAt": ts,
        "updatedAt": ts,
        "entityType": "APPLICATION",
    }

    table.put_item(Item=item)

    # also write the initial status event
    _write_status_event(app_id, user_id, None, body["status"], ts)

    return resp(201, {"application": item})


def get_application(user_id: str, app_id: str) -> dict:
    result = table.get_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"}
    )
    item = result.get("Item")
    if not item:
        return resp(404, {"error": "Application not found"})
    return resp(200, {"application": item})


def update_application(user_id: str, app_id: str, body: dict) -> dict:
    allowed = ["company", "role", "jobDescUrl", "resumeVersion", "source",
               "companySize", "notes", "dateApplied"]
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        return resp(400, {"error": "No valid fields to update"})

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
    return resp(200, {"message": "Updated", "appId": app_id})


def delete_application(user_id: str, app_id: str) -> dict:
    table.delete_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
        ConditionExpression="attribute_exists(PK)",
    )
    return resp(200, {"message": "Deleted", "appId": app_id})


def update_status(user_id: str, app_id: str, body: dict) -> dict:
    new_status = body.get("status")
    valid = {"applied", "screened", "interview", "offer", "rejected", "withdrawn"}
    if new_status not in valid:
        return resp(400, {"error": f"status must be one of {valid}"})

    # get current status before updating
    result = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"})
    item = result.get("Item")
    if not item:
        return resp(404, {"error": "Application not found"})

    old_status = item.get("status")
    ts = now_iso()

    table.update_item(
        Key={"PK": f"USER#{user_id}", "SK": f"APP#{app_id}"},
        UpdateExpression="SET #status = :status, updatedAt = :ts",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": new_status, ":ts": ts},
    )

    _write_status_event(app_id, user_id, old_status, new_status, ts, body.get("notes", ""))

    return resp(200, {"message": "Status updated", "from": old_status, "to": new_status})


def _write_status_event(app_id, user_id, from_status, to_status, ts, notes=""):
    event_id = str(uuid.uuid4())
    table.put_item(Item={
        "PK": f"APP#{app_id}",
        "SK": f"EVENT#{ts}#{event_id}",
        "userId": user_id,
        "fromStatus": from_status,
        "toStatus": to_status,
        "notes": notes,
        "createdAt": ts,
        "entityType": "STATUS_EVENT",
    })


# ── Resume presigned URL ───────────────────────────────────────────────────────

def get_upload_url(user_id: str, body: dict) -> dict:
    filename = body.get("filename")
    version_name = body.get("versionName", "v1")
    content_type = body.get("contentType", "application/pdf")

    if not filename:
        return resp(400, {"error": "filename is required"})

    s3_key = f"resumes/{user_id}/{version_name}/{filename}"

    url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": RESUME_BUCKET,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=300,  # 5 minutes
    )

    return resp(200, {"uploadUrl": url, "s3Key": s3_key, "versionName": version_name})


def list_resumes(user_id: str) -> dict:
    """List all resume versions uploaded by this user from S3."""
    prefix = f"resumes/{user_id}/"
    result = s3_client.list_objects_v2(Bucket=RESUME_BUCKET, Prefix=prefix)
    resumes = []
    for obj in result.get("Contents", []):
        key = obj["Key"]
        parts = key.replace(prefix, "").split("/")
        if len(parts) >= 2:
            version_name = parts[0]
            filename = parts[1]
            resumes.append({
                "versionName": version_name,
                "filename": filename,
                "uploadedAt": obj["LastModified"].strftime("%Y-%m-%d"),
                "s3Key": key,
            })
    resumes.sort(key=lambda x: x["uploadedAt"], reverse=True)
    return resp(200, {"resumes": resumes})


# ── Router ─────────────────────────────────────────────────────────────────────

def lambda_handler(event: dict, context) -> dict:
    method = event.get("httpMethod", "")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}
    body = {}

    if event.get("body"):
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError:
            return resp(400, {"error": "Invalid JSON body"})

    try:
        user_id = get_user_id(event)
    except (KeyError, TypeError):
        return resp(401, {"error": "Unauthorized"})

    app_id = path_params.get("appId")

    try:
        # /resumes/upload-url
        if method == "POST" and path.endswith("/upload-url"):
            return get_upload_url(user_id, body)

        # /resumes/list
        if method == "GET" and path.endswith("/resumes/list"):
            return list_resumes(user_id)

        # /applications/{appId}/status
        if method == "POST" and app_id and path.endswith("/status"):
            return update_status(user_id, app_id, body)

        # /applications
        if path.endswith("/applications"):
            if method == "GET":
                return list_applications(user_id)
            if method == "POST":
                return create_application(user_id, body)

        # /applications/{appId}
        if app_id:
            if method == "GET":
                return get_application(user_id, app_id)
            if method == "PUT":
                return update_application(user_id, app_id, body)
            if method == "DELETE":
                return delete_application(user_id, app_id)

        return resp(404, {"error": "Route not found"})

    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            return resp(404, {"error": "Item not found"})
        print(f"DynamoDB error: {e}")
        return resp(500, {"error": "Database error"})

    except Exception as e:
        print(f"Unhandled error: {e}")
        return resp(500, {"error": "Internal server error"})
