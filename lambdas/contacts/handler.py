"""
Contacts Lambda - v3.1
Handles:
  GET    /applications/{appId}/contacts             - list all contacts for an application
  POST   /applications/{appId}/contacts             - add a new contact
  DELETE /applications/{appId}/contacts/{contactId}  - delete a specific contact

DynamoDB entity:
  PK          = APP#appId
  SK          = CONTACT#timestamp#contactId
  userId      = owner (used for auth check)
  name        = contact name
  email       = contact email (optional)
  linkedinUrl = LinkedIn profile URL (optional)
  role        = recruiter/hiring manager/referral etc (optional, free text)
  createdAt   = ISO timestamp
  entityType  = CONTACT

Auth: every operation verifies the application belongs to the calling user
by checking the APPLICATION record exists under USER#userId before acting.
Mirrors notes/handler.py exactly - same ownership check, same SK timestamp
prefix pattern, same clean-and-return shape.
"""
import os
import uuid

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

MAX_NAME_LENGTH = 200
MAX_EMAIL_LENGTH = 320  # RFC 5321 max
MAX_ROLE_LENGTH = 100


class CreateContactRequest(BaseModel):
    name: str
    email: Optional[str] = ""
    linkedinUrl: Optional[str] = ""
    role: Optional[str] = ""

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > MAX_NAME_LENGTH:
            raise ValueError(f"name must be {MAX_NAME_LENGTH} characters or less")
        return v

    @field_validator("email")
    @classmethod
    def email_length(cls, v: Optional[str]) -> str:
        v = (v or "").strip()
        if len(v) > MAX_EMAIL_LENGTH:
            raise ValueError(f"email must be {MAX_EMAIL_LENGTH} characters or less")
        return v

    @field_validator("role")
    @classmethod
    def role_length(cls, v: Optional[str]) -> str:
        v = (v or "").strip()
        if len(v) > MAX_ROLE_LENGTH:
            raise ValueError(f"role must be {MAX_ROLE_LENGTH} characters or less")
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
def list_contacts(app_id: str) -> list[dict]:
    """List all contacts for an application, sorted oldest first."""
    result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"APP#{app_id}") &
            Key("SK").begins_with("CONTACT#")
        ),
        FilterExpression=Attr("entityType").eq("CONTACT"),
        ScanIndexForward=True,  # oldest first
    )
    return result.get("Items", [])


@tracer.capture_method
def create_contact(app_id: str, user_id: str, name: str, email: str, linkedin_url: str, role: str) -> dict:
    """Write a new CONTACT record under APP#appId."""
    contact_id = str(uuid.uuid4())
    ts = now_iso()

    item = {
        "PK": f"APP#{app_id}",
        "SK": f"CONTACT#{ts}#{contact_id}",
        "contactId": contact_id,
        "appId": app_id,
        "userId": user_id,
        "name": name,
        "email": email,
        "linkedinUrl": linkedin_url,
        "role": role,
        "createdAt": ts,
        "entityType": "CONTACT",
    }
    table.put_item(Item=item)
    return item


@tracer.capture_method
def delete_contact(app_id: str, contact_id: str, user_id: str) -> bool:
    """
    Delete a specific contact by contactId.
    Scans CONTACT# items for the app to find the correct SK (which includes timestamp).
    Returns True if deleted, False if not found.
    """
    result = table.query(
        KeyConditionExpression=(
            Key("PK").eq(f"APP#{app_id}") &
            Key("SK").begins_with("CONTACT#")
        ),
        FilterExpression=Attr("contactId").eq(contact_id) & Attr("entityType").eq("CONTACT"),
    )
    items = result.get("Items", [])
    if not items:
        return False

    contact = items[0]
    # Verify ownership - only the user who created the contact can delete it
    if contact.get("userId") != user_id:
        return False

    table.delete_item(Key={"PK": f"APP#{app_id}", "SK": contact["SK"]})
    return True


def _clean_contact(item: dict) -> dict:
    """Return only fields the frontend needs."""
    return {
        "contactId": item.get("contactId"),
        "appId": item.get("appId"),
        "name": item.get("name"),
        "email": item.get("email"),
        "linkedinUrl": item.get("linkedinUrl"),
        "role": item.get("role"),
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
    contact_id = path_params.get("contactId")

    if not app_id:
        return resp(400, {"error": "appId is required"}, event)

    try:

        # GET /applications/{appId}/contacts
        if method == "GET" and path.endswith("/contacts"):
            if not verify_application_owner(user_id, app_id):
                return resp(404, {"error": "Application not found"}, event)
            contacts = list_contacts(app_id)
            cleaned = [_clean_contact(c) for c in contacts]
            return resp(200, {"contacts": cleaned, "count": len(cleaned)}, event)

        # POST /applications/{appId}/contacts
        if method == "POST" and path.endswith("/contacts"):
            try:
                req = CreateContactRequest(**body)
            except Exception as e:
                return resp(400, {"error": f"Validation error: {e}"}, event)

            if not verify_application_owner(user_id, app_id):
                return resp(404, {"error": "Application not found"}, event)

            contact = create_contact(app_id, user_id, req.name, req.email, req.linkedinUrl, req.role)
            logger.info("Contact created", extra={"app_id": app_id, "contact_id": contact["contactId"]})
            return resp(201, {"contact": _clean_contact(contact)}, event)

        # DELETE /applications/{appId}/contacts/{contactId}
        if method == "DELETE" and contact_id:
            if not verify_application_owner(user_id, app_id):
                return resp(404, {"error": "Application not found"}, event)

            deleted = delete_contact(app_id, contact_id, user_id)
            if not deleted:
                return resp(404, {"error": "Contact not found"}, event)

            logger.info("Contact deleted", extra={"app_id": app_id, "contact_id": contact_id})
            return resp(200, {"message": "Deleted", "contactId": contact_id}, event)

        return resp(404, {"error": "Route not found"}, event)

    except Exception:
        logger.exception("Unhandled error in contacts handler")
        return resp(500, {"error": "Internal server error"}, event)