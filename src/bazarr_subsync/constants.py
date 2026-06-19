from __future__ import annotations

SYMBOLS_TO_DELETE = {"\u266a", "\uff5e", "\u2015", "~", "♬", "＞", "＜", "➨"}
HEARING_IMPAIRED_REGEX = r"\uff08.+?\uff09"
FURIGANA_REGEX = r"\([ぁ-ゞ]+?\)"
INITIAL_BRACKETS_REGEX = r"^\(.+\)"
NETFLIX_REGEX = r"NETFLIX"

TAGS_TO_IGNORE = (
    "Signs",
    "Caption",
    "Song",
    "ED",
    "OP",
    "Opening",
    "Ending",
    "Karaoke",
)

AUDIO_TAGS_TO_AVOID = (
    "commentary",
    "comment",
    "director",
    "descriptive",
    "description",
    "audio description",
)

AUDIO_DISPOSITIONS_TO_AVOID = {
    "comment",
    "descriptions",
    "hearing_impaired",
    "visual_impaired",
}

SUBTITLE_DISPOSITIONS_TO_AVOID = {
    "captions",
    "forced",
    "hearing_impaired",
    "karaoke",
}

TEXT_SUBTITLE_CODECS = {
    "ass",
    "ssa",
    "subrip",
    "srt",
    "text",
    "mov_text",
    "webvtt",
}
