"""
Cognito Post Confirmation Lambda — v1.2
Triggered automatically after a user confirms their Cognito account.
Sends SES email verification so the user can receive Monday digests.

Note: Never blocks Cognito signup — all errors are caught and swallowed.
In v2.0 this is replaced by SES production access.
"""
import os
import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

ses = boto3.client("ses")
logger = Logger(service=os.environ.get("POWERTOOLS_SERVICE_NAME", "applytic"))


def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Cognito requires this function to return the event unchanged.
    Never raise an exception — it would block the user's signup.
    """
    try:
        email = event.get("request", {}).get("userAttributes", {}).get("email")

        if not email:
            logger.warning("No email in Cognito trigger event",
                           extra={"trigger_source": event.get("triggerSource")})
            return event

        # Skip if already verified — avoids duplicate verification emails
        try:
            result = ses.get_identity_verification_attributes(Identities=[email])
            status = result["VerificationAttributes"].get(email, {}).get("VerificationStatus")
            if status == "Success":
                logger.info("Email already SES-verified, skipping", extra={"email": email})
                return event
        except Exception:
            pass  # If check fails, proceed with verification attempt

        # Send SES verification email
        ses.verify_email_identity(EmailAddress=email)

        logger.info("SES verification email sent", extra={
            "email": email,
            "trigger_source": event.get("triggerSource"),
        })

    except ses.exceptions.ClientError as e:
        # Log but never block signup
        logger.error("SES call failed — user signup not blocked", extra={"error": str(e)})

    except Exception:
        logger.exception("Unexpected error in Post Confirmation trigger")

    # Always return event unchanged
    return event
