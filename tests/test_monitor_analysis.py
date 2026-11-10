"""Validate failure evidence without making GitHub or OpenAI API calls."""

import io
import json
import base64
import zipfile
from types import SimpleNamespace

import pytest

from monitoring.agent import collect_evidence
from monitoring.agent import analyze_failure


def monitor_run(**overrides):
    run = {
        "path": ".github/workflows/monitor.yml",
        "status": "completed",
        "conclusion": "failure",
        "event": "workflow_dispatch",
        "head_repository": {"full_name": "example/project"},
        "run_attempt": 2,
        "head_sha": "abc123",
    }
    run.update(overrides)
    return run


def test_evidence_is_bounded_and_redacted(monkeypatch):
    monkeypatch.setattr(collect_evidence, "gh", lambda *args: SimpleNamespace(stdout=json.dumps(monitor_run())))
    monkeypatch.setattr(collect_evidence.tempfile, "TemporaryFile", io.BytesIO)

    def fake_run(args, *, stdout, **kwargs):
        stdout.write(b"x" * 41000 + b"\ntoken=secret-value sk-example1234567890")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(collect_evidence.subprocess, "run", fake_run)
    evidence = collect_evidence.collect("123", "2", "example/project")

    assert evidence["attempt"] == "2"
    assert evidence["log_truncated"] is True
    assert len(evidence["failed_step_log"].encode()) <= collect_evidence.MAX_LOG_BYTES
    assert "secret-value" not in evidence["failed_step_log"]
    assert "sk-example1234567890" not in evidence["failed_step_log"]


@pytest.mark.parametrize("run", [
    monitor_run(conclusion="success"),
    monitor_run(path=".github/workflows/other.yml"),
    monitor_run(head_repository={"full_name": "other/project"}),
])
def test_only_failed_monitor_runs_are_accepted(monkeypatch, run):
    monkeypatch.setattr(collect_evidence, "gh", lambda *args: SimpleNamespace(stdout=json.dumps(run)))
    with pytest.raises(ValueError, match="not a completed failed monitor run"):
        collect_evidence.collect("123", None, "example/project")


def test_invalid_run_id_is_rejected():
    with pytest.raises(ValueError, match="positive integer"):
        collect_evidence.collect("123; unexpected", None, "example/project")


def test_missing_api_key_creates_failure_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert analyze_failure.main() == 1
    assert "OPENAI_API_KEY is missing" in capsys.readouterr().err
    report = (tmp_path / "analysis-output" / "report.md").read_text(encoding="utf-8")
    assert "agent analysis did not complete" in report
    assert "API key is not configured" in report


def test_authentication_failure_produces_safe_explanation(tmp_path, monkeypatch):
    class AuthenticationError(Exception):
        pass

    async def failed_analysis(evidence):
        raise AuthenticationError("sensitive provider details")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(analyze_failure, "analyze", failed_analysis)
    output = tmp_path / "analysis-output"
    output.mkdir()
    (output / "evidence.json").write_text('{}', encoding="utf-8")

    assert analyze_failure.main() == 1
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "OpenAI authentication failed" in report
    assert "sensitive provider details" not in report


def test_screenshot_from_selected_attempt_prefers_second(monkeypatch):
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nmV8AAAAASUVORK5CYII=")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("failure-1.png", png)
        z.writestr("failure-2.png", png + b"second")
    artifacts = {"total_count": 2, "artifacts": [
        {"id": 1, "name": "dashboard-monitor-failure", "expired": False, "size_in_bytes": 1000, "created_at": "2026-01-01T10:00:00Z"},
        {"id": 2, "name": "dashboard-monitor-failure", "expired": False, "size_in_bytes": 1000, "created_at": "2026-01-02T10:00:00Z"},
    ]}
    attempt = {"run_started_at": "2026-01-02T09:59:00Z", "updated_at": "2026-01-02T10:01:00Z"}
    monkeypatch.setattr(collect_evidence, "gh", lambda *args: SimpleNamespace(stdout=json.dumps(artifacts)))
    monkeypatch.setattr(collect_evidence.tempfile, "TemporaryFile", io.BytesIO)

    def download(args, *, stdout, **kwargs):
        assert "/artifacts/2/zip" in args[-1]
        stdout.write(archive.getvalue())
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(collect_evidence.subprocess, "run", download)
    image, note = collect_evidence.fetch_screenshot("123", attempt, "example/project")
    assert image == png + b"second"
    assert "failure-2.png" in note


def test_missing_screenshot_falls_back_to_log_only(monkeypatch):
    attempt = {"run_started_at": "2026-01-02T09:59:00Z", "updated_at": "2026-01-02T10:01:00Z"}
    monkeypatch.setattr(collect_evidence, "gh", lambda *args: SimpleNamespace(stdout=json.dumps({"total_count": 0, "artifacts": []})))
    image, note = collect_evidence.fetch_screenshot("123", attempt, "example/project")
    assert image is None
    assert "No unique screenshot" in note


def test_model_input_contains_at_most_one_image():
    input_items = analyze_failure.build_input({"failed_step_log": "example", "screenshot_base64": "aW1hZ2U="})
    content = input_items[0]["content"]
    assert [item["type"] for item in content] == ["input_text", "input_image"]
    assert content[1]["image_url"] == "data:image/png;base64,aW1hZ2U="
    assert "aW1hZ2U=" not in content[0]["text"]
    no_image = analyze_failure.build_input({"screenshot_base64": None})[0]["content"]
    assert len(no_image) == 1


def test_data_release_failure_evidence_uses_only_matching_workflow(monkeypatch):
    run = monitor_run(path='.github/workflows/data-release.yml')
    monkeypatch.setattr(collect_evidence, 'gh', lambda *args: SimpleNamespace(stdout=json.dumps(run)))
    monkeypatch.setattr(collect_evidence.tempfile, 'TemporaryFile', io.BytesIO)
    def fake_run(args, *, stdout, **kwargs):
        stdout.write(b'token=secret-value validation failed')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(collect_evidence.subprocess, 'run', fake_run)
    evidence = collect_evidence.collect('123', '2', 'example/project', data_release=True)
    assert 'secret-value' not in evidence['failed_step_log']
    assert evidence['screenshot_base64'] is None
    with pytest.raises(ValueError):
        collect_evidence.collect('123', '2', 'example/project')
