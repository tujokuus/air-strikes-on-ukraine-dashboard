from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import test_release_locally as local


def test_default_local_test_downloads_to_new_isolated_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['test_release_locally', '--skip-browser'])
    with patch.object(local.subprocess, 'run') as run, patch.object(local, 'build_candidate') as build:
        local.main()
    output = build.call_args.args[0]
    assert output.parent == tmp_path / '.local-data-tests'
    assert build.call_args.kwargs == {'download': True, 'compare_previous': False}
    assert run.call_count == 1


def test_explicit_data_dir_uses_copy_without_download(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    for name in (local.ATTACKS_FILENAME, local.WEAPON_REFERENCE_FILENAME):
        (source / name).write_text('source contents', encoding='utf-8')
    monkeypatch.setattr(local, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['test_release_locally', '--data-dir', str(source), '--skip-browser'])
    with patch.object(local.subprocess, 'run'), patch.object(local, 'build_candidate') as build:
        local.main()
    output = build.call_args.args[0]
    assert build.call_args.kwargs == {'download': False, 'compare_previous': False}
    for name in (local.ATTACKS_FILENAME, local.WEAPON_REFERENCE_FILENAME):
        assert (output / 'bronze' / name).read_text(encoding='utf-8') == 'source contents'


def test_download_failure_stops_before_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'ROOT', tmp_path)
    monkeypatch.setattr('sys.argv', ['test_release_locally'])
    with patch.object(local.subprocess, 'run'), \
         patch.object(local, 'build_candidate', side_effect=RuntimeError('download failed')), \
         patch.object(local, 'run_browser_check') as browser:
        with pytest.raises(RuntimeError, match='download failed'):
            local.main()
    browser.assert_not_called()
