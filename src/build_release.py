"""Build and validate one isolated candidate release from a fresh Kaggle download."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd

from src import download_data, ingest, load, pipeline
from src.release_data import API_URL, _read_url, sha256
from src.transform import _snake_case


def validate_inputs(bronze: Path) -> dict:
    summary = {}
    for filename, required in ((ingest.ATTACKS_FILENAME, {'time_start', 'model', 'target', 'launched', 'destroyed'}),
                               (ingest.WEAPON_REFERENCE_FILENAME, {'model'})):
        path = bronze / filename
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        frame.columns = [_snake_case(c) for c in frame.columns]
        if frame.columns.duplicated().any():
            raise ValueError(f'{filename}: duplicate normalized columns')
        missing = required - set(frame.columns)
        if missing or frame.empty:
            raise ValueError(f'{filename}: missing columns {sorted(missing)} or empty data')
        if filename == ingest.ATTACKS_FILENAME:
            dates = pd.to_datetime(frame['time_start'], errors='coerce', format='mixed')
            if dates.isna().any():
                raise ValueError(f'{filename}: invalid or missing time_start ({dates.isna().sum()} rows)')
            for column in ('launched', 'destroyed'):
                values = frame[column].str.strip()
                invalid = values.ne('') & pd.to_numeric(values, errors='coerce').isna()
                if invalid.any():
                    raise ValueError(f'{filename}: invalid {column} ({invalid.sum()} rows)')
        summary[filename] = {'rows': len(frame), 'columns': list(frame.columns), 'sha256': sha256(path)}
        print(f'{filename}: {len(frame)} rows; columns: {list(frame.columns)}')
    return summary


def validate_gold(path: Path) -> None:
    # Execute every public dashboard query against exactly the candidate database.
    import dashboard.date_queries as queries
    with duckdb.connect(str(path), read_only=True) as connection:
        def query(sql, params=None):
            return connection.execute(sql, params or ()).df()
        start, end = connection.execute('SELECT min(event_date), max(event_date) FROM vw_dashboard_daily_activity').fetchone()
        if start is None or end is None:
            raise ValueError('Gold has no dated dashboard activity')
        with patch.object(queries, 'query', query):
            for name in dir(queries):
                if name.startswith('get_') and callable(getattr(queries, name)):
                    getattr(queries, name)(start, end)
                    print(f'Validated {name}')
        for name, in connection.execute("SELECT table_name FROM information_schema.views WHERE table_name LIKE 'vw_dashboard_%'").fetchall():
            connection.execute(f'SELECT * FROM "{name}" LIMIT 1').fetchall()


def report_changes(inputs: dict) -> None:
    """Compare with previous published metadata when available; never gate on revisions."""
    try:
        releases = json.loads(_read_url(API_URL))
        previous = next(r for r in releases if r.get('tag_name', '').startswith('data-')
                        and not r.get('draft') and not r.get('prerelease'))
        asset = next(a['browser_download_url'] for a in previous['assets'] if a['name'] == 'metadata.json')
        old = json.loads(_read_url(asset))['source_files']
        for name, current in inputs.items():
            if name in old:
                prior = old[name]
                print(f"{name}: rows {prior['rows']} -> {current['rows']}; "
                      f"added columns {sorted(set(current['columns']) - set(prior['columns']))}; "
                      f"removed columns {sorted(set(prior['columns']) - set(current['columns']))}")
    except Exception as exc:
        print(f'Previous release comparison unavailable: {type(exc).__name__}')


def build_candidate(root: Path, *, download: bool = True, compare_previous: bool = True) -> Path:
    """Build under root; local callers may supply existing files in root/bronze."""
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    bronze = root / 'bronze'
    with patch.object(download_data, 'BRONZE_DATA_DIR', bronze), \
         patch.object(ingest, 'BRONZE_DATA_DIR', bronze), \
         patch.object(load, 'SILVER_DATA_DIR', root / 'silver'), \
         patch.object(load, 'GOLD_DATA_DIR', root / 'gold'):
        if download:
            download_data.main()
        inputs = validate_inputs(bronze)
        if compare_previous:
            report_changes(inputs)
        pipeline.main()
    database = root / 'gold/gold.duckdb'
    validate_gold(database)
    digest = sha256(database)
    (root / 'gold.duckdb.sha256').write_text(f'{digest}  gold.duckdb\n', encoding='ascii')
    (root / 'metadata.json').write_text(json.dumps({
        'built_at': datetime.now(timezone.utc).isoformat(),
        'source_dataset': download_data.KAGGLE_DATASET,
        'source_files': inputs,
        'code_revision': os.environ.get('GITHUB_SHA', 'unknown'),
        'gold_sha256': digest,
    }, indent=2) + '\n', encoding='utf-8')
    return database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('workdir', type=Path)
    args = parser.parse_args()
    build_candidate(args.workdir)


if __name__ == '__main__':
    main()
