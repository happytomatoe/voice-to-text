from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pytest

from voice_to_text.stats_reporter import show_stats
from voice_to_text.usage_db import UsageDB


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = UsageDB(tmp.name)
    _seed_data(db)
    yield db
    db.close()
    Path(tmp.name).unlink(missing_ok=True)


def _seed_data(db: UsageDB):
    db.record_session(
        provider="groq",
        model="whisper-large-v3-turbo",
        language="en",
        timestamp="2026-06-01T10:00:00",
        recording_duration_seconds=30.0,
        api_response_time_seconds=1.5,
        word_count=45,
        character_count=210,
    )
    db.record_session(
        provider="groq",
        model="whisper-large-v3-turbo",
        language="en",
        timestamp="2026-06-01T14:00:00",
        recording_duration_seconds=15.0,
        api_response_time_seconds=2.0,
        word_count=20,
        character_count=95,
    )
    db.record_session(
        provider="voxtral",
        model="voxtral-mini-latest",
        language="en",
        timestamp="2026-06-02T10:00:00",
        recording_duration_seconds=60.0,
        api_response_time_seconds=3.0,
        word_count=120,
        character_count=600,
    )


def _make_args(**kwargs) -> argparse.Namespace:
    defaults = dict(daily=False, weekly=False, monthly=False, by_provider=False, json=False, since=None, until=None)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestStatsReporter:
    def test_summary_output(self, db):
        result = show_stats(db, _make_args())
        assert "Usage Summary" in result
        assert "3" in result  # 3 total sessions
        assert "groq" not in result  # not provider breakdown

    def test_daily_output(self, db):
        result = show_stats(db, _make_args(daily=True))
        assert "Usage by Day" in result
        assert "2026-06-01" in result
        assert "2026-06-02" in result

    def test_weekly_output(self, db):
        result = show_stats(db, _make_args(weekly=True))
        assert "Usage by Week" in result

    def test_monthly_output(self, db):
        result = show_stats(db, _make_args(monthly=True))
        assert "Usage by Month" in result

    def test_by_provider_output(self, db):
        result = show_stats(db, _make_args(by_provider=True))
        assert "Usage by Provider" in result
        assert "groq" in result
        assert "voxtral" in result
        assert "2,000 req/day" in result  # groq limit shown

    def test_json_output(self, db):
        result = show_stats(db, _make_args(json=True))
        import json as json_mod
        data = json_mod.loads(result)
        assert isinstance(data, list)

    def test_since_filter(self, db):
        result = show_stats(db, _make_args(since="2026-06-02"))
        assert "2" in result  # only June 2 session

    def test_empty_db(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        empty_db = UsageDB(tmp.name)
        result = show_stats(empty_db, _make_args())
        assert "No usage data found" in result
        empty_db.close()
        Path(tmp.name).unlink(missing_ok=True)
