# ============================================================================== 
# Password Reset Service - Forgot Password Verification Codes
# ==============================================================================

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import secrets

from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.password_reset_code import PasswordResetCode
from app.services.email_service import send_password_reset_code_email

logger = logging.getLogger(__name__)


def _as_utc(dt: datetime) -> datetime:
    """Coerce a datetime to timezone-aware UTC.

    Some DB drivers return naive datetimes even if the original value
    was created with tzinfo. We normalize to avoid naive/aware comparisons.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _generate_6_digit_code() -> str:
    return str(secrets.randbelow(1_000_000)).zfill(6)


def send_forgot_password_verification_code(session: Session, email: str) -> None:
    """Generate + store a 6-digit code and send it to the user's email.

    Raises:
        ValueError: if user does not exist or is inactive
        RuntimeError: if email delivery is not configured in non-dev env
    """
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.is_active:
        raise ValueError("Email is not registered")

    # Remove any previously issued unused codes for this user
    existing_codes = session.exec(
        select(PasswordResetCode).where(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.used_at.is_(None),
        )
    ).all()
    for code_row in existing_codes:
        session.delete(code_row)

    code = _generate_6_digit_code()
    expires_minutes = settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

    reset_row = PasswordResetCode(
        user_id=user.id,
        email=email,
        code_hash=hash_password(code),
        expires_at=expires_at,
    )

    session.add(reset_row)
    session.commit()

    # Send email (or log in development if SMTP not configured)
    send_password_reset_code_email(to_email=email, code=code, expires_minutes=expires_minutes)

    logger.info("Issued password reset code for user_id=%s", user.id)


def verify_forgot_password_verification_code(session: Session, email: str, code: str) -> None:
    """Verify that a 6-digit code is correct, un-used, and un-expired.

    Raises:
        ValueError: if email not registered/inactive or code invalid/expired/used
    """
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.is_active:
        raise ValueError("Email is not registered")

    reset_row = session.exec(
        select(PasswordResetCode)
        .where(
            PasswordResetCode.email == email,
            PasswordResetCode.used_at.is_(None),
        )
        .order_by(PasswordResetCode.created_at.desc())
    ).first()

    if not reset_row:
        raise ValueError("Invalid or expired verification code")

    now = datetime.now(timezone.utc)
    if _as_utc(reset_row.expires_at) < now:
        raise ValueError("Invalid or expired verification code")

    if not verify_password(code, reset_row.code_hash):
        raise ValueError("Invalid or expired verification code")


def reset_password_with_verification_code(
    session: Session,
    email: str,
    code: str,
    new_password: str,
) -> None:
    """Reset the user's password using a valid verification code.

    This marks the code as used.

    Raises:
        ValueError: if email not registered/inactive or code invalid/expired/used
    """
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not user.is_active:
        raise ValueError("Email is not registered")

    reset_row = session.exec(
        select(PasswordResetCode)
        .where(
            PasswordResetCode.email == email,
            PasswordResetCode.used_at.is_(None),
        )
        .order_by(PasswordResetCode.created_at.desc())
    ).first()

    if not reset_row:
        raise ValueError("Invalid or expired verification code")

    now = datetime.now(timezone.utc)
    if _as_utc(reset_row.expires_at) < now:
        raise ValueError("Invalid or expired verification code")

    if not verify_password(code, reset_row.code_hash):
        raise ValueError("Invalid or expired verification code")

    user.hashed_password = hash_password(new_password)
    reset_row.used_at = now

    session.add(user)
    session.add(reset_row)
    session.commit()

    logger.info("Password reset completed for user_id=%s", user.id)
