"""
Shared middleware for all Applytic Lambda handlers.
Single source of truth for:
  - HTTP response formatting + CORS headers
  - Auth/user extraction from Cognito JWT claims
  - Structured logging with correlation IDs
  - Request validation helpers
  - Common error types
"""
import json
import uuid
import os
from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))

ALLOWED_ORIGINS = [
    "https://d3jumje9o63lys.cloudfront.net",
    "https://hardikjp7.github.io",
    "https://hardikjp7.com"
]

def _get_cors_origin(event: dict) -> str:
    origin = (event.get("headers") or {}).get("origin", "") or \
             (event.get("headers") or {}).get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        return origin
    return ALLOWED_ORIGINS[0]

def resp(status: int, body: dict, event: dict = None) -> dict:
    origin = _get_cors_origin(event) if event else ALLOWED_ORIGINS[0]
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }

def get_user_id(event: dict) -> str:
    return event["requestContext"]["authorizer"]["claims"]["sub"]

def get_user_email(event: dict) -> str:
    return event["requestContext"]["authorizer"]["claims"].get("email", "")

def get_correlation_id(event: dict) -> str:
    return (
        event.get("requestContext", {}).get("requestId")
        or str(uuid.uuid4())
    )

def parse_body(event: dict) -> tuple:
    raw = event.get("body")
    if not raw:
        return {}, None
    try:
        return json.loads(raw), None
    except (json.JSONDecodeError, TypeError):
        return {}, resp(400, {"error": "Invalid JSON body"}, event)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def with_middleware(handler_fn):
    def wrapper(event: dict, context: LambdaContext) -> dict:
        correlation_id = get_correlation_id(event)
        logger.set_correlation_id(correlation_id)
        logger.info("Request received", extra={
            "http_method": event.get("httpMethod"),
            "path": event.get("path"),
            "correlation_id": correlation_id,
        })
        try:
            response = handler_fn(event, context)
            logger.info("Request completed", extra={
                "status_code": response.get("statusCode"),
                "correlation_id": correlation_id,
            })
            return response
        except Exception as e:
            logger.exception("Unhandled exception", extra={"correlation_id": correlation_id})
            return resp(500, {"error": "Internal server error"}, event)
    return wrapper
