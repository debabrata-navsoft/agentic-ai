"""Outgoing email: password-reset links. Without an SMTP host the link is logged instead,
which is enough for local development."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import Settings

log = logging.getLogger(__name__)


def send_reset_link(settings: Settings, to: str, link: str) -> None:
    if not settings.smtp_host:
        log.warning("Password reset link for %s (no SMTP configured): %s", to, link)
        return
    msg = EmailMessage()
    msg["Subject"] = "Reset your Synora password"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(
        f"Someone asked to reset the password for your Synora account.\n\n"
        f"Open this link within {settings.reset_minutes} minutes to choose a new password:\n{link}\n\n"
        "If this wasn't you, ignore this email; your password won't change."
    )
    smtp_class = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
    try:
        with smtp_class(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if smtp_class is smtplib.SMTP and settings.smtp_port == 587:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        log.exception("Could not send the password reset email to %s", to)
