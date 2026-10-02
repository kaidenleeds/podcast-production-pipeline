# Podcast Production Pipeline

## What it does

This tool turns an episode script into narrated audio, optional background music, a looped 1080p video, and a text file with chapter and ad-break times. It includes a local button-based page and the original command-line controls.

For local testing, mock mode replaces the voice with generated tones. It never calls ElevenLabs or spends API credits.

## Button version

You need Python 3.10 or newer, FFmpeg, and FFprobe. The page runs only on your computer.

### Windows

1. Download or clone this repository.
2. Open the project folder.
3. Double-click `start-podcast-ui.bat`.
4. Wait for the first-time setup to finish. Your browser will open automatically.
5. Paste a script, click **Inspect script**, then click **Build episode**.

Test voice is selected by default. It creates free test tones and never contacts ElevenLabs. Finished files can be downloaded from the result box and are also saved under `out/ui/`.

### macOS

Open `start-podcast-ui.command`. If macOS blocks it the first time, right-click the file, choose **Open**, then confirm. The launcher creates the local environment, installs the project, and opens the page.

### What the buttons do

- **Inspect script** checks the title, chapters, ad breaks, character count, and estimated length.
- **Build episode** creates the narration and episode notes. It also creates mixed audio or video when those options are supplied.
- **Test voice** checks the whole workflow without an API key.
- **ElevenLabs voice** uses the key and voice ID stored in your local `.env` file.

## Command-line quick start

Install Python 3.10 or newer, FFmpeg, and FFprobe first. Make sure `ffmpeg -version` and `ffprobe -version` work in a new terminal.

Windows PowerShell:

```powershell
git clone https://github.com/kaidenleeds/podcast-production-pipeline.git
Set-Location podcast-production-pipeline
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m podcast_pipeline check
.\.venv\Scripts\python -m podcast_pipeline inspect examples/sample_episode.md
.\.venv\Scripts\python -m podcast_pipeline build examples/sample_episode.md --mock-tts --audio-only --output-dir out/smoke
```

macOS or Linux:

```bash
git clone https://github.com/kaidenleeds/podcast-production-pipeline.git
cd podcast-production-pipeline
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m podcast_pipeline check
.venv/bin/python -m podcast_pipeline inspect examples/sample_episode.md
.venv/bin/python -m podcast_pipeline build examples/sample_episode.md --mock-tts --audio-only --output-dir out/smoke
```

The mock build creates `narration.wav` and `metadata.txt` under `out/smoke`. Add an ElevenLabs key only when you want a real voice. Run `python -m podcast_pipeline ui` to open the button version from a terminal.

## How it works

```text
Episode script
  -> read the title, chapters, and ad-break markers
  -> remove production notes and split long text
  -> create the voice track or local test tones
  -> convert each audio clip to the same WAV format
  -> add chapter pauses and ad-break silence
  -> mix in music when supplied
  -> loop a background video when supplied
  -> write the chapter and ad-break times
```

Working audio files go in the system's temporary folder. The tool removes them when the build finishes.

## Supported media

- Scripts: UTF-8 Markdown or plain text
- Background video: anything your FFmpeg install can open, commonly MP4, MOV, MKV, and WebM
- Music: anything your FFmpeg install can open, commonly MP3, WAV, M4A, FLAC, OGG, and AAC
- Audio output: 44.1 kHz mono PCM WAV
- Video output: 1920x1080 H.264 video with AAC audio in an MP4 container

Git ignores media files, transcripts, caches, local settings, and finished output.

## Requirements

- Python 3.10 or newer
- FFmpeg and FFprobe on `PATH`
- An ElevenLabs API key and voice ID only for live narration

The default model is `eleven_multilingual_v2` because it handles long reads steadily. Pass `--model` to use another ElevenLabs model.

## Live narration setup

After the quick start, copy the example settings file.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS or Linux:

```bash
cp .env.example .env
```

Add your ElevenLabs key and voice ID to `.env`. Git ignores this file.

```dotenv
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
```

Check the setup again. The key fields should now report `ready`.

```powershell
.\.venv\Scripts\python -m podcast_pipeline check
```

```bash
.venv/bin/python -m podcast_pipeline check
```

You can skip this section when using `--mock-tts`.

## Script format

```markdown
TITLE: Episode title
DESCRIPTION: One-line episode description
VOICE:
---
## CHAPTER: Opening
Narration for the opening chapter.

[AD BREAK]

## CHAPTER: Second section
Narration continues here.

// This production note is removed before narration.
```

The script can use these markers:

- `TITLE:`, `DESCRIPTION:`, and `VOICE:` set the basic episode details
- `## CHAPTER:` starts a chapter and records its start time
- `[AD BREAK]` adds a short silence and records its time
- `//` at the start of a line marks a production note that will be ignored
- `[pause]` adds a spoken pause; other bracketed notes are removed

A plain `.txt` file with no markers is treated as a single chapter.

## Run commands

The examples below use `python`. If the virtual environment is not active, use `.\.venv\Scripts\python` on Windows or `.venv/bin/python` on macOS and Linux.

Check a script and estimate its length before spending credits:

```bash
python -m podcast_pipeline inspect examples/sample_episode.md
```

Test the full audio build with local tones:

```bash
python -m podcast_pipeline build examples/sample_episode.md --mock-tts --audio-only --output-dir out/smoke
```

Create the voice track with ElevenLabs:

```bash
python -m podcast_pipeline build examples/sample_episode.md --audio-only --output-dir out/episode
```

Create a video with a background clip and music:

```bash
python -m podcast_pipeline build path/to/episode.md --background path/to/background.mp4 --music path/to/music.mp3 --music-volume 0.10 --output-dir out/episode
```

Choose another model for one run:

```bash
python -m podcast_pipeline build path/to/episode.md --model eleven_v3 --audio-only --output-dir out/episode
```

Live narration sends the script text to ElevenLabs and can use paid credits. Run `inspect` first to see the character count. Mock mode stays on your computer.

## Output

Each build writes:

- `narration.wav`: voice track with chapter pauses and ad-break silence
- `metadata.txt`: title, description, chapter times, and ad-break times
- `episode_audio.wav`: narration plus music when `--music` is used
- `episode_final.mp4`: final video when `--background` is used

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests cover script reading, production notes, long text, timestamps, and the output text file.

## Project layout

```text
src/podcast_pipeline/
  audio.py       runs FFmpeg and FFprobe
  cli.py         reads commands and settings
  elevenlabs.py  requests the voice track
  pipeline.py    runs the build from start to finish
  script.py      reads the script and splits long text
  web.py         provides the local button-based page
examples/
  sample_episode.md
tests/
start-podcast-ui.bat      Windows launcher
start-podcast-ui.command  macOS launcher
```
