"""Check persisted values and rebuilding the test database."""

import duckdb
import pandas as pd

from src.pipeline import main


def test_pipeline_persists_data_and_replaces_it_on_rebuild(isolated_data_dir):
    main()
    database = isolated_data_dir / "gold" / "gold.duckdb"

    with duckdb.connect(str(database), read_only=True) as connection:
        rows = connection.execute(
            "SELECT event_date, weapon_model, launched, destroyed "
            "FROM silver_attacks ORDER BY event_date"
        ).fetchall()
        totals = connection.execute(
            "SELECT total_launched, total_destroyed FROM vw_dashboard_overview"
        ).fetchone()
    assert rows == [
        ("2025-01-01", "Example UAV", 10, 8),
        ("2025-01-02", "Example missile", 4, 3),
    ]
    assert totals == (14, 11)

    source = isolated_data_dir / "bronze" / "missile_attacks_daily.csv"
    attacks = pd.read_csv(source)
    attacks.loc[0, "launched"] = 12
    attacks.to_csv(source, index=False)
    main()

    with duckdb.connect(str(database), read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM silver_attacks").fetchone()[0] == 2
        assert connection.execute(
            "SELECT total_launched, total_destroyed FROM vw_dashboard_overview"
        ).fetchone() == (16, 11)
