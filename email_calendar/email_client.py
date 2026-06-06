"""
Email Client - IMAP/SMTP email client for JARVIS AI Assistant.

Supports reading emails via IMAP and sending emails via SMTP.
Compatible with Gmail, Outlook, and Yahoo providers.
Uses App Passwords only (never real passwords).
"""

import email
import re
import smtplib
import socket
import threading
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from imaplib import IMAP4, IMAP4_SSL
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Provider presets
# ---------------------------------------------------------------------------

PROVIDER_SETTINGS = {
    "gmail": {
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
    },
    "outlook": {
        "imap_server": "outlook.office365.com",
        "imap_port": 993,
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
    },
    "yahoo": {
        "imap_server": "imap.mail.yahoo.com",
        "imap_port": 993,
        "smtp_server": "smtp.mail.yahoo.com",
        "smtp_port": 587,
    },
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _decode_str(raw) -> str:
    """Decode an email header value to a plain string."""
    if raw is None:
        return ""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return "".join(decoded)


def _mask_sensitive(text: str) -> str:
    """Mask credit-card numbers and similar sensitive patterns in text."""
    # Credit card pattern: groups of 4 digits, 4 groups
    text = re.sub(
        r"\b(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})[\s-]?(\d{4})\b",
        r"\1-****-****-\4",
        text,
    )
    # SSN-like pattern
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "***-**-****", text)
    return text


def _get_text_body(msg) -> str:
    """Extract the plain-text body from an email message object."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(charset, errors="replace")
                except Exception:
                    continue
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            try:
                charset = msg.get_content_charset() or "utf-8"
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="replace")
            except Exception:
                pass
    return ""


# ---------------------------------------------------------------------------
# Email data container
# ---------------------------------------------------------------------------

class EmailMessage:
    """Represents a single email message."""

    def __init__(
        self,
        uid: str,
        sender: str,
        sender_email: str,
        subject: str,
        body: str,
        date: str,
        is_unread: bool = True,
    ):
        self.uid = uid
        self.sender = sender
        self.sender_email = sender_email
        self.subject = subject
        self.body = body
        self.date = date
        self.is_unread = is_unread

    def to_dict(self) -> Dict:
        return {
            "uid": self.uid,
            "sender": self.sender,
            "sender_email": self.sender_email,
            "subject": self.subject,
            "body": self.body,
            "date": self.date,
            "is_unread": self.is_unread,
        }

    def brief(self) -> str:
        """Short summary suitable for speech."""
        return f"From {self.sender}: {self.subject}"

    def full(self) -> str:
        """Full email suitable for speech (with sensitive content masked)."""
        safe_body = _mask_sensitive(self.body[:500])
        return (
            f"From {self.sender} on {self.date}. "
            f"Subject: {self.subject}. "
            f"Body: {safe_body}"
        )

    def __repr__(self):
        return f"EmailMessage(uid={self.uid}, from={self.sender}, subject={self.subject})"


# ---------------------------------------------------------------------------
# IMAP/SMTP Email Client
# ---------------------------------------------------------------------------

class EmailClient:
    """
    IMAP/SMTP email client supporting Gmail, Outlook, and Yahoo.

    Only uses App Passwords — never real account passwords.
    All operations are thread-safe via an internal lock.
    """

    IMAP_TIMEOUT = 30  # seconds
    SMTP_TIMEOUT = 30  # seconds

    def __init__(self, config: dict):
        """
        Initialise the email client from configuration.

        Args:
            config: Email config dict with keys:
                provider, address, app_password,
                imap_server, smtp_server, smtp_port
        """
        self.provider = config.get("provider", "gmail")
        self.address = config.get("address", "")
        self.app_password = config.get("app_password", "")

        # Merge provider defaults with explicit overrides
        defaults = PROVIDER_SETTINGS.get(self.provider, PROVIDER_SETTINGS["gmail"])
        self.imap_server = config.get("imap_server", defaults["imap_server"])
        self.imap_port = config.get("imap_port", defaults["imap_port"])
        self.smtp_server = config.get("smtp_server", defaults["smtp_server"])
        self.smtp_port = config.get("smtp_port", defaults["smtp_port"])

        self._imap: Optional[IMAP4_SSL] = None
        self._lock = threading.Lock()
        self._connected = False

    # ── Connection ────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """Check if email credentials are configured."""
        return bool(self.address and self.app_password)

    def connect_imap(self) -> bool:
        """
        Connect to the IMAP server.

        Returns:
            True if connection succeeded, False otherwise.
        """
        if not self.is_configured:
            return False

        try:
            self._imap = IMAP4_SSL(
                self.imap_server,
                self.imap_port,
                timeout=self.IMAP_TIMEOUT,
            )
            self._imap.login(self.address, self.app_password)
            self._connected = True
            print(f"[EmailClient] Connected to IMAP: {self.imap_server}")
            return True
        except IMAP4.error as exc:
            print(f"[EmailClient] IMAP login error: {exc}")
            self._connected = False
            return False
        except (socket.timeout, ConnectionError, OSError) as exc:
            print(f"[EmailClient] IMAP connection error: {exc}")
            self._connected = False
            return False

    def disconnect_imap(self):
        """Disconnect from the IMAP server."""
        if self._imap:
            try:
                self._imap.close()
            except Exception:
                pass
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None
            self._connected = False
            print("[EmailClient] Disconnected from IMAP")

    def _ensure_connected(self) -> bool:
        """Ensure IMAP is connected; reconnect if needed."""
        if self._connected and self._imap:
            return True
        return self.connect_imap()

    # ── Fetching ──────────────────────────────────────────────────

    def fetch_unread(self, count: int = 5) -> List[EmailMessage]:
        """
        Fetch the most recent unread emails.

        Args:
            count: Maximum number of emails to fetch.

        Returns:
            List of EmailMessage objects.
        """
        with self._lock:
            if not self._ensure_connected():
                return []

            try:
                self._imap.select("INBOX")
                status, data = self._imap.search(None, "UNSEEN")
                if status != "OK":
                    return []

                uid_list = data[0].split()
                # Take the most recent 'count' emails (last in list)
                recent_uids = uid_list[-count:] if len(uid_list) > count else uid_list
                recent_uids = list(reversed(recent_uids))  # newest first

                messages = []
                for uid in recent_uids:
                    msg = self._fetch_single(uid)
                    if msg:
                        messages.append(msg)

                return messages

            except (IMAP4.error, socket.timeout, ConnectionError) as exc:
                print(f"[EmailClient] fetch_unread error: {exc}")
                self._connected = False
                return []

    def fetch_email(self, uid: str) -> Optional[EmailMessage]:
        """
        Fetch a single email by UID.

        Args:
            uid: IMAP UID of the email.

        Returns:
            EmailMessage or None if not found.
        """
        with self._lock:
            if not self._ensure_connected():
                return None
            return self._fetch_single(uid)

    def fetch_latest(self, count: int = 5) -> List[EmailMessage]:
        """
        Fetch the latest emails (read + unread).

        Args:
            count: Maximum number of emails to fetch.

        Returns:
            List of EmailMessage objects, newest first.
        """
        with self._lock:
            if not self._ensure_connected():
                return []

            try:
                self._imap.select("INBOX")
                status, data = self._imap.search(None, "ALL")
                if status != "OK":
                    return []

                uid_list = data[0].split()
                recent_uids = uid_list[-count:] if len(uid_list) > count else uid_list
                recent_uids = list(reversed(recent_uids))

                messages = []
                for uid in recent_uids:
                    msg = self._fetch_single(uid)
                    if msg:
                        messages.append(msg)

                return messages

            except (IMAP4.error, socket.timeout, ConnectionError) as exc:
                print(f"[EmailClient] fetch_latest error: {exc}")
                self._connected = False
                return []

    def _fetch_single(self, uid: bytes) -> Optional[EmailMessage]:
        """Internal: fetch and parse a single email by UID."""
        try:
            status, data = self._imap.fetch(uid, "(RFC822)")
            if status != "OK":
                return None

            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            from_header = _decode_str(msg.get("From", ""))
            sender_name, sender_email = parseaddr(from_header)
            if not sender_name:
                sender_name = sender_email

            subject = _decode_str(msg.get("Subject", ""))
            date = _decode_str(msg.get("Date", ""))
            body = _get_text_body(msg)

            # Determine read/unread from FLAGS if available
            is_unread = True  # default; actual flag check would need FETCH with FLAGS

            return EmailMessage(
                uid=uid.decode() if isinstance(uid, bytes) else str(uid),
                sender=sender_name,
                sender_email=sender_email,
                subject=subject,
                body=body.strip(),
                date=date,
                is_unread=is_unread,
            )

        except Exception as exc:
            print(f"[EmailClient] _fetch_single error for UID {uid}: {exc}")
            return None

    # ── Searching ─────────────────────────────────────────────────

    def search_emails(self, query: str, criteria: str = "FROM") -> List[EmailMessage]:
        """
        Search emails by a criterion.

        Args:
            query: Search term (e.g. sender name, subject keyword).
            criteria: IMAP search criterion — "FROM", "SUBJECT", "TO", "BODY".

        Returns:
            List of matching EmailMessage objects.
        """
        with self._lock:
            if not self._ensure_connected():
                return []

            try:
                self._imap.select("INBOX")
                search_query = f'({criteria} "{query}")'
                status, data = self._imap.search(None, search_query)
                if status != "OK":
                    return []

                uid_list = data[0].split()
                # Return at most 20 results, newest first
                recent_uids = uid_list[-20:] if len(uid_list) > 20 else uid_list
                recent_uids = list(reversed(recent_uids))

                messages = []
                for uid in recent_uids:
                    msg = self._fetch_single(uid)
                    if msg:
                        messages.append(msg)

                return messages

            except (IMAP4.error, socket.timeout, ConnectionError) as exc:
                print(f"[EmailClient] search_emails error: {exc}")
                self._connected = False
                return []

    # ── Deleting ──────────────────────────────────────────────────

    def delete_email(self, uid: str) -> bool:
        """
        Delete an email by UID.

        Args:
            uid: IMAP UID of the email to delete.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        with self._lock:
            if not self._ensure_connected():
                return False

            try:
                self._imap.select("INBOX")
                uid_bytes = uid.encode() if isinstance(uid, str) else uid
                self._imap.store(uid_bytes, "+FLAGS", "\\Deleted")
                self._imap.expunge()
                print(f"[EmailClient] Deleted email UID {uid}")
                return True

            except (IMAP4.error, socket.timeout, ConnectionError) as exc:
                print(f"[EmailClient] delete_email error: {exc}")
                self._connected = False
                return False

    # ── Sending ───────────────────────────────────────────────────

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Send an email via SMTP.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Email body (plain text).

        Returns:
            True if the email was sent successfully, False otherwise.
        """
        if not self.is_configured:
            print("[EmailClient] Cannot send: not configured")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.address
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.SMTP_TIMEOUT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.address, self.app_password)
                server.sendmail(self.address, [to], msg.as_string())

            print(f"[EmailClient] Email sent to {to}")
            return True

        except smtplib.SMTPAuthenticationError as exc:
            print(f"[EmailClient] SMTP auth error: {exc}")
            return False
        except (socket.timeout, ConnectionError, OSError) as exc:
            print(f"[EmailClient] SMTP connection error: {exc}")
            return False
        except Exception as exc:
            print(f"[EmailClient] send_email error: {exc}")
            return False

    # ── Unread count ──────────────────────────────────────────────

    def get_unread_count(self) -> int:
        """
        Get the number of unread emails in the inbox.

        Returns:
            Number of unread emails, or -1 on error.
        """
        with self._lock:
            if not self._ensure_connected():
                return -1

            try:
                status, data = self._imap.select("INBOX")
                if status != "OK":
                    return -1

                # data[0] contains the mailbox message count
                # Use SEARCH UNSEEN to get actual unread count
                status, search_data = self._imap.search(None, "UNSEEN")
                if status != "OK":
                    return -1

                uid_list = search_data[0].split()
                return len(uid_list)

            except (IMAP4.error, socket.timeout, ConnectionError) as exc:
                print(f"[EmailClient] get_unread_count error: {exc}")
                self._connected = False
                return -1
