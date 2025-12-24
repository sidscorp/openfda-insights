"""
Usage Tracker - SQLite-based IP usage tracking and cost limiting.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "/var/lib/fda-agent/usage.db"
DEFAULT_LIMIT_USD = 1.50


@dataclass
class UsageStats:
    ip_address: str
    total_cost_usd: float
    limit_usd: float
    total_input_tokens: int
    total_output_tokens: int
    request_count: int
    first_request: Optional[str]
    last_request: Optional[str]


class UsageTracker:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("FDA_USAGE_DB", DEFAULT_DB_PATH)
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS usage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT NOT NULL,
                    session_id TEXT,
                    timestamp TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    model TEXT
                );

                CREATE TABLE IF NOT EXISTS ip_limits (
                    ip_address TEXT PRIMARY KEY,
                    limit_usd REAL NOT NULL DEFAULT 1.50,
                    extended_at TEXT,
                    extended_by TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_usage_ip ON usage_records(ip_address);
                CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_records(timestamp);
            """)
            conn.commit()
        finally:
            conn.close()

    def record_usage(
        self,
        ip_address: str,
        session_id: Optional[str],
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        model: Optional[str] = None
    ) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO usage_records (ip_address, session_id, timestamp, input_tokens, output_tokens, cost_usd, model)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ip_address, session_id, datetime.utcnow().isoformat(), input_tokens, output_tokens, cost_usd, model))
            conn.commit()
            logger.debug(f"Recorded usage: IP={ip_address}, cost=${cost_usd:.6f}")
        finally:
            conn.close()

    def get_ip_usage(self, ip_address: str) -> float:
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT COALESCE(SUM(cost_usd), 0.0) as total_cost
                FROM usage_records
                WHERE ip_address = ?
            """, (ip_address,)).fetchone()
            return row["total_cost"] if row else 0.0
        finally:
            conn.close()

    def get_ip_limit(self, ip_address: str) -> float:
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT limit_usd FROM ip_limits WHERE ip_address = ?
            """, (ip_address,)).fetchone()
            return row["limit_usd"] if row else DEFAULT_LIMIT_USD
        finally:
            conn.close()

    def check_limit(self, ip_address: str) -> Tuple[bool, float, float]:
        used = self.get_ip_usage(ip_address)
        limit = self.get_ip_limit(ip_address)
        allowed = used < limit
        return (allowed, used, limit)

    def extend_limit(self, ip_address: str, new_limit: float, extended_by: Optional[str] = None) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO ip_limits (ip_address, limit_usd, extended_at, extended_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ip_address) DO UPDATE SET
                    limit_usd = excluded.limit_usd,
                    extended_at = excluded.extended_at,
                    extended_by = excluded.extended_by
            """, (ip_address, new_limit, datetime.utcnow().isoformat(), extended_by))
            conn.commit()
            logger.info(f"Extended limit for {ip_address} to ${new_limit:.2f}")
        finally:
            conn.close()

    def get_stats(self, ip_address: str) -> UsageStats:
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT
                    COALESCE(SUM(cost_usd), 0.0) as total_cost,
                    COALESCE(SUM(input_tokens), 0) as total_input,
                    COALESCE(SUM(output_tokens), 0) as total_output,
                    COUNT(*) as request_count,
                    MIN(timestamp) as first_request,
                    MAX(timestamp) as last_request
                FROM usage_records
                WHERE ip_address = ?
            """, (ip_address,)).fetchone()

            limit = self.get_ip_limit(ip_address)

            return UsageStats(
                ip_address=ip_address,
                total_cost_usd=row["total_cost"] if row else 0.0,
                limit_usd=limit,
                total_input_tokens=row["total_input"] if row else 0,
                total_output_tokens=row["total_output"] if row else 0,
                request_count=row["request_count"] if row else 0,
                first_request=row["first_request"] if row else None,
                last_request=row["last_request"] if row else None,
            )
        finally:
            conn.close()


_tracker_instance: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = UsageTracker()
    return _tracker_instance
