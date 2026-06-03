from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from voice_to_text.usage_db import UsageDB


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = UsageDB(tmp.name)
    yield db
    db.close()
    Path(tmp.name).unlink(missing_ok=True)


class TestUsageDB:
    def test_creates_db_and_table(self, db):
        row = db._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='transcription_sessions'"
        ).fetchone()
        assert row is not None

    def test_record_session_inserts_row(self, db):
        row_id = db.record_session(
            provider="groq",
            model="whisper-large-v3-turbo",
            language="en",
            recording_duration_seconds=30.0,
            api_response_time_seconds=2.5,
            word_count=45,
            character_count=210,
        )
        assert row_id > 0

        row = db._conn.execute(
            "SELECT * FROM transcription_sessions WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["provider"] == "groq"
        assert row["word_count"] == 45

    def test_query_stats_overall(self, db):
        db.record_session(provider="groq", word_count=10, character_count=50)
        db.record_session(provider="voxtral", word_count=20, character_count=100)

        results = db.query_stats(period="all")
        assert len(results) == 1
        assert results[0]["sessions"] == 2
        assert results[0]["total_words"] == 30

    def test_query_stats_by_day(self, db):
        db.record_session(
            provider="groq",
            timestamp="2026-06-01T10:00:00",
            word_count=10,
            character_count=50,
        )
        db.record_session(
            provider="groq",
            timestamp="2026-06-02T10:00:00",
            word_count=20,
            character_count=100,
        )

        results = db.query_stats(period="day")
        assert len(results) == 2

    def test_query_stats_since_until(self, db):
        db.record_session(
            provider="groq",
            timestamp="2026-06-01T10:00:00",
            word_count=10,
            character_count=50,
        )
        db.record_session(
            provider="groq",
            timestamp="2026-06-15T10:00:00",
            word_count=20,
            character_count=100,
        )

        results = db.query_stats(
            period="all", since="2026-06-10", until="2026-06-20"
        )
        assert len(results) == 1
        assert results[0]["total_words"] == 20

    def test_query_by_provider(self, db):
        db.record_session(provider="groq", word_count=10, character_count=50)
        db.record_session(provider="groq", word_count=20, character_count=100)
        db.record_session(provider="voxtral", word_count=5, character_count=25)

        results = db.query_by_provider()
        providers = {r["provider"]: r for r in results}
        assert providers["groq"]["sessions"] == 2
        assert providers["groq"]["total_words"] == 30
        assert providers["voxtral"]["sessions"] == 1

    def test_default_timestamp(self, db):
        row_id = db.record_session(provider="groq", word_count=1, character_count=5)
        row = db._conn.execute(
            "SELECT timestamp FROM transcription_sessions WHERE id = ?", (row_id,)
        ).fetchone()
        assert row["timestamp"] is not None
        assert "T" in row["timestamp"]
