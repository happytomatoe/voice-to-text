from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class UsageDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transcription_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT,
                language TEXT,
                recording_duration_seconds REAL,
                api_response_time_seconds REAL,
                word_count INTEGER,
                character_count INTEGER
            )
            """
        )
        self._conn.commit()

    def record_session(self, **kwargs: Any) -> int:
        kwargs.setdefault("timestamp", datetime.now().astimezone().isoformat())
        kwargs.setdefault("model", None)
        kwargs.setdefault("language", None)
        kwargs.setdefault("recording_duration_seconds", None)
        kwargs.setdefault("api_response_time_seconds", None)
        kwargs.setdefault("word_count", 0)
        kwargs.setdefault("character_count", 0)
        cursor = self._conn.execute(
            """
            INSERT INTO transcription_sessions
                (timestamp, provider, model, language,
                 recording_duration_seconds, api_response_time_seconds,
                 word_count, character_count)
            VALUES
                (:timestamp, :provider, :model, :language,
                 :recording_duration_seconds, :api_response_time_seconds,
                 :word_count, :character_count)
            """,
            kwargs,
        )
        self._conn.commit()
        return cursor.lastrowid

    def query_stats(
        self,
        period: str = "all",
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clauses: list[str] = []
        params: dict[str, str] = {}

        if since:
            where_clauses.append("timestamp >= :since")
            params["since"] = since
        if until:
            where_clauses.append("timestamp <= :until")
            params["until"] = until

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        if period == "day":
            group_expr = "DATE(timestamp)"
        elif period == "week":
            group_expr = "DATE(timestamp, 'weekday 1', '-7 days')"
        elif period == "month":
            group_expr = "strftime('%Y-%m', timestamp)"
        else:
            group_expr = "'overall'"

        query = f"""
            SELECT
                {group_expr} AS period,
                COUNT(*) AS sessions,
                AVG(recording_duration_seconds) AS avg_recording_duration,
                AVG(api_response_time_seconds) AS avg_response_time,
                AVG(word_count) AS avg_word_count,
                SUM(word_count) AS total_words,
                SUM(character_count) AS total_characters
            FROM transcription_sessions
            WHERE {where_sql}
            GROUP BY period
            ORDER BY period
        """
        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def query_by_provider(
        self,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        where_clauses: list[str] = []
        params: dict[str, str] = {}

        if since:
            where_clauses.append("timestamp >= :since")
            params["since"] = since
        if until:
            where_clauses.append("timestamp <= :until")
            params["until"] = until

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT
                provider,
                COUNT(*) AS sessions,
                AVG(api_response_time_seconds) AS avg_response_time,
                SUM(word_count) AS total_words,
                SUM(character_count) AS total_characters,
                AVG(recording_duration_seconds) AS avg_recording_duration
            FROM transcription_sessions
            WHERE {where_sql}
            GROUP BY provider
            ORDER BY provider
        """
        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def close(self):
        self._conn.close()
