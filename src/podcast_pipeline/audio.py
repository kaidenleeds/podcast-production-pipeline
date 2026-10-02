from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

SAMPLE_RATE = 44_100


class MediaCommandError(RuntimeError):
    pass


def missing_tools() -> list[str]:
    return [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]


def run_media_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        summary = detail[-1] if detail else "No diagnostic output was returned."
        raise MediaCommandError(f"FFmpeg or FFprobe failed: {summary}")
    return completed


def duration_seconds(path: Path) -> float:
    completed = run_media_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(completed.stdout.strip())


def make_silence(path: Path, seconds: float) -> None:
    run_media_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=mono:sample_rate={SAMPLE_RATE}",
            "-t",
            f"{seconds:.3f}",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def make_mock_audio(path: Path, text: str) -> None:
    seconds = max(0.6, len(text) / 14.0)
    run_media_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=180:duration={seconds:.3f}:sample_rate={SAMPLE_RATE}",
            "-af",
            "volume=0.04",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def normalize_audio(source: Path, destination: Path) -> None:
    run_media_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
    )


def concat_audio(files: Sequence[Path], destination: Path, manifest: Path) -> None:
    if not files:
        raise ValueError("At least one audio file is required.")
    entries = [f"file '{_escape_concat_path(path)}'" for path in files]
    manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
    run_media_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
    )


def mix_music(narration: Path, music: Path, destination: Path, volume: float) -> None:
    run_media_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(narration),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-filter_complex",
            (
                f"[1:a]volume={volume:.3f}[bed];"
                "[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0[a]"
            ),
            "-map",
            "[a]",
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
    )


def render_video(
    background: Path,
    audio: Path,
    destination: Path,
    preset: str,
    video_bitrate: str,
) -> None:
    run_media_command(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background),
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-b:v",
            video_bitrate,
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )


def _escape_concat_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")
