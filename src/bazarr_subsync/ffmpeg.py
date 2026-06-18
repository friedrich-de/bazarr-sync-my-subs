from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from bazarr_subsync.streams import MediaStream

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandError(RuntimeError):
    def __init__(self, result: CommandResult) -> None:
        self.result = result
        detail = result.stderr.strip() or result.stdout.strip() or f"command exited {result.returncode}"
        super().__init__(detail)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f"required executable not found on PATH: {name}")


def run_quiet(args: list[str]) -> CommandResult:
    completed = subprocess.run(args, check=False, capture_output=True, text=True)
    result = CommandResult(args=args, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
    if result.returncode != 0:
        raise CommandError(result)
    return result


def probe_streams(media_path: Path) -> list[MediaStream]:
    args = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        str(media_path),
    ]
    result = run_quiet(args)
    data = cast(JsonObject, json.loads(result.stdout))
    streams = data.get("streams")
    if not isinstance(streams, list):
        return []
    return [MediaStream.from_ffprobe(raw) for raw in streams if isinstance(raw, dict)]


def extract_subtitle_stream(media_path: Path, stream: MediaStream, output_path: Path) -> None:
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media_path),
        "-map",
        f"0:{stream.index}",
        str(output_path),
    ]
    run_quiet(args)


def extract_audio_stream(media_path: Path, stream: MediaStream, output_path: Path) -> None:
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media_path),
        "-map",
        f"0:{stream.index}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-f",
        "wav",
        str(output_path),
    ]
    run_quiet(args)
