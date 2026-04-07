from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from influxdb_client import InfluxDBClient

from gait_analysis.models import InfluxConfig


class InfluxService:
    """Service for querying InfluxDB."""

    def __init__(self, cfg: InfluxConfig) -> None:
        """Initialize InfluxDB client.

        Args:
            cfg: InfluxDB configuration.
        """
        self._client = InfluxDBClient(
            url=cfg.url,
            token=cfg.token,
            org=cfg.org,
            verify_ssl=cfg.verify_ssl,
        )
        self._query_api = self._client.query_api()

    def query(self, flux: str):
        """Execute a Flux query.

        Args:
            flux: Flux query string.

        Returns:
            Query result tables.
        """
        return self._query_api.query(flux)

    @staticmethod
    def count_records(tables) -> int:
        """Count total records in result tables.

        Args:
            tables: InfluxDB query result tables.

        Returns:
            Total record count.
        """
        return sum(len(t.records) for t in tables)

    @staticmethod
    def tables_to_dataframe(tables) -> pd.DataFrame:
        """Convert Influx tables to a pandas DataFrame.

        Args:
            tables: Query result tables from InfluxDB client.

        Returns:
            DataFrame with one row per timestamp and one column per selected field.
        """
        rows: List[Dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                values = dict(record.values)
                rows.append(values)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        preferred = ["_time"]
        preferred += [
            c for c in df.columns
            if c in {"Ax", "Ay", "Az", "Gx", "Gy", "Gz", "Mx", "My", "Mz", "S0", "S1", "S2"}
        ]
        if preferred:
            preferred_existing = [c for c in preferred if c in df.columns]
            if preferred_existing:
                df = df[preferred_existing]

        if "_time" in df.columns:
            df["_time"] = pd.to_datetime(df["_time"], utc=True)
            df = df.sort_values("_time").drop_duplicates(subset=["_time"]).reset_index(drop=True)

        return df