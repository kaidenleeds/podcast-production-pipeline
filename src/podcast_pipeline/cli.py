from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import __version__
from .pipeline import BuildOptions, PipelineError, build_episode, format_timestamp
from .script import parse_script

DEFAULT_MODEL = "eleven_multilingual_v2"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="podcast-pipeline",
        description="Turn an episode script into narrated audio and video.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("check", help="Check the required tools and settings.")

    ui_parser = subcommands.add_parser("ui", help="Open the local button-based interface.")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=8765)
    ui_parser.add_argument("--no-open", action="store_true")

    inspect_parser = subcommands.add_parser(
        "inspect", help="Read a script and show its length and chapter count."
    )
    inspect_parser.add_argument("script", type=Path)

    build_parser = subcommands.add_parser(
        "build", help="Create the episode audio and optional video."
    )
    build_parser.add_argument("script", type=Path)
    build_parser.add_argument("--output-dir", type=Path, default=Path("out"))
    build_parser.add_argument("--voice-id", default="")
    build_parser.add_argument("--model", default=DEFAULT_MODEL)
    build_parser.add_argument("--background", type=Path)
    build_parser.add_argument("--music", type=Path)
    build_parser.add_argument("--music-volume", type=float, default=0.10)
    build_parser.add_argument("--chunk-limit", type=int, default=2_500)
    build_parser.add_argument("--video-bitrate", default="6M")
    build_parser.add_argument(
        "--preset",
        default="medium",
        choices=("ultrafast", "veryfast", "faster", "fast", "medium", "slow", "slower"),
    )
    build_parser.add_argument("--mock-tts", action="store_true")
    build_parser.add_argument("--audio-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            return run_check()
        if args.command == "ui":
            from .web import run_ui

            return run_ui(args.host, args.port, open_browser=not args.no_open)
        if args.command == "inspect":
            return run_inspect(args.script)
        if args.command == "build":
            return run_build(args)
    except (OSError, ValueError, PipelineError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 2


def run_check() -> int:
    checks = {
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "ELEVENLABS_API_KEY": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "ELEVENLABS_VOICE_ID": bool(os.environ.get("ELEVENLABS_VOICE_ID")),
    }
    for name, available in checks.items():
        print(f"{name}: {'ready' if available else 'missing'}")
    return 0 if checks["ffmpeg"] and checks["ffprobe"] else 1


def run_inspect(script_path: Path) -> int:
    episode = parse_script(script_path)
    estimated_minutes = episode.character_count / 14.0 / 60.0
    print(f"Title: {episode.metadata.title}")
    print(f"Chapters: {len(episode.chapters)}")
    print(f"Ad breaks: {episode.ad_break_count}")
    print(f"Characters to narrate: {episode.character_count}")
    print(f"Estimated length: {estimated_minutes:.1f} minutes")
    return 0


def run_build(args: argparse.Namespace) -> int:
    episode = parse_script(args.script)
    voice_id = (
        args.voice_id
        or os.environ.get("ELEVENLABS_VOICE_ID", "")
        or episode.metadata.voice
    )
    options = BuildOptions(
        output_dir=args.output_dir,
        model_id=args.model,
        voice_id=voice_id,
        api_key=os.environ.get("ELEVENLABS_API_KEY", ""),
        mock_tts=args.mock_tts,
        audio_only=args.audio_only,
        background=args.background,
        music=args.music,
        music_volume=args.music_volume,
        chunk_limit=args.chunk_limit,
        preset=args.preset,
        video_bitrate=args.video_bitrate,
    )
    result = build_episode(episode, options)
    print(f"Duration: {format_timestamp(result.duration)}")
    print(f"Narration: {result.narration}")
    if result.final_audio != result.narration:
        print(f"Mixed audio: {result.final_audio}")
    if result.video:
        print(f"Video: {result.video}")
    print(f"Episode notes: {result.metadata}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
