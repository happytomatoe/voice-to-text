from __future__ import annotations

import json
from typing import Any

from voice_to_text.usage_db import UsageDB


def _fmt(val: Any, decimals: int = 2) -> str:
    if val is None:
        return "-"
    return f"{val:.{decimals}f}"


def _estimated_audio_hours(total_words: int | None) -> str:
    if not total_words:
        return "-"
    minutes = total_words / 150.0
    return f"{minutes / 60:.2f}"


def _provider_limits(provider: str) -> str:
    limits = {
        "groq": "2,000 req/day, 20 req/min",
        "voxtral": "1B tokens/mo, 2 req/min",
        "parakeet": "unlimited (local)",
    }
    return limits.get(provider, "unknown")


def show_stats(usage_db: UsageDB, args: Any) -> str:
    since = getattr(args, "since", None)
    until = getattr(args, "until", None)

    if getattr(args, "by_provider", False):
        rows = usage_db.query_by_provider(since=since, until=until)
        return _format_provider_table(rows, since, until)

    period = "all"
    if getattr(args, "daily", False):
        period = "day"
    elif getattr(args, "weekly", False):
        period = "week"
    elif getattr(args, "monthly", False):
        period = "month"

    rows = usage_db.query_stats(period=period, since=since, until=until)

    if getattr(args, "json", False):
        return json.dumps(rows, indent=2, default=str)

    return _format_stats_table(rows, period, since, until)


def _format_stats_table(
    rows: list[dict[str, Any]],
    period: str,
    since: str | None,
    until: str | None,
) -> str:
    lines: list[str] = []

    if not rows:
        return "No usage data found."

    if period == "all":
        r = rows[0]
        lines.append("Usage Summary")
        lines.append("=" * 60)
        lines.append(f"  Total sessions:          {r['sessions']}")
        lines.append(f"  Total words:             {r['total_words'] or 0}")
        lines.append(f"  Total characters:        {r['total_characters'] or 0}")
        lines.append(f"  Avg recording duration:  {_fmt(r['avg_recording_duration'])}s")
        lines.append(f"  Avg API response time:   {_fmt(r['avg_response_time'])}s")
        lines.append(f"  Avg words per session:   {_fmt(r['avg_word_count'])}")
        if r["total_words"]:
            lines.append(
                f"  Estimated audio hours:   {_estimated_audio_hours(r['total_words'])}h"
            )
    else:
        label = period.capitalize()
        header = f"{'Period':<20} {'Sessions':>10} {'Words':>10} {'Chars':>10} {'Avg Resp':>10} {'Audio Hrs':>12}"
        lines.append(f"Usage by {label}")
        lines.append("=" * len(header))
        lines.append(header)
        lines.append("-" * len(header))
        for r in rows:
            lines.append(
                f"{r['period']:<20} {r['sessions']:>10} {r['total_words'] or 0:>10} {r['total_characters'] or 0:>10} {_fmt(r['avg_response_time']):>10} {_estimated_audio_hours(r['total_words']):>12}"
            )

    if since or until:
        lines.append("")
        lines.append(f"  Period: {since or 'beginning'} to {until or 'now'}")

    return "\n".join(lines)


def _format_provider_table(
    rows: list[dict[str, Any]],
    since: str | None,
    until: str | None,
) -> str:
    lines: list[str] = []

    if not rows:
        return "No usage data found."

    header = f"{'Provider':<12} {'Sessions':>10} {'Words':>10} {'Chars':>10} {'Avg Resp':>10} {'Audio Hrs':>12}  Limits"
    lines.append("Usage by Provider")
    lines.append("=" * len(header))
    lines.append(header)
    lines.append("-" * len(header))
    for r in rows:
        lines.append(
            f"{r['provider']:<12} {r['sessions']:>10} {r['total_words'] or 0:>10} {r['total_characters'] or 0:>10} {_fmt(r['avg_response_time']):>10} {_estimated_audio_hours(r['total_words']):>12}  {_provider_limits(r['provider'])}"
        )

    if since or until:
        lines.append("")
        lines.append(f"  Period: {since or 'beginning'} to {until or 'now'}")

    return "\n".join(lines)
