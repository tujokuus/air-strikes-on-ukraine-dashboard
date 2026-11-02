"""Optionally email the analysis through an authenticated STARTTLS SMTP server."""

from __future__ import annotations

from email.headerregistry import Address
from email.message import EmailMessage
import os
from pathlib import Path
import re
import smtplib
import ssl
import sys


REQUIRED = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "ALERT_EMAIL_TO")


def address(value: str) -> str:
    """Accept one plain email address, never a list or injected header."""
    parsed = Address(addr_spec=value)
    if not parsed.username or not parsed.domain:
        raise ValueError("Invalid email address")
    return parsed.addr_spec


def send_notification(environ: dict, report: str, *, analysis_unavailable: bool = False) -> bool:
    """Send one message, or skip when SMTP has not been configured at all."""
    values = {name: environ.get(name, "") for name in REQUIRED}
    for name in ("SMTP_HOST", "SMTP_USERNAME", "ALERT_EMAIL_TO"):
        values[name] = values[name].strip()
    if not any(values.values()):
        print("Email notification is not configured; skipping.")
        return False
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError("Missing email settings: " + ", ".join(missing))

    port = int(environ.get("SMTP_PORT", "").strip() or "587")
    if not 1 <= port <= 65535:
        raise ValueError("Invalid SMTP_PORT")
    sender = address(environ.get("SMTP_FROM", "").strip() or values["SMTP_USERNAME"])
    recipient = address(values["ALERT_EMAIL_TO"])

    message = EmailMessage()
    message["Subject"] = (
        "Dashboard monitor failed - agent analysis unavailable"
        if analysis_unavailable else "Dashboard monitoring failure analysis"
    )
    message["From"] = sender
    message["To"] = recipient
    message.set_content(report)

    with smtplib.SMTP(values["SMTP_HOST"], port, timeout=30) as connection:
        connection.ehlo()
        connection.starttls(context=ssl.create_default_context())
        connection.ehlo()
        connection.login(values["SMTP_USERNAME"], values["SMTP_PASSWORD"])
        connection.send_message(message)
    print("Analysis notification sent.")
    return True


def main() -> int:
    try:
        path = Path("analysis-output/report.md")
        analysis_unavailable = not path.is_file() or os.environ.get("ANALYSIS_OUTCOME") in {"failure", "skipped", "cancelled"}
        report = path.read_text(encoding="utf-8") if path.is_file() else (
            "Monitor failure analysis could not be completed. "
            "Please check the analysis workflow in GitHub Actions.\n"
        )
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        monitor_run_id = os.environ.get("MONITOR_RUN_ID", "")
        attempt = os.environ.get("MONITOR_RUN_ATTEMPT", "")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            if re.fullmatch(r"[1-9][0-9]*", monitor_run_id):
                monitor_url = f"https://github.com/{repo}/actions/runs/{monitor_run_id}"
                if re.fullmatch(r"[1-9][0-9]*", attempt):
                    monitor_url += f"/attempts/{attempt}"
                if monitor_url not in report:
                    report += f"\nOriginal monitor run: {monitor_url}\n"
            if re.fullmatch(r"[1-9][0-9]*", run_id):
                report += f"\nAnalysis workflow: https://github.com/{repo}/actions/runs/{run_id}\n"
        send_notification(os.environ, report, analysis_unavailable=analysis_unavailable)
        return 0
    except ValueError as exc:
        # Only disclose known configuration names, never secrets or addresses.
        message = str(exc)
        if message.startswith("Missing email settings:") or message == "Invalid SMTP_PORT":
            print(message, file=sys.stderr)
        else:
            print("Invalid email configuration.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Email notification failed: {type(exc).__name__}.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
