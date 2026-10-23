"""Outgoing mail for password reset: SMTP when configured, the server log otherwise."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Annotated, Protocol

from fastapi import Depends

from savora_backend.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpMailer:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    def _send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port, timeout=15) as smtp:
            if self._s.smtp_starttls:
                smtp.starttls()
            if self._s.smtp_username:
                smtp.login(self._s.smtp_username, self._s.smtp_password)
            smtp.send_message(message)

    async def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._s.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        await asyncio.to_thread(self._send, message)


class LogMailer:
    """Development stand-in: the message goes to the log, so a reset link can be followed
    without a mail server. Never used in production (the link is a credential)."""

    async def send(self, to: str, subject: str, body: str) -> None:
        logger.warning(
            "Mail not configured (SMTP_HOST); would send to %s:\n%s\n%s", to, subject, body
        )


class DisabledMailer:
    """Production without SMTP: nothing is sent and nothing secret is logged."""

    async def send(self, to: str, subject: str, body: str) -> None:
        del to, body
        logger.error("Password reset requested but SMTP_HOST is not configured (%s)", subject)


def get_mailer() -> Mailer:
    settings = get_settings()
    if settings.smtp_host:
        return SmtpMailer(settings)
    return DisabledMailer() if settings.app_env == "production" else LogMailer()


MailerDep = Annotated[Mailer, Depends(get_mailer)]
