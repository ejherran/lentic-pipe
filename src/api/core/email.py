"""
Email sender — stdlib smtplib, no third-party service required.

Two operating modes:

**Log-only (default)** — SMTP_HOST is empty.
    Verification codes are written to the server log and retrievable by an
    admin via GET /auth/email/pending-code. The full verification flow works
    without any mail infrastructure.

**Relay mode** — SMTP_HOST is set.
    Delivers via any standards-compliant SMTP relay (SendGrid, AWS SES,
    Mailgun, Gmail SMTP, a self-hosted Postfix, etc.).  STARTTLS is used when
    SMTP_USE_TLS is true (default). SMTP AUTH is performed when SMTP_USERNAME
    and SMTP_PASSWORD are set.

> ⚠ For emails to reach Gmail / Outlook inboxes reliably you need a relay
> with an established sender reputation and proper SPF / DKIM / DMARC records
> on the sender domain. Without those, messages will land in spam or be
> rejected outright. Document this to end users and instruct them to check
> their spam folder and whitelist the sender address.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.api.config import settings

_logger = logging.getLogger(__name__)


def _build_message(to: str, subject: str, body_text: str, body_html: str | None) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_text, "plain"))
    if body_html:
        msg.attach(MIMEText(body_html, "html"))
    return msg


def _send_sync(msg: MIMEMultipart, to: str, subject: str) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
    _logger.info("email sent", extra={"to": to, "subject": subject})


async def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    """
    Send an email asynchronously. Falls back to stdout logging when SMTP_HOST is not configured.
    Never raises — failures are logged so they never break a request or task flow.
    The blocking smtplib call runs in a thread executor to avoid stalling the event loop.
    """
    if not settings.SMTP_HOST:
        _logger.warning(
            "SMTP not configured — email logged to stdout instead of sent",
            extra={"to": to, "subject": subject, "body": body_text},
        )
        return

    msg = _build_message(to, subject, body_text, body_html)
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_sync, msg, to, subject)
    except Exception:
        _logger.warning("email send failed", extra={"to": to, "subject": subject}, exc_info=True)
