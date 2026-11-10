"""Download and verify an approved public GitHub data release."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen

REPOSITORY = 'tujokuus/air-strikes-on-ukraine-dashboard'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100'


def _read_url(url: str) -> bytes:
    request = Request(url, headers={'User-Agent': 'ukraine-dashboard', 'Accept': 'application/vnd.github+json'})
    with urlopen(request, timeout=60) as response:
        return response.read()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def latest_data_release() -> dict | None:
    """Find the latest published data release across all release pages."""
    releases = []
    page = 1
    while True:
        url = API_URL if page == 1 else f'{API_URL}&page={page}'
        data = json.loads(_read_url(url))
        if not isinstance(data, list):
            raise ValueError('Invalid releases response')
        releases.extend(r for r in data if r.get('tag_name', '').startswith('data-')
                        and not r.get('draft') and not r.get('prerelease'))
        if len(data) < 100:
            break
        page += 1
    return max(releases, key=lambda r: r.get('published_at') or '') if releases else None


def _cached_valid(path: Path) -> bool:
    try:
        expected = path.with_suffix('.sha256').read_text(encoding='ascii').strip()
        return bool(re.fullmatch(r'[0-9a-f]{64}', expected)) and sha256(path) == expected
    except OSError:
        return False


def install_latest_release(path: Path) -> str:
    """Install latest data release; fall back only to a checksum-verified prior download."""
    try:
        release = latest_data_release()
        if release is None:
            raise ValueError('No published data release exists')
        assets = {a['name']: a['browser_download_url'] for a in release['assets']}
        expected = _read_url(assets['gold.duckdb.sha256']).decode('ascii').split()[0].lower()
        if not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('Invalid release checksum')
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
                temporary = Path(target.name)
                target.write(_read_url(assets['gold.duckdb']))
            if sha256(temporary) != expected:
                raise ValueError('Release checksum mismatch')
            os.replace(temporary, path)
            path.with_suffix('.sha256').write_text(expected, encoding='ascii')
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return release['tag_name']
    except Exception as exc:
        if _cached_valid(path):
            return 'cached'
        raise RuntimeError('No verified approved data release is available') from exc
