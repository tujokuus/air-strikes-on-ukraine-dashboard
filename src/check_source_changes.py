"""Download the source and compare it with the last approved release."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from unittest.mock import patch

from src import download_data, ingest
from src.release_data import _read_url, latest_data_release, sha256

FILES = (ingest.ATTACKS_FILENAME, ingest.WEAPON_REFERENCE_FILENAME)


def source_hashes(bronze: Path) -> dict[str, str]:
    return {name: sha256(bronze / name) for name in FILES}


def latest_release_metadata() -> dict | None:
    release = latest_data_release()
    if release is None:
        return None
    asset = next(a for a in release['assets'] if a['name'] == 'metadata.json')
    return json.loads(_read_url(asset['browser_download_url']))


def has_changed(current: dict[str, str], previous: dict | None) -> bool:
    if previous is None:
        return True
    files = previous['source_files']
    hashes = {name: files[name]['sha256'] for name in FILES}
    if any(not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v) for v in hashes.values()):
        raise ValueError('Previous release has invalid source hashes')
    return current != hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('workdir', type=Path)
    args = parser.parse_args()
    bronze = args.workdir.resolve() / 'bronze'
    with patch.object(download_data, 'BRONZE_DATA_DIR', bronze):
        download_data.main()
    hashes = source_hashes(bronze)
    changed = has_changed(hashes, latest_release_metadata())
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a', encoding='utf-8') as stream:
            stream.write(f'changed={str(changed).lower()}\n')
            stream.write(f'hashes={json.dumps(hashes, separators=(",", ":"))}\n')
    print('Source changed; candidate validation required.' if changed else 'Source unchanged; no release required.')


if __name__ == '__main__':
    main()
