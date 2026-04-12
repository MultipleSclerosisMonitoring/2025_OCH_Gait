from __future__ import annotations

from typing import Iterable


class FluxQueryBuilder:
    """Builds Flux queries for IMU extraction."""

    @classmethod
    def build(
        cls,
        bucket: str,
        start_iso: str,
        stop_iso: str,
        ref_tag: str,
        reference: str,
        foot_tag: str,
        foot: str,
        fields: Iterable[str],
        pivot: bool = True,
    ) -> str:
        """Build a Flux query for a given foot and time range.

        Args:
            bucket: InfluxDB bucket.
            start_iso: UTC RFC3339 start time.
            stop_iso: UTC RFC3339 stop time.
            ref_tag: Tag key for reference.
            reference: Tag value for reference.
            foot_tag: Tag key for foot.
            foot: Tag value for foot.
            fields: Iterable of field names to keep.
            pivot: Whether to pivot to wide format.

        Returns:
            Flux query string.
        """
        field_filters = " or ".join([f'r["_field"] == "{f}"' for f in fields])

        query = f'''
from(bucket: "{bucket}")
  |> range(start: time(v: "{start_iso}"), stop: time(v: "{stop_iso}"))
  |> filter(fn: (r) => r["{ref_tag}"] == "{reference}")
  |> filter(fn: (r) => r["{foot_tag}"] == "{foot}")
  |> filter(fn: (r) => {field_filters})
'''
        if pivot:
            query += '  |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")\n'
        return query