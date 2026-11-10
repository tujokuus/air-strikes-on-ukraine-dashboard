"""Browser smoke test for all pages of the local candidate application."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    url = os.environ.get('DASHBOARD_URL', 'http://127.0.0.1:8501')
    artifacts = Path('candidate-artifacts')
    artifacts.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        executable = os.environ.get('PLAYWRIGHT_BROWSER_EXECUTABLE')
        browser = playwright.chromium.launch(**({'executable_path': executable} if executable else {}))
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        try:
            for route, heading in (('', 'Air Strikes in Ukraine Analytics'),
                                   ('Weapons', 'Weapons'), ('Areas', 'Areas'), ('Analysis', 'Analysis')):
                page.goto(f'{url}/{route}', wait_until='domcontentloaded', timeout=60000)
                page.get_by_role('heading', name=heading, exact=True).first.wait_for(timeout=120000)
                page.wait_for_timeout(3000)
                if page.get_by_test_id('stException').count() or page.get_by_test_id('stAlert').filter(has_text='Approved Gold database could not be loaded').count():
                    raise RuntimeError(f'Dashboard error on {heading}')
                page.screenshot(path=str(artifacts / f'{route or "overview"}.png'), full_page=True)
        except Exception:
            page.screenshot(path=str(artifacts / 'failure.png'), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == '__main__':
    main()
