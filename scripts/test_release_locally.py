"""Download fresh Kaggle data and run release checks locally without publishing."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from src.build_release import build_candidate
from src.ingest import ATTACKS_FILENAME, WEAPON_REFERENCE_FILENAME

ROOT = Path(__file__).resolve().parents[1]


def run_browser_check(database: Path, output: Path) -> None:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env['DASHBOARD_GOLD_DB'] = str(database)
    env['DASHBOARD_URL'] = f'http://127.0.0.1:{port}'
    env['CANDIDATE_ARTIFACT_DIR'] = str(output / 'screenshots')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
    with (output / 'streamlit.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(
            [sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.headless', 'true',
             '--server.address', '127.0.0.1', '--server.port', str(port)],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
        )
        try:
            opener = build_opener(ProxyHandler({}))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'Streamlit exited; see {output / "streamlit.log"}')
                try:
                    with opener.open(env['DASHBOARD_URL'] + '/_stcore/health', timeout=2) as response:
                        if response.status == 200:
                            if process.poll() is not None:
                                raise RuntimeError(f'Streamlit exited; see {output / "streamlit.log"}')
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.5)
            else:
                raise RuntimeError(f'Streamlit did not start; see {output / "streamlit.log"}')
            subprocess.run([sys.executable, 'monitoring/check_candidate.py'], cwd=ROOT,
                           env=env, check=True, creationflags=flags)
            if process.poll() is not None:
                raise RuntimeError(f'Streamlit exited during checks; see {output / "streamlit.log"}')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path,
                        help='Use an existing snapshot from this directory instead of downloading')
    parser.add_argument('--skip-browser', action='store_true', help='Skip Playwright page checks')
    args = parser.parse_args()
    source = args.data_dir.resolve() if args.data_dir else None
    if source:
        for name in (ATTACKS_FILENAME, WEAPON_REFERENCE_FILENAME):
            if not (source / name).is_file():
                parser.error(f'Missing source file: {source / name}')
    output_root = ROOT / '.local-data-tests'
    output_root.mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='run-', dir=output_root))
    print(f'Local test output: {output}', flush=True)
    subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=ROOT, check=True)
    if source:
        bronze = output / 'bronze'
        bronze.mkdir()
        for name in (ATTACKS_FILENAME, WEAPON_REFERENCE_FILENAME):
            shutil.copy2(source / name, bronze / name)
        print(f'Using local data snapshot: {source}', flush=True)
    else:
        print('Downloading the latest Kaggle dataset into the isolated test directory.', flush=True)
    database = build_candidate(output, download=source is None, compare_previous=False)
    if not args.skip_browser:
        run_browser_check(database, output)
    print(f'Local checks passed. Candidate and logs: {output}')
    print('No GitHub release was published; normal data directories were not modified.')


if __name__ == '__main__':
    main()
