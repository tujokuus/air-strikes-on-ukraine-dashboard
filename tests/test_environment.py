"""A smoke test for the isolated test data and pipeline environment."""

import duckdb

from src.pipeline import main


def test_pipeline_runs_with_isolated_synthetic_data(isolated_data_dir):
    main()

    database = isolated_data_dir / "gold" / "gold.duckdb"
    assert database.is_file()
    with duckdb.connect(str(database), read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM silver_attacks").fetchone()[0] == 2
