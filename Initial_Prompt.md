# Goal

Create a single Bazarr post-processing binary that performs subtitle synchronization and writes multiple synchronized subtitle variants next to the original downloaded subtitle.

The binary will be used as a Bazarr custom post-processing command. Bazarr will call it with paths and metadata for the episode/movie and downloaded subtitle.

The binary must support both:

1. **Subtitle-based synchronization**, using an embedded reference subtitle track when available.
2. **Audio-based synchronization**, using the episode audio as the reference.

Given:

```text
episode1.mkv
episode1.srt
```

The tool should produce:

```text
episode1.alass1.srt  # subtitle-based synchronization
episode1.alass2.srt  # audio-based synchronization
```

The original subtitle file must not be overwritten.

---

# Bazarr Input Parameters

Bazarr can provide the following parameters. Implement the CLI so these values can be passed explicitly as command-line arguments.

```text
directory                       Full path of the episode file parent directory
episode                         Full path of the episode file
episode_name                    Filename of the episode without parent directory or extension
subtitles                       Full path of the subtitles file
subtitles_language              Language of the subtitles file, may include HI or forced
subtitles_language_code2        2-letter ISO-639 language code, may include :hi or :forced
subtitles_language_code2_dot    Same as previous, but with dot separator instead of colon
subtitles_language_code3        3-letter ISO-639 language code, may include :hi or :forced
subtitles_language_code3_dot    Same as previous, but with dot separator instead of colon
episode_language                Audio language of the episode file
episode_language_code2          2-letter ISO-639 language code of the episode audio language
episode_language_code3          3-letter ISO-639 language code of the episode audio language
score                           Score of the subtitle file
subtitle_id                     Provider ID of the subtitle file
provider                        Provider of the subtitle file
uploader                        Uploader of the subtitle file
release_info                    Release info for the subtitle file
series_id                       Sonarr series ID, empty if movie
episode_id                      Sonarr episode ID or Radarr movie ID
```

---

# Required Implementation

## Tooling

Use `uv` for project and dependency management:

* Initialize the project with `uv init` / `pyproject.toml`.
* Use `uv add` to manage dependencies.
* Use `uv run` to invoke scripts and tools.
* Use `uv build` for packaging.

Use `ruff` for linting and formatting:

* Add `ruff` as a dev dependency via `uv add --dev ruff`.
* Configure `ruff` in `pyproject.toml` under `[tool.ruff]`.
* Enable strict lint rules (e.g. `E`, `F`, `I`, `UP`, `B`, `C4`, `RUF`).
* Set `line-length = 120`.
* Run `ruff format` for code formatting (replaces `black`).
* Run `ruff check --fix` for linting.
* All source files must pass `ruff format --check` and `ruff check` with zero errors.

Use strong typing throughout:

* All functions and methods must have full type annotations.
* Use `from __future__ import annotations` in all source files.
* Use `strict = true` under `[tool.mypy]` (or equivalent via `pyright`).
* Use `pyright` or `mypy` as a dev dependency for type checking.
* All source files must pass type checking with zero errors.

Do not use `black`, `flake8`, `isort`, or `pylint` — `ruff` replaces them all.

---

## Runtime dependencies

Use:

* `pysubs2` for subtitle parsing, manipulation, and preprocessing.
* `ffmpeg` / `ffprobe` for media inspection, subtitle extraction, and audio extraction.
* `alass` for both subtitle-based and audio-based synchronization.
* A bundled `alass` binary located at:

```text
bin/alass
```

The final deliverable should be one distributable binary produced with `pyinstaller`.

When packaged, the binary must include the bundled `alass` executable and must be able to locate it at runtime.

---

# Build Requirements

Use GitHub Actions to build the binary.

The Linux build should use a 2014-based manylinux image so the produced binary has a low glibc requirement.

The build should produce a downloadable artifact containing the final Bazarr post-processing binary.

---

# Output Files

For an input subtitle:

```text
/path/to/episode1.srt
```

write synchronized outputs to the same directory:

```text
/path/to/episode1.alass1.srt
/path/to/episode1.alass2.srt
```

Where:

* `.alass1` is the subtitle-based synchronization result.
* `.alass2` is the audio-based synchronization result.

Preserve the original subtitle extension where possible. For example:

```text
episode1.ass  -> episode1.alass1.ass
episode1.ass  -> episode1.alass2.ass
```

Do not overwrite the original subtitle.

If an output file already exists, overwrite only the generated `.alass1` / `.alass2` file, not the original input subtitle.

---

# Processing Pipeline

## 1. Validate inputs

Validate that:

* The episode file exists.
* The downloaded subtitle file exists.
* `ffmpeg` and `ffprobe` are available.
* The bundled `alass` executable is available and executable.
* The subtitle format is supported by `pysubs2` and/or the synchronization pipeline.

If validation fails, log a clear error and exit non-zero.

---

## 2. Select reference audio track

Use `ffprobe` to inspect audio streams.

Selection logic:

1. Prefer the first embedded English audio track.
2. Avoid commentary tracks when possible.
3. Avoid tracks that appear to be non-primary audio, such as commentary, descriptive audio, or alternate-language dubs when a better English track exists.
4. If no desired English track is found, select the first usable audio track.
5. If the file contains only one audio track, select that track.

Use stream metadata such as:

* language
* title
* disposition
* codec
* channel count

Avoid tracks with titles containing words like:

```text
commentary
comment
director
descriptive
description
audio description
```

Matching should be case-insensitive.

Log the selected audio stream index and the reason it was selected.

---

## 3. Select reference subtitle track

Use `ffprobe` to inspect embedded subtitle streams.

Selection logic:

1. Prefer the first English subtitle track.
2. Avoid subtitle tracks that appear to be signs-only, songs-only, karaoke, forced-only, or captions-only.
3. Avoid tracks whose title contains ignored tags.
4. If no good English reference subtitle exists, skip subtitle-based synchronization and continue with audio-based synchronization.

Ignore embedded subtitle tracks whose metadata/title contains any of the following terms, case-insensitive:

```python
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
```

The ignore rule should match if the ASS style name, track title, or relevant tag contains one of these terms after lowercasing.

Log the selected subtitle stream index and the reason it was selected.

If no usable embedded reference subtitle is found, log that subtitle-based synchronization was skipped.

---

## 4. Extract reference material

### Audio reference

Extract/process the selected audio stream using `ffmpeg` into a temporary file suitable for `alass`.

The extraction should be robust and deterministic.

Clean up temporary files after processing.

### Subtitle reference

If a usable embedded reference subtitle stream exists, extract it using `ffmpeg` into a temporary subtitle file.

Then preprocess the extracted reference subtitle before using it for synchronization.

Clean up temporary files after processing.

---

# Subtitle Preprocessing

Preprocess both:

1. The downloaded subtitle.
2. The embedded reference subtitle, if available.

Use `pysubs2` where possible.

The goal is to remove symbols, hearing-impaired text, furigana, service branding, signs, songs, karaoke, and other non-dialogue content before synchronization.

The cleaned subtitle files should be temporary synchronization inputs. The original downloaded subtitle should remain unchanged.

---

## Initial filtering rules

Use the following initial filters:

```python
SYMBOLS_TO_DELETE = {"♪", "～", "―", "~"}

HEARING_IMPAIRED_REGEX = r"（.+?）"
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
```

Apply these rules case-insensitively where appropriate.

---

## Text cleanup

For each subtitle event/dialogue line:

* Remove symbols in `SYMBOLS_TO_DELETE`.
* Remove text matching `HEARING_IMPAIRED_REGEX`.
* Remove text matching `FURIGANA_REGEX`.
* Remove text matching `INITIAL_BRACKETS_REGEX`.
* Remove occurrences matching `NETFLIX_REGEX`.
* Strip leading/trailing whitespace after cleanup.
* Drop subtitle lines that become empty after cleanup.

Track how many events were modified or removed by each rule.

---

## ASS-specific cleanup

For ASS/SSA subtitles:

* Ignore/remove dialogue events whose style name contains any ignored tag from `TAGS_TO_IGNORE`.
* Ignore/remove dialogue events whose text or effect field indicates signs, songs, karaoke, OP, ED, opening, or ending material.
* Clean ASS override tags where they interfere with text matching.
* Remove or ignore sign/song/karaoke lines before synchronization.

Matching must be case-insensitive.

Track how many ASS events were removed because of ignored styles/tags.

---

# Synchronization

## Subtitle-based synchronization

If a usable embedded reference subtitle was selected and extracted:

1. Clean the downloaded subtitle into a temporary file.
2. Clean the embedded reference subtitle into a temporary file.
3. Run `alass` in subtitle-to-subtitle synchronization mode.
4. Write the result as:

```text
<original-subtitle-stem>.alass1.<original-extension>
```

Example:

```text
episode1.alass1.srt
```

Suppress normal `alass` progress output.

Only log:

* errors
* success/failure
* relevant selected stream information
* preprocessing statistics

If subtitle-based synchronization fails, log the error and continue to audio-based synchronization if possible.

---

## Audio-based synchronization

1. Select the reference audio track.
2. Extract/process the selected audio stream.
3. Clean the downloaded subtitle into a temporary file.
4. Run `alass` in audio-based synchronization mode.
5. Write the result as:

```text
<original-subtitle-stem>.alass2.<original-extension>
```

Example:

```text
episode1.alass2.srt
```

Suppress normal `alass` progress output.

Only log:

* errors
* success/failure
* selected audio stream information
* preprocessing statistics

If audio-based synchronization fails, log the error and exit non-zero unless subtitle-based synchronization succeeded.

---

# Logging Requirements

Bazarr logs should remain readable and not be flooded.

Do log:

* Startup summary with episode path and subtitle path.
* Validation errors.
* Selected audio stream and why it was selected.
* Selected reference subtitle stream and why it was selected.
* Whether subtitle-based synchronization was skipped.
* Each successful output file path.
* Each synchronization failure with a concise error.
* Preprocessing statistics:

  * how many events were modified by each cleanup rule
  * how many events were removed by each cleanup rule
  * which ASS styles/tags were ignored
  * how many subtitle events each ignored ASS style/tag removed

Do not log:

* `alass` progress reports.
* Full normal `alass` stdout.
* Repetitive ffmpeg progress output.
* Large dumps of subtitle text.

`alass` stdout/stderr should be captured. Only emit stderr or a concise failure summary if the command fails.

---

# Exit Codes

Use deterministic exit behavior:

* Exit `0` if at least one synchronization output was successfully produced.
* Exit non-zero if no synchronization output was produced.
* Exit non-zero on input validation failure.
* Exit non-zero on unexpected fatal errors.

---

# Error Handling

The tool should be resilient:

* If subtitle-based synchronization cannot run because no reference subtitle exists, continue to audio-based synchronization.
* If subtitle-based synchronization fails, log the failure and continue to audio-based synchronization.
* If audio-based synchronization fails but subtitle-based synchronization succeeded, exit `0`.
* Always clean up temporary files.
* Avoid leaving partial output files when synchronization fails.
* Write outputs atomically where practical, e.g. write to a temporary file and rename on success.

---

# Project Structure

Use a maintainable Python project structure, for example:

```text
.
├── bin/
│   └── alass
├── src/
│   └── bazarr_subsync/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── ffmpeg.py
│       ├── logging.py
│       ├── preprocess.py
│       ├── streams.py
│       └── sync.py
├── tests/
│   ├── test_preprocess.py
│   ├── test_stream_selection.py
│   └── test_output_paths.py
├── pyproject.toml
├── README.md
└── .github/
    └── workflows/
        └── build.yml
```

The exact structure can differ, but keep the code modular and testable.

---

# Tests

Add tests for at least:

## Subtitle preprocessing

* Symbol removal.
* Hearing-impaired text removal.
* Furigana removal.
* Initial bracket removal.
* Netflix branding removal.
* Empty subtitle removal after cleanup.
* ASS style/tag filtering.
* Preprocessing statistics.

## Output paths

Given:

```text
episode1.srt
```

verify:

```text
episode1.alass1.srt
episode1.alass2.srt
```

Given:

```text
episode1.ass
```

verify:

```text
episode1.alass1.ass
episode1.alass2.ass
```

## Stream selection

Test audio selection preference:

* English primary track preferred.
* Commentary avoided.
* Single audio track selected.
* First usable track selected as fallback.

Test subtitle selection preference:

* English subtitle preferred.
* signs/song/karaoke/caption tracks avoided.
* no usable subtitle causes subtitle-sync skip.

## Command execution

Mock `ffmpeg`, `ffprobe`, and `alass` calls.

Verify:

* `alass` progress output is not logged.
* errors are logged on failure.
* temp files are cleaned up.
* non-zero exit if no output succeeds.
* zero exit if at least one output succeeds.

---

# README Requirements

Document:

* What the tool does.
* How to configure it in Bazarr.
* Required Bazarr arguments.
* The required glibc version of the produced binary.
* Example Bazarr post-processing command.
* Required system dependency: `ffmpeg`.
* Bundled dependency: `alass`.
* Output file naming.
* Logging behavior.
* Exit behavior.
* Build instructions.
* GitHub Actions artifact location.

---

# Acceptance Criteria

The task is complete when:

1. A Bazarr-callable binary can be built with PyInstaller.
2. The binary can locate the bundled `bin/alass` at runtime.
3. The binary accepts all required Bazarr parameters as CLI arguments.
4. The binary writes `.alass1` and/or `.alass2` subtitle files next to the original subtitle.
5. The original subtitle is never overwritten.
6. Subtitle preprocessing is applied to both downloaded subtitles and embedded reference subtitles.
7. ASS signs/songs/karaoke/caption-style events are filtered before synchronization.
8. English primary audio is preferred, while commentary tracks are avoided.
9. English dialogue subtitle tracks are preferred, while signs/songs/karaoke/caption tracks are avoided.
10. Normal `alass` and `ffmpeg` progress output does not flood Bazarr logs.
11. Preprocessing statistics are logged.
12. The tool exits `0` if at least one synchronization output succeeds.
13. The tool exits non-zero if no synchronization output succeeds.
14. Tests cover preprocessing, stream selection, output paths, command execution, and exit behavior.
15. GitHub Actions builds the Linux binary on a 2014-based manylinux image.
16. All source files pass `ruff format --check` and `ruff check` with zero errors.
17. All source files pass type checking with zero errors (`pyright` or `mypy --strict`).
18. Project is managed with `uv` (`pyproject.toml`, `uv.lock`).
