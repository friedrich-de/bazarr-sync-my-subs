from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pysubs2

from bazarr_subsync.ffmpeg import (
    CommandError,
    extract_audio_stream,
    extract_subtitle_stream,
    probe_streams,
    require_tool,
    run_quiet,
)
from bazarr_subsync.preprocess import PreprocessStats, preprocess_subtitle
from bazarr_subsync.streams import MediaStream, select_audio_stream, select_subtitle_stream

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncConfig:
    episode: Path
    subtitles: Path
    alass_path: Path | None = None


@dataclass(frozen=True)
class OutputPaths:
    subtitle_based: Path
    audio_based: Path


def output_paths(subtitles: Path) -> OutputPaths:
    suffix = subtitles.suffix
    stem = subtitles.with_suffix("")
    return OutputPaths(
        subtitle_based=stem.with_name(f"{stem.name}.alass1{suffix}"),
        audio_based=stem.with_name(f"{stem.name}.alass2{suffix}"),
    )


def bundled_alass_path() -> Path:
    meipass = vars(sys).get("_MEIPASS")
    if isinstance(meipass, str):
        return Path(meipass) / "bin" / "alass"
    return Path(__file__).resolve().parents[2] / "bin" / "alass"


def validate(config: SyncConfig) -> Path:
    if not config.episode.exists():
        raise FileNotFoundError(f"episode file does not exist: {config.episode}")
    if not config.subtitles.exists():
        raise FileNotFoundError(f"subtitle file does not exist: {config.subtitles}")
    require_tool("ffmpeg")
    require_tool("ffprobe")

    alass_path = config.alass_path or bundled_alass_path()
    if not alass_path.exists():
        raise FileNotFoundError(f"bundled alass executable not found: {alass_path}")
    if not os.access(alass_path, os.X_OK):
        raise PermissionError(f"bundled alass executable is not executable: {alass_path}")

    try:
        pysubs2.load(str(config.subtitles))
    except Exception as exc:
        raise ValueError(f"unsupported or unreadable subtitle file: {config.subtitles}") from exc
    return alass_path


def _log_preprocess_stats(label: str, stats: PreprocessStats) -> None:
    LOGGER.info(
        "%s preprocessing: %s input events, %s output events",
        label,
        stats.total_events,
        stats.output_events,
    )
    for rule_name, rule_stats in sorted(stats.rules.items()):
        LOGGER.info(
            "%s preprocessing rule %s: modified=%s removed=%s",
            label,
            rule_name,
            rule_stats.modified,
            rule_stats.removed,
        )
    for tag, count in sorted(stats.ass_removed_by_tag.items()):
        LOGGER.info("%s preprocessing ignored ASS tag/style %s removed %s events", label, tag, count)


def _atomic_alass(
    alass_path: Path, reference_path: Path, incorrect_path: Path, output_path: Path, permissions_source: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{output_path.stem}.",
        suffix=output_path.suffix,
        dir=output_path.parent,
        delete=False,
    ) as handle:
        temp_output = Path(handle.name)
    try:
        run_quiet([str(alass_path), str(reference_path), str(incorrect_path), str(temp_output)])
        shutil.copymode(permissions_source, temp_output)
        temp_output.replace(output_path)
    except Exception:
        temp_output.unlink(missing_ok=True)
        raise


def _preprocess_input(input_path: Path, working_dir: Path, label: str) -> Path:
    suffix = input_path.suffix or ".srt"
    output_path = working_dir / f"{label}.cleaned{suffix}"
    stats = preprocess_subtitle(input_path, output_path)
    _log_preprocess_stats(label, stats)
    return output_path


def _run_subtitle_sync(
    alass_path: Path,
    episode: Path,
    subtitles: Path,
    reference_stream: MediaStream,
    output_path: Path,
    working_dir: Path,
) -> bool:
    reference_raw = working_dir / "reference.extracted.srt"
    reference_clean = working_dir / "reference.cleaned.srt"
    try:
        incorrect_clean = _preprocess_input(subtitles, working_dir, "downloaded-subtitle-subtitle-sync")
        extract_subtitle_stream(episode, reference_stream, reference_raw)
        reference_stats = preprocess_subtitle(reference_raw, reference_clean)
        _log_preprocess_stats("embedded-reference-subtitle", reference_stats)
        _atomic_alass(alass_path, reference_clean, incorrect_clean, output_path, subtitles)
    except CommandError as exc:
        LOGGER.error("subtitle-based synchronization failed: %s", str(exc))
        return False
    except Exception as exc:
        LOGGER.error("subtitle-based synchronization failed: %s", str(exc))
        return False
    LOGGER.info("subtitle-based synchronization wrote %s", output_path)
    return True


def _run_audio_sync(
    alass_path: Path,
    episode: Path,
    subtitles: Path,
    audio_stream: MediaStream,
    output_path: Path,
    working_dir: Path,
) -> bool:
    audio_reference = working_dir / "reference-audio.wav"
    try:
        incorrect_clean = _preprocess_input(subtitles, working_dir, "downloaded-subtitle-audio-sync")
        extract_audio_stream(episode, audio_stream, audio_reference)
        _atomic_alass(alass_path, audio_reference, incorrect_clean, output_path, subtitles)
    except CommandError as exc:
        LOGGER.error("audio-based synchronization failed: %s", str(exc))
        return False
    except Exception as exc:
        LOGGER.error("audio-based synchronization failed: %s", str(exc))
        return False
    LOGGER.info("audio-based synchronization wrote %s", output_path)
    return True


def run_sync(config: SyncConfig) -> int:
    LOGGER.info("Starting Bazarr subtitle sync: episode=%s subtitles=%s", config.episode, config.subtitles)
    try:
        alass_path = validate(config)
    except Exception as exc:
        LOGGER.error("validation failed: %s", str(exc))
        return 2

    try:
        streams = probe_streams(config.episode)
    except Exception as exc:
        LOGGER.error("failed to inspect media streams: %s", str(exc))
        return 2

    selected_audio = select_audio_stream(streams)
    selected_subtitle = select_subtitle_stream(streams)
    paths = output_paths(config.subtitles)
    successes = 0

    if selected_subtitle is None:
        LOGGER.info("subtitle-based synchronization skipped: no embedded text subtitle found")
    else:
        LOGGER.info(
            "selected subtitle stream %s for subtitle-based synchronization: %s",
            selected_subtitle.stream.index,
            selected_subtitle.reason,
        )
        with tempfile.TemporaryDirectory(prefix="bazarr-subsync-") as temp_dir:
            if _run_subtitle_sync(
                alass_path,
                config.episode,
                config.subtitles,
                selected_subtitle.stream,
                paths.subtitle_based,
                Path(temp_dir),
            ):
                successes += 1

    if selected_audio is None:
        LOGGER.error("audio-based synchronization skipped: no usable audio stream found")
    else:
        LOGGER.info(
            "selected audio stream %s for audio-based synchronization: %s",
            selected_audio.stream.index,
            selected_audio.reason,
        )
        with tempfile.TemporaryDirectory(prefix="bazarr-subsync-") as temp_dir:
            if _run_audio_sync(
                alass_path,
                config.episode,
                config.subtitles,
                selected_audio.stream,
                paths.audio_based,
                Path(temp_dir),
            ):
                successes += 1

    if successes > 0:
        return 0
    LOGGER.error("no synchronization outputs were produced")
    return 1
