import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.build_release import validate_gold, validate_inputs
from src.pipeline import main
from src.release_data import install_latest_release


def test_candidate_gold_executes_dashboard_queries(isolated_data_dir):
    validate_inputs(isolated_data_dir / 'bronze')
    main()
    validate_gold(isolated_data_dir / 'gold/gold.duckdb')


@pytest.mark.parametrize('change', ['missing', 'empty', 'date', 'number'])
def test_invalid_source_is_rejected(isolated_data_dir, change):
    path = isolated_data_dir / 'bronze/missile_attacks_daily.csv'
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if change == 'missing':
        frame = frame.drop(columns=['model'])
    elif change == 'empty':
        frame = frame.iloc[:0]
    elif change == 'date':
        frame.loc[0, 'time_start'] = 'not a date'
    else:
        frame.loc[0, 'launched'] = 'not a number'
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        validate_inputs(isolated_data_dir / 'bronze')


def test_optional_columns_and_corrected_data_are_accepted(isolated_data_dir):
    path = isolated_data_dir / 'bronze/missile_attacks_daily.csv'
    frame = pd.read_csv(path, dtype=str, keep_default_na=False).drop(columns=['carrier'])
    frame.loc[0, 'launched'] = '23'
    frame.loc[0, 'model'] = 'New category'
    frame.to_csv(path, index=False)
    validate_inputs(isolated_data_dir / 'bronze')
    main()
    validate_gold(isolated_data_dir / 'gold/gold.duckdb')


def test_release_download_checksum_and_offline_fallback(tmp_path):
    content = b'verified database'
    digest = hashlib.sha256(content).hexdigest()
    release = [{'tag_name': 'data-001', 'draft': False, 'prerelease': False,
                'assets': [{'name': 'gold.duckdb', 'browser_download_url': 'db'},
                           {'name': 'gold.duckdb.sha256', 'browser_download_url': 'sum'}]}]
    responses = {'api': json.dumps(release).encode(), 'db': content, 'sum': digest.encode()}
    dest = tmp_path / 'gold.duckdb'
    with patch('src.release_data.API_URL', 'api'), patch('src.release_data._read_url', side_effect=lambda url: responses[url]):
        assert install_latest_release(dest) == 'data-001'
    assert dest.read_bytes() == content
    with patch('src.release_data._read_url', side_effect=OSError('offline')):
        assert install_latest_release(dest) == 'cached'
        dest.write_bytes(b'corrupt')
        with pytest.raises(RuntimeError):
            install_latest_release(dest)


def test_release_rejects_missing_asset_and_wrong_checksum(tmp_path):
    dest = tmp_path / 'gold.duckdb'
    release = [{'tag_name': 'data-1', 'assets': [{'name': 'gold.duckdb.sha256', 'browser_download_url': 'sum'},
                                                  {'name': 'gold.duckdb', 'browser_download_url': 'db'}]}]
    for responses in ({'api': json.dumps([{'tag_name': 'data-1', 'assets': []}]).encode()},
                      {'api': json.dumps(release).encode(), 'sum': b'0' * 64, 'db': b'wrong'}):
        with patch('src.release_data.API_URL', 'api'), patch('src.release_data._read_url', side_effect=lambda url: responses[url]):
            with pytest.raises(RuntimeError):
                install_latest_release(dest)
        assert not dest.exists()
