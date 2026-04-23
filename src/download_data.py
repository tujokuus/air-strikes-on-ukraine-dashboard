"""Download the Kaggle source dataset into the bronze data layer."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BRONZE_DATA_DIR = PROJECT_ROOT / "data" / "bronze"
KAGGLE_DATASET = "piterfm/massive-missile-attacks-on-ukraine"


def main() -> None:
    """Download and unzip the configured Kaggle dataset."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as exc:
        raise SystemExit(
            "The 'kaggle' package is not installed. Run 'poetry install' after "
            "updating dependencies, or install it with 'poetry add kaggle'."
        ) from exc
    except Exception as exc:
        raise SystemExit(
            "The Kaggle package could not initialize. Check your Kaggle credentials "
            "and config directory permissions. Do not commit Kaggle tokens to Git."
        ) from exc

    BRONZE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as exc:
        raise SystemExit(
            "Kaggle authentication failed. Create a Kaggle API token in your "
            "Kaggle account settings and configure it before running this script."
        ) from exc

    api.dataset_download_files(
        KAGGLE_DATASET,
        path=str(BRONZE_DATA_DIR),
        unzip=True,
        quiet=False,
        force=True,
    )

    print(f"Downloaded Kaggle dataset '{KAGGLE_DATASET}' to {BRONZE_DATA_DIR}")


if __name__ == "__main__":
    main()
