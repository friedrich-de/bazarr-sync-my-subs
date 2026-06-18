from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pysubs2

from bazarr_subsync.constants import (
    FURIGANA_REGEX,
    HEARING_IMPAIRED_REGEX,
    INITIAL_BRACKETS_REGEX,
    NETFLIX_REGEX,
    SYMBOLS_TO_DELETE,
)
from bazarr_subsync.streams import ignored_tags_in_text

ASS_OVERRIDE_REGEX = re.compile(r"\{[^}]*\}")


@dataclass
class RuleStats:
    modified: int = 0
    removed: int = 0


@dataclass
class PreprocessStats:
    total_events: int = 0
    output_events: int = 0
    rules: dict[str, RuleStats] = field(default_factory=dict[str, RuleStats])
    ass_removed_by_tag: Counter[str] = field(default_factory=lambda: Counter[str]())

    def ensure_rule(self, name: str) -> RuleStats:
        if name not in self.rules:
            self.rules[name] = RuleStats()
        return self.rules[name]

    def mark_modified(self, name: str) -> None:
        self.ensure_rule(name).modified += 1

    def mark_removed(self, name: str) -> None:
        self.ensure_rule(name).removed += 1

    def mark_removed_count(self, name: str, count: int) -> None:
        self.ensure_rule(name).removed += count


def clean_override_tags(text: str) -> str:
    return ASS_OVERRIDE_REGEX.sub("", text)


def _replace_pattern(text: str, pattern: str, replacement: str = "", *, flags: int = 0) -> tuple[str, bool]:
    updated = re.sub(pattern, replacement, text, flags=flags)
    return updated, updated != text


def clean_event_text(text: str, stats: PreprocessStats) -> str:
    updated = text
    symbols_changed = False
    for symbol in SYMBOLS_TO_DELETE:
        if symbol in updated:
            updated = updated.replace(symbol, "")
            symbols_changed = True
    if symbols_changed:
        stats.mark_modified("symbols")

    regex_rules = (
        ("hearing_impaired", HEARING_IMPAIRED_REGEX, 0),
        ("furigana", FURIGANA_REGEX, 0),
        ("initial_brackets", INITIAL_BRACKETS_REGEX, 0),
        ("netflix", NETFLIX_REGEX, re.IGNORECASE),
    )
    for name, pattern, flags in regex_rules:
        updated, changed = _replace_pattern(updated, pattern, flags=flags)
        if changed:
            stats.mark_modified(name)

    return updated.strip()


def _ignored_ass_tags(event: pysubs2.SSAEvent) -> list[str]:
    searchable = " ".join(
        part
        for part in (
            event.style,
            event.effect,
            clean_override_tags(event.text),
        )
        if part
    )
    return ignored_tags_in_text(searchable)


def preprocess_subtitle(input_path: Path, output_path: Path) -> PreprocessStats:
    subtitles = pysubs2.load(str(input_path))
    stats = PreprocessStats(total_events=len(subtitles.events))
    subtitles.remove_miscellaneous_events()
    stats.mark_removed_count("miscellaneous", stats.total_events - len(subtitles.events))
    cleaned_events: list[pysubs2.SSAEvent] = []

    for event in subtitles.events:
        ignored_tags = _ignored_ass_tags(event)
        if ignored_tags:
            for tag in ignored_tags:
                stats.ass_removed_by_tag[tag] += 1
            stats.mark_removed("ass_ignored_tag")
            continue

        updated = event.copy()
        updated.text = clean_event_text(updated.text, stats)
        if not clean_override_tags(updated.text).strip():
            stats.mark_removed("empty_after_cleanup")
            continue
        cleaned_events.append(updated)

    subtitles.events = cleaned_events
    stats.output_events = len(cleaned_events)
    subtitles.save(str(output_path))
    return stats
