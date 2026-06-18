# bazarr-subsync

`bazarr-subsync` is a Bazarr custom post-processing command that synchronizes a downloaded subtitle in two ways:

- `episode.alass1.srt`: subtitle-to-subtitle synchronization against a usable embedded English subtitle track.
- `episode.alass2.srt`: audio-based synchronization against the selected episode audio track.

The original downloaded subtitle is never overwritten. Generated `.alass1` and `.alass2` files are replaced if they
already exist.

## Bazarr command

After downloading the release artifact, make it executable and configure Bazarr to call it as a custom
post-processing command:

```sh
/path/to/bazarr-subsync --episode "{{episode}}" --subtitles "{{subtitles}}"
```

Only `--episode` and `--subtitles` are required. The binary also accepts Bazarr metadata flags for compatibility, but
they are not needed for synchronization.

## Dependencies

Runtime system dependency:

- `ffmpeg` and `ffprobe` on `PATH`

Bundled dependency:

- `bin/alass`, included in the PyInstaller binary with `--add-binary "bin/alass:bin"`

The Linux GitHub Actions build runs in `manylinux2014_x86_64`, so the produced artifact targets the older glibc baseline
provided by that image.

## Behavior

Audio selection prefers the first English non-commentary track, avoids commentary/descriptive tracks when possible, and
falls back to the first usable audio stream.

Embedded subtitle selection uses the first English text subtitle that does not look like signs, captions, songs,
karaoke, OP, ED, opening, ending, or forced-only material. If no usable embedded subtitle exists, `.alass1` is skipped
and audio synchronization still runs.

Before synchronization, subtitles are cleaned with `pysubs2`: symbols, hearing-impaired text, furigana, initial bracket
labels, Netflix branding, and ASS signs/songs/karaoke/caption events are removed from temporary synchronization inputs.
Original subtitles are left untouched.

Logs are compact for Bazarr: startup, validation failures, selected streams, skip reasons, preprocessing statistics,
successful output paths, and concise failures. Normal `ffmpeg` and `alass` progress output is suppressed.

Exit behavior:

- `0` if at least one output file is produced.
- Non-zero if validation fails or no synchronization output succeeds.
- Subtitle-sync failure does not prevent audio-sync from running.

## Development

```sh
uv sync --dev
uv run ruff format
uv run ruff check --fix
uv run mypy
uv run pyright
uv run pytest
uv build
uv run pyinstaller --onefile --clean --name bazarr-subsync --paths src --add-binary "bin/alass:bin" src/bazarr_subsync/__main__.py
```

GitHub Actions builds and uploads the binary as the `bazarr-subsync-linux-x86_64` artifact.
