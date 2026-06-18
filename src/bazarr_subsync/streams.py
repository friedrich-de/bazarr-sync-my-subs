from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from bazarr_subsync.constants import (
    AUDIO_DISPOSITIONS_TO_AVOID,
    AUDIO_TAGS_TO_AVOID,
    SUBTITLE_DISPOSITIONS_TO_AVOID,
    TAGS_TO_IGNORE,
    TEXT_SUBTITLE_CODECS,
)

ENGLISH_CODES = {"en", "eng", "english"}


@dataclass(frozen=True)
class MediaStream:
    index: int
    codec_type: str
    codec_name: str
    tags: dict[str, str] = field(default_factory=dict[str, str])
    disposition: dict[str, int] = field(default_factory=dict[str, int])
    channels: int | None = None

    @classmethod
    def from_ffprobe(cls, raw: Mapping[str, object]) -> MediaStream:
        return cls(
            index=_int_value(raw.get("index"), -1),
            codec_type=_str_value(raw.get("codec_type")),
            codec_name=_str_value(raw.get("codec_name")),
            tags=_string_mapping(raw.get("tags")),
            disposition=_int_mapping(raw.get("disposition")),
            channels=_optional_int(raw.get("channels")),
        )

    @property
    def language(self) -> str:
        return self.tags.get("language", "").lower()

    @property
    def searchable_text(self) -> str:
        parts = [self.codec_name, self.language, *self.tags.values()]
        return " ".join(parts).lower()

    @property
    def is_english(self) -> bool:
        return self.language in ENGLISH_CODES or "english" in self.searchable_text


@dataclass(frozen=True)
class StreamSelection:
    stream: MediaStream
    reason: str


def _str_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int_value(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    return None


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(key).lower(): str(item) for key, item in mapping.items()}


def _int_mapping(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    mapping = cast(Mapping[object, object], value)
    return {str(key).lower(): int(item) for key, item in mapping.items() if isinstance(item, int | bool)}


def is_commentary_or_secondary_audio(stream: MediaStream) -> bool:
    text = stream.searchable_text
    has_avoided_tag = any(tag in text for tag in AUDIO_TAGS_TO_AVOID)
    has_avoided_disposition = any(
        stream.disposition.get(disposition, 0) == 1 for disposition in AUDIO_DISPOSITIONS_TO_AVOID
    )
    return has_avoided_tag or has_avoided_disposition


def select_audio_stream(streams: list[MediaStream]) -> StreamSelection | None:
    audio_streams = [stream for stream in streams if stream.codec_type == "audio"]
    if not audio_streams:
        return None
    if len(audio_streams) == 1:
        return StreamSelection(audio_streams[0], "only audio stream")

    english_primary = [
        stream for stream in audio_streams if stream.is_english and not is_commentary_or_secondary_audio(stream)
    ]
    if english_primary:
        return StreamSelection(english_primary[0], "first English primary audio stream")

    non_secondary = [stream for stream in audio_streams if not is_commentary_or_secondary_audio(stream)]
    if non_secondary:
        return StreamSelection(non_secondary[0], "first non-commentary audio fallback")

    english_any = [stream for stream in audio_streams if stream.is_english]
    if english_any:
        return StreamSelection(english_any[0], "first English audio stream; all audio appears secondary")

    return StreamSelection(audio_streams[0], "first usable audio fallback")


def _ignored_tag_matches(text: str) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for tag in TAGS_TO_IGNORE:
        tag_lower = tag.lower()
        if len(tag_lower) <= 2:
            if re.search(rf"(?:^|[\W_]){re.escape(tag_lower)}(?:$|[\W_])", lowered):
                matches.append(tag)
        elif tag_lower in lowered:
            matches.append(tag)
    return matches


def has_ignored_subtitle_tag(stream: MediaStream) -> bool:
    has_ignored_tag = bool(_ignored_tag_matches(stream.searchable_text))
    has_ignored_disposition = any(
        stream.disposition.get(disposition, 0) == 1 for disposition in SUBTITLE_DISPOSITIONS_TO_AVOID
    )
    return has_ignored_tag or has_ignored_disposition


def is_text_subtitle(stream: MediaStream) -> bool:
    return stream.codec_type == "subtitle" and stream.codec_name.lower() in TEXT_SUBTITLE_CODECS


def select_subtitle_stream(streams: list[MediaStream]) -> StreamSelection | None:
    subtitle_streams = [stream for stream in streams if is_text_subtitle(stream)]
    english_dialogue = [
        stream for stream in subtitle_streams if stream.is_english and not has_ignored_subtitle_tag(stream)
    ]
    if english_dialogue:
        return StreamSelection(english_dialogue[0], "first English dialogue subtitle stream")
    return None


def ignored_tags_in_text(text: str) -> list[str]:
    return _ignored_tag_matches(text)
