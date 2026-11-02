"""Load the raw CSVs without altering them.

Everything is read as text (all_varchar) so that bad values (non-numeric order values,
malformed dates, blanks) are visible to the quality checks instead of being silently
coerced by the CSV reader. Raw files are only ever opened read-only.
"""
import duckdb
import pandas as pd

from src.config import RAW_FILES


def load_raw() -> dict[str, pd.DataFrame]:
    """Return the three raw tables as all-string DataFrames. Blanks stay as '' (not NaN)."""
    return {
        name: pd.read_csv(path, dtype=str, keep_default_na=False)
        for name, path in RAW_FILES.items()
    }


def raw_connection() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with views `users`, `orders`, `spend` over the raw CSVs (all text).

    Empty strings are loaded as '' (not NULL) so blank detection is explicit.
    """
    con = duckdb.connect()
    for name, path in RAW_FILES.items():
        con.execute(
            f"CREATE VIEW {name} AS SELECT * FROM read_csv('{path.as_posix()}', "
            f"all_varchar=true, nullstr='__NO_NULLS__')"
        )
    return con


def load_cleaned() -> dict[str, pd.DataFrame]:
    """Read the cleaned CSVs from data/processed/ with proper types (used by notebook / analytics)."""
    from src.config import PROCESSED_DIR
    users = pd.read_csv(PROCESSED_DIR / "users_cleaned.csv", parse_dates=["signup_date"])
    orders = pd.read_csv(PROCESSED_DIR / "orders_cleaned.csv", parse_dates=["order_date"])
    spend = pd.read_csv(PROCESSED_DIR / "marketing_spend_cleaned.csv")
    return {"users": users, "orders": orders, "spend": spend}
