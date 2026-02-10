# ============================================================================== 
# Email Service - SMTP Sending Utilities
# ==============================================================================

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body_text: str) -> None:
    """Send a plain-text email via SMTP.

    In development, if SMTP is not configured, this logs the email instead of
    failing, so the forgot-password flow can still be tested.
    """
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        if settings.ENVIRONMENT.lower() == "development":
            logger.warning(
                "SMTP not configured; skipping email send. "
                "Set SMTP_HOST and SMTP_FROM_EMAIL to enable delivery. "
                "To=%s Subject=%s Body=%s",
                to_email,
                subject,
                body_text,
            )
            return
        raise RuntimeError("SMTP is not configured")

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    smtp_port = settings.SMTP_PORT or 587
    use_tls = True if settings.SMTP_USE_TLS is None else settings.SMTP_USE_TLS

    with smtplib.SMTP(settings.SMTP_HOST, smtp_port, timeout=20) as server:
        if use_tls:
            server.starttls()

        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

        server.send_message(msg)


def send_password_reset_code_email(to_email: str, code: str, expires_minutes: int) -> None:
    subject = "Your verification code"
    body = (
        "Your verification code is: "
        f"{code}\n\n"
        f"This code expires in {expires_minutes} minutes."
    )
    send_email(to_email=to_email, subject=subject, body_text=body)
