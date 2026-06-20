from __future__ import annotations

import stat
from pathlib import Path

from pytest import MonkeyPatch

from bazarr_subsync import sync


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_atomic_alass_copies_subtitle_permissions(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    source_subtitle = tmp_path / "episode.en.srt"
    source_subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    source_subtitle.chmod(0o644)
    output = tmp_path / "episode.en.alass1.srt"

    def fake_run_quiet(command: list[str]) -> None:
        Path(command[-1]).write_text("synced subtitle\n", encoding="utf-8")

    monkeypatch.setattr(sync, "run_quiet", fake_run_quiet)

    sync._atomic_alass(
        tmp_path / "alass", tmp_path / "reference.srt", tmp_path / "incorrect.srt", output, source_subtitle
    )

    assert output.read_text(encoding="utf-8") == "synced subtitle\n"
    assert _mode(output) == 0o644


def test_atomic_alass_replacement_uses_subtitle_permissions(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    source_subtitle = tmp_path / "episode.en.srt"
    source_subtitle.write_text("source\n", encoding="utf-8")
    source_subtitle.chmod(0o664)
    output = tmp_path / "episode.en.alass2.srt"
    output.write_text("old\n", encoding="utf-8")
    output.chmod(0o600)

    def fake_run_quiet(command: list[str]) -> None:
        Path(command[-1]).write_text("new\n", encoding="utf-8")

    monkeypatch.setattr(sync, "run_quiet", fake_run_quiet)

    sync._atomic_alass(
        tmp_path / "alass", tmp_path / "reference.wav", tmp_path / "incorrect.srt", output, source_subtitle
    )

    assert output.read_text(encoding="utf-8") == "new\n"
    assert _mode(output) == 0o664
