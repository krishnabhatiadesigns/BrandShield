"""Durable notification, webhook and usage helpers."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import smtplib
import threading
import time
from email.message import EmailMessage
from urllib.parse import urlsplit

from .config import get_settings
from .db import Database
from .seed import now_iso

log = logging.getLogger("brandshield.operations")


def queue_notification(
    db: Database,
    workspace_id: int,
    recipient: str,
    subject: str,
    body: str,
) -> None:
    db.insert(
        "INSERT INTO notification_outbox"
        " (workspace_id, recipient, subject, body, status, attempts, created_at)"
        " VALUES (?, ?, ?, ?, 'pending', 0, ?)",
        (workspace_id, recipient.strip(), subject.strip(), body.strip(), now_iso()),
    )


def queue_webhook(
    db: Database,
    workspace_id: int,
    event_type: str,
    payload: dict,
) -> None:
    endpoints = db.query(
        "SELECT id, events FROM webhook_endpoints"
        " WHERE workspace_id = ? AND is_active = 1",
        (workspace_id,),
    )
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    for endpoint in endpoints:
        events = {item.strip() for item in (endpoint["events"] or "").split(",")}
        if "*" not in events and event_type not in events:
            continue
        db.insert(
            "INSERT INTO webhook_deliveries"
            " (workspace_id, endpoint_id, event_type, payload, status, attempts, created_at)"
            " VALUES (?, ?, ?, ?, 'pending', 0, ?)",
            (workspace_id, int(endpoint["id"]), event_type, serialized, now_iso()),
        )


def record_usage(db: Database, workspace_id: int, event_type: str, actor: str = "") -> None:
    db.insert(
        "INSERT INTO usage_events (workspace_id, event_type, quantity, actor, created_at)"
        " VALUES (?, ?, 1, ?, ?)",
        (workspace_id, event_type, actor or None, now_iso()),
    )


def safe_webhook_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        return False
    if parsed.username or parsed.password or parsed.fragment:
        return False
    if parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False
    if parsed.hostname.endswith(".local"):
        return False
    return True


def _deliver_notifications(db: Database) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        return
    for row in db.query(
        "SELECT * FROM notification_outbox"
        " WHERE status = 'pending' AND attempts < 5"
        " ORDER BY created_at LIMIT 20"
    ):
        try:
            message = EmailMessage()
            message["From"] = settings.smtp_from
            message["To"] = row["recipient"]
            message["Subject"] = row["subject"]
            message.set_content(row["body"])
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=15,
            ) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
            db.execute(
                "UPDATE notification_outbox SET status='sent', sent_at=?, attempts=attempts+1,"
                " last_error=NULL WHERE id=?",
                (now_iso(), int(row["id"])),
            )
        except Exception as exc:
            db.execute(
                "UPDATE notification_outbox SET attempts=attempts+1,"
                " status=?, last_error=? WHERE id=?",
                (
                    "failed" if int(row["attempts"]) + 1 >= 5 else "pending",
                    str(exc)[:500],
                    int(row["id"]),
                ),
            )


def _deliver_webhooks(db: Database) -> None:
    try:
        import httpx
    except ImportError:
        return
    for row in db.query(
        "SELECT d.*, e.url, e.secret"
        " FROM webhook_deliveries d JOIN webhook_endpoints e ON e.id=d.endpoint_id"
        " WHERE d.status='pending' AND d.attempts < 5"
        " ORDER BY d.created_at LIMIT 20"
    ):
        timestamp = str(int(time.time()))
        signature = hmac.new(
            row["secret"].encode("utf-8"),
            f"{timestamp}.{row['payload']}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        try:
            response = httpx.post(
                row["url"],
                content=row["payload"],
                headers={
                    "Content-Type": "application/json",
                    "X-BrandShield-Timestamp": timestamp,
                    "X-BrandShield-Signature": f"sha256={signature}",
                    "User-Agent": "BrandShield-Webhook/1",
                },
                timeout=10,
                follow_redirects=False,
            )
            if 200 <= response.status_code < 300:
                db.execute(
                    "UPDATE webhook_deliveries SET status='delivered', delivered_at=?,"
                    " attempts=attempts+1, last_status=?, last_error=NULL WHERE id=?",
                    (now_iso(), response.status_code, int(row["id"])),
                )
            else:
                raise RuntimeError(f"HTTP {response.status_code}")
        except Exception as exc:
            attempts = int(row["attempts"]) + 1
            db.execute(
                "UPDATE webhook_deliveries SET attempts=?, status=?, last_error=?, last_status=?"
                " WHERE id=?",
                (
                    attempts,
                    "failed" if attempts >= 5 else "pending",
                    str(exc)[:500],
                    getattr(locals().get("response"), "status_code", None),
                    int(row["id"]),
                ),
            )


def start_operations_worker(db: Database) -> threading.Thread | None:
    settings = get_settings()
    if not settings.notification_worker_enabled:
        return None

    def run() -> None:
        while True:
            _deliver_notifications(db)
            _deliver_webhooks(db)
            time.sleep(30)

    thread = threading.Thread(target=run, name="brandshield-operations", daemon=True)
    thread.start()
    log.info("BrandShield operations worker started")
    return thread
