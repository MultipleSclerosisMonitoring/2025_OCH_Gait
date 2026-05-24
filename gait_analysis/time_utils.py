from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo


class TimeProcessor:
    """Parses project datetimes and formats query timestamps for InfluxDB."""

    @staticmethod
    def to_utc_rfc3339_and_key(dt_str: str, tz_name: str) -> Tuple[str, str]:
        """Build a UTC RFC3339 timestamp and a local compact key.

        The CLI input is interpreted in the provided timezone and converted to UTC
        for InfluxDB queries. The compact key keeps the original local wall-clock
        time so file names remain stable and human-readable.

        Args:
            dt_str: Datetime string, e.g. "2025-07-01 15:59:14" (or with 'T').
            tz_name: Timezone name kept for interface compatibility.

        Returns:
            Tuple (rfc3339_str, local_key) where:
                - rfc3339_str: UTC timestamp string in RFC3339 format.
                - local_key: Compact local string YYYYMMDDTHHMMSS.
        """
        local_dt = TimeProcessor.to_local_datetime(dt_str, tz_name)
        utc_dt = local_dt.astimezone(ZoneInfo("UTC"))

        rfc3339_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        key_str = local_dt.strftime("%Y%m%dT%H%M%S")
        return rfc3339_str, key_str

    @staticmethod
    def to_local_datetime(dt_str: str, tz_name: str) -> datetime:
        """Parse local datetime string into timezone-aware datetime.

        Args:
            dt_str: Datetime string in '%Y-%m-%d %H:%M:%S' format.
            tz_name: IANA timezone name.

        Returns:
            Timezone-aware datetime in local timezone.
        """
        s = dt_str.strip().replace("T", " ")
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=ZoneInfo(tz_name))

    @staticmethod
    def to_utc_datetime(dt_str: str, tz_name: str) -> datetime:
        """Parse a local datetime string and convert it to UTC.

        Args:
            dt_str: Datetime string in '%Y-%m-%d %H:%M:%S' format.
            tz_name: IANA timezone name.

        Returns:
            Timezone-aware datetime in UTC.
        """
        return TimeProcessor.to_local_datetime(dt_str, tz_name).astimezone(
            ZoneInfo("UTC")
        )

    @staticmethod
    def generate_window_centers(
        start_dt: datetime,
        stop_dt: datetime,
        window_s: float,
        delta_t_s: float,
    ) -> List[datetime]:
        """Generate valid centered window times inside the gait interval.

        A center is valid only if the full analysis window is contained in the
        gait interval.

        Args:
            start_dt: Start of gait interval.
            stop_dt: End of gait interval.
            window_s: Duration of centered analysis window in seconds.
            delta_t_s: Step between consecutive centers in seconds.

        Returns:
            List of center times.
        """
        half = timedelta(seconds=window_s / 2.0)
        step = timedelta(seconds=delta_t_s)

        first_center = start_dt + half
        last_center = stop_dt - half

        centers: List[datetime] = []
        t = first_center
        while t <= last_center:
            centers.append(t)
            t += step

        return centers
