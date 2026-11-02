"""Check that the deployed Streamlit overview loads in a real browser."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error, TimeoutError as PlaywrightTimeoutError, sync_playwright


APP_URL = os.environ.get(
    "DASHBOARD_URL", "https://air-strikes-on-ukraine-dashboard.streamlit.app/"
)
ARTIFACT_DIR = Path(os.environ.get("MONITOR_ARTIFACT_DIR", "monitor-artifacts"))
TIMEOUT_SECONDS = int(os.environ.get("MONITOR_TIMEOUT_SECONDS", "180"))
MAX_ATTEMPTS = 2


def check_page(page) -> None:
    """Wait for the overview metric and wake a sleeping Streamlit app if asked."""
    page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
    deadline = time.monotonic() + TIMEOUT_SECONDS
    wake_clicked = False
    expected_host = urlparse(APP_URL).netloc
    heading_visible = False
    metric_visible = False
    app_frame_count = 0
    while time.monotonic() < deadline:
        # Community Cloud can embed the app in a same-origin iframe. Ignore
        # unrelated frames, such as Streamlit's status widget.
        app_frames = [frame for frame in page.frames if urlparse(frame.url).netloc == expected_host]
        app_frame_count = len(app_frames)
        heading_visible = False
        metric_visible = False
        for frame in app_frames:
            try:
                wake_button = frame.get_by_role("button", name="Yes, get this app back up!")
                if not wake_clicked and wake_button.is_visible():
                    print("Sleeping app detected; requesting wake-up.", flush=True)
                    wake_button.click(timeout=10_000)
                    wake_clicked = True

                errors = frame.get_by_test_id("stException")
                if errors.count() and errors.first.is_visible():
                    raise RuntimeError(f"Streamlit exception: {errors.first.inner_text()[:1500]}")
                bootstrap_error = frame.get_by_text(
                    "Gold database was not found and automatic data bootstrap failed.", exact=False
                )
                if bootstrap_error.count() and bootstrap_error.first.is_visible():
                    raise RuntimeError("The dashboard reported a data bootstrap error.")

                heading = frame.locator("h1").filter(has_text="Air Strikes in Ukraine Analytics")
                metric = frame.get_by_test_id("stMetric").filter(has_text="Launched total")
                frame_heading = bool(heading.count() and heading.first.is_visible())
                frame_metric = bool(metric.count() and metric.first.is_visible())
                heading_visible |= frame_heading
                metric_visible |= frame_metric
                if frame_heading and frame_metric:
                    print("Overview heading and Launched total metric are visible.", flush=True)
                    return
            except Error:
                if not frame.is_detached():
                    raise
        page.wait_for_timeout(2_000)
    raise TimeoutError(
        f"Overview did not load within {TIMEOUT_SECONDS} seconds. "
        f"Visible heading: {heading_visible}; visible Launched total metric: {metric_visible}; "
        f"app frames: {app_frame_count}."
    )


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"Checking {APP_URL} (attempt {attempt}/{MAX_ATTEMPTS})", flush=True)
                page = browser.new_page()
                try:
                    check_page(page)
                    return 0
                except (Error, PlaywrightTimeoutError, RuntimeError, TimeoutError) as exc:
                    print(f"Attempt {attempt} failed: {exc}", file=sys.stderr, flush=True)
                    try:
                        page.screenshot(path=str(ARTIFACT_DIR / f"failure-{attempt}.png"), full_page=True)
                    except Error as screenshot_error:
                        print(f"Could not capture screenshot: {screenshot_error}", file=sys.stderr)
                finally:
                    page.close()
                if attempt < MAX_ATTEMPTS:
                    time.sleep(5)
        finally:
            browser.close()
    print("Dashboard check failed after both attempts.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
