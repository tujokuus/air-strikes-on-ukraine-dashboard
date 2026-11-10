import json
from unittest.mock import patch

import pytest

from src.check_source_changes import FILES, has_changed, latest_release_metadata
from src.release_data import latest_data_release


def test_change_detection_compares_to_approved_hashes():
    hashes = {FILES[0]: 'a' * 64, FILES[1]: 'b' * 64}
    previous = {'source_files': {name: {'sha256': value} for name, value in hashes.items()}}
    assert has_changed(hashes, None)
    assert not has_changed(hashes, previous)
    assert has_changed({**hashes, FILES[0]: 'c' * 64}, previous)
    with pytest.raises(KeyError):
        has_changed(hashes, {'source_files': {}})


def test_release_selection_paginates_and_uses_publication_time():
    older = {'tag_name': 'data-old', 'published_at': '2025-01-01T00:00:00Z'}
    newer = {'tag_name': 'data-new', 'published_at': '2025-02-01T00:00:00Z'}
    first_page = [older] + [{'tag_name': f'app-{i}'} for i in range(99)]
    with patch('src.release_data.API_URL', 'api'), patch('src.release_data._read_url', side_effect=lambda url: json.dumps(first_page if url == 'api' else [newer]).encode()):
        assert latest_data_release() == newer


def test_missing_approved_metadata_fails_closed():
    with patch('src.check_source_changes.latest_data_release', return_value={'assets': []}):
        with pytest.raises(StopIteration):
            latest_release_metadata()


def test_snapshot_mismatch_stops_before_build(tmp_path, monkeypatch):
    from src import build_release
    expected = {name: 'a' * 64 for name in FILES}
    monkeypatch.setattr('sys.argv', ['build_release', str(tmp_path), '--expected-hashes', json.dumps(expected)])
    with patch('src.build_release.download_data.main'), \
         patch('src.check_source_changes.source_hashes', return_value={name: 'b' * 64 for name in FILES}), \
         patch('src.build_release.build_candidate') as candidate:
        with pytest.raises(ValueError, match='changed between detection and validation'):
            build_release.main()
    candidate.assert_not_called()
