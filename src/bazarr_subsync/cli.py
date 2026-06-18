from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bazarr_subsync.log import configure_logging
from bazarr_subsync.sync import SyncConfig, run_sync


@dataclass(frozen=True)
class BazarrArguments:
    directory: str | None
    episode: Path
    episode_name: str | None
    subtitles: Path
    subtitles_language: str | None
    subtitles_language_code2: str | None
    subtitles_language_code2_dot: str | None
    subtitles_language_code3: str | None
    subtitles_language_code3_dot: str | None
    episode_language: str | None
    episode_language_code2: str | None
    episode_language_code3: str | None
    score: str | None
    subtitle_id: str | None
    provider: str | None
    uploader: str | None
    release_info: str | None
    series_id: str | None
    episode_id: str | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bazarr-subsync",
        description="Bazarr post-processing subtitle synchronizer using embedded subtitles and audio via alass.",
    )
    parser.add_argument("--directory")
    parser.add_argument("--episode", required=True, type=Path)
    parser.add_argument("--episode-name")
    parser.add_argument("--subtitles", required=True, type=Path)
    parser.add_argument("--subtitles-language")
    parser.add_argument("--subtitles-language-code2")
    parser.add_argument("--subtitles-language-code2-dot")
    parser.add_argument("--subtitles-language-code3")
    parser.add_argument("--subtitles-language-code3-dot")
    parser.add_argument("--episode-language")
    parser.add_argument("--episode-language-code2")
    parser.add_argument("--episode-language-code3")
    parser.add_argument("--score")
    parser.add_argument("--subtitle-id")
    parser.add_argument("--provider")
    parser.add_argument("--uploader")
    parser.add_argument("--release-info")
    parser.add_argument("--series-id")
    parser.add_argument("--episode-id")
    parser.add_argument("--alass-path", type=Path, help="Override bundled alass path, mainly for testing.")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    return parser


def parse_args(argv: Sequence[str] | None = None) -> tuple[BazarrArguments, Path | None, str]:
    namespace = build_parser().parse_args(argv)
    args = BazarrArguments(
        directory=namespace.directory,
        episode=namespace.episode,
        episode_name=namespace.episode_name,
        subtitles=namespace.subtitles,
        subtitles_language=namespace.subtitles_language,
        subtitles_language_code2=namespace.subtitles_language_code2,
        subtitles_language_code2_dot=namespace.subtitles_language_code2_dot,
        subtitles_language_code3=namespace.subtitles_language_code3,
        subtitles_language_code3_dot=namespace.subtitles_language_code3_dot,
        episode_language=namespace.episode_language,
        episode_language_code2=namespace.episode_language_code2,
        episode_language_code3=namespace.episode_language_code3,
        score=namespace.score,
        subtitle_id=namespace.subtitle_id,
        provider=namespace.provider,
        uploader=namespace.uploader,
        release_info=namespace.release_info,
        series_id=namespace.series_id,
        episode_id=namespace.episode_id,
    )
    return args, namespace.alass_path, namespace.log_level


def main(argv: Sequence[str] | None = None) -> None:
    args, alass_path, log_level = parse_args(argv)
    configure_logging(getattr(logging, log_level))
    exit_code = run_sync(SyncConfig(episode=args.episode, subtitles=args.subtitles, alass_path=alass_path))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main(sys.argv[1:])
