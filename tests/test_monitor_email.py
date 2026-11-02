"""Check optional notification behavior without sending email."""

from unittest.mock import MagicMock

import pytest

from monitoring.agent import send_email


def email_settings():
    return {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_USERNAME": "sender@example.com",
        "SMTP_PASSWORD": "example-password",
        "ALERT_EMAIL_TO": "different@example.org",
    }


def test_email_is_skipped_when_not_configured(monkeypatch):
    smtp = MagicMock()
    monkeypatch.setattr(send_email.smtplib, "SMTP", smtp)
    assert send_email.send_notification({}, "Test report") is False
    smtp.assert_not_called()


def test_email_uses_starttls_and_separate_recipient(monkeypatch):
    connection = MagicMock()
    smtp = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=connection), __exit__=MagicMock(return_value=False)))
    monkeypatch.setattr(send_email.smtplib, "SMTP", smtp)

    assert send_email.send_notification(email_settings(), "English report") is True

    smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
    connection.starttls.assert_called_once()
    connection.login.assert_called_once_with("sender@example.com", "example-password")
    message = connection.send_message.call_args.args[0]
    assert message["From"] == "sender@example.com"
    assert message["To"] == "different@example.org"
    assert "English report" in message.get_content()


def test_partial_email_configuration_fails_without_connecting(monkeypatch):
    smtp = MagicMock()
    monkeypatch.setattr(send_email.smtplib, "SMTP", smtp)
    with pytest.raises(ValueError, match="Missing email settings"):
        send_email.send_notification({"ALERT_EMAIL_TO": "different@example.org"}, "report")
    smtp.assert_not_called()


def test_multiple_recipient_addresses_are_rejected():
    settings = email_settings()
    settings["ALERT_EMAIL_TO"] = "one@example.org, two@example.org"
    with pytest.raises(ValueError):
        send_email.send_notification(settings, "report")
