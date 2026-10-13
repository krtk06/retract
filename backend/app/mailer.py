"""Outbound email.

One message type exists — the address-verification link — so this module is small
on purpose. It uses `smtplib` from the standard library rather than a mail library:
the requirements are "send a short text message over an authenticated submission
port", and a dependency for that is more surface than it is worth.

Delivery is best-effort and never fails the request that triggered it. A sign-up
must not 500 because Gmail was briefly unavailable; the user can ask for another
link. What is *not* best-effort is saying so: an unsent verification link is logged
loudly, because otherwise the feature fails invisibly and the only symptom is that
GitHub sign-ins never link to email accounts.
"""

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import unquote, urlsplit

from app.config import get_settings

logger = logging.getLogger(__name__)


def send(to: str, subject: str, body: str) -> None:
    """Deliver a plain-text message, or explain why it could not be delivered."""
    settings = get_settings()
    if not settings.smtp_url:
        _no_transport(to, subject, body)
        return
    try:
        _send_smtp(settings.smtp_url, settings.mail_from, to, subject, body)
    except (OSError, smtplib.SMTPException, ValueError):
        logger.exception("could not send %r to %s; the request continues", subject, to)


def _no_transport(to: str, subject: str, body: str) -> None:
    """With no SMTP configured, make the message visible without leaking it.

    In development the body is printed, which is the point — there is no other way
    to follow the link. In production only the fact is logged: printing the body
    would write a working verification link, and any other future message contents,
    into the logs where anyone with log access could use it.
    """
    if get_settings().is_production:
        logger.error(
            "no RETRACT_SMTP_URL is configured, so email to %s was NOT sent (%r). "
            "Address verification cannot work, and GitHub sign-ins will never link "
            "to email accounts.",
            to,
            subject,
        )
        return
    logger.warning("email not sent (no RETRACT_SMTP_URL). to=%s subject=%r\n%s", to, subject, body)


def _send_smtp(smtp_url: str, sender: str, to: str, subject: str, body: str) -> None:
    parts = urlsplit(smtp_url)
    if parts.scheme not in ("smtp", "smtps"):
        raise ValueError(f"unsupported scheme in RETRACT_SMTP_URL: {parts.scheme!r}")
    if not parts.hostname:
        raise ValueError("RETRACT_SMTP_URL has no host")

    # Credentials arrive percent-encoded (a Gmail address is `user%40gmail.com`).
    username = unquote(parts.username) if parts.username else None
    password = unquote(parts.password) if parts.password else None
    port = parts.port or (465 if parts.scheme == "smtps" else 587)

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    if parts.scheme == "smtps":
        with smtplib.SMTP_SSL(parts.hostname, port, timeout=20) as client:
            if username and password:
                client.login(username, password)
            client.send_message(message)
        return

    # `smtp://` means STARTTLS, which is what every submission port expects; using
    # it without TLS would put the credentials on the wire in the clear.
    with smtplib.SMTP(parts.hostname, port, timeout=20) as client:
        client.starttls()
        if username and password:
            client.login(username, password)
        client.send_message(message)


def send_verification(to: str, link: str, ttl_hours: int) -> None:
    send(
        to,
        "Verify your email for Retract",
        (
            "Confirm this address to finish setting up your Retract account.\n\n"
            f"{link}\n\n"
            f"The link works once and expires in {ttl_hours} hour(s). If you did not "
            "create an account, you can ignore this message.\n"
        ),
    )
