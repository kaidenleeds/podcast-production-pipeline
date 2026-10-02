from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .audio import (
    concat_audio,
    duration_seconds,
    make_mock_audio,
    make_silence,
    missing_tools,
    mix_music,
    normalize_audio,
    render_video,
)
from .elevenlabs import ElevenLabsNarrator
from .script import EpisodeScript, chunk_text, sanitize_narration

GAP_BETWEEN_CHUNKS = 0.20
GAP_BETWEEN_CHAPTERS = 0.70
AD_BREAK_SILENCE = 1.20


@dataclass(frozen=True)
class BuildOptions:
    output_dir: Path
    model_id: str = "eleven_multilingual_v2"
    voice_id: str = ""
    api_key: str = ""
    mock_tts: bool = False
    audio_only: bool = False
    background: Path | None = None
    music: Path | None = None
    music_volume: float = 0.10
    chunk_limit: int = 2_500
    preset: str = "medium"
    video_bitrate: str = "6M"


@dataclass(frozen=True)
class BuildResult:
    narration: Path
    metadata: Path
    final_audio: Path
    video: Path | None
    duration: float


class PipelineError(RuntimeError):
    pass


def build_episode(episode: EpisodeScript, options: BuildOptions) -> BuildResult:
    _validate(options)
    options.output_dir.mkdir(parents=True, exist_ok=True)

    narrator = None
    if not options.mock_tts:
        narrator = ElevenLabsNarrator(
            api_key=options.api_key,
            voice_id=options.voice_id or episode.metadata.voice,
            model_id=options.model_id,
        )

    timeline: list[Path] = []
    chapter_marks: list[tuple[str, float]] = []
    ad_marks: list[float] = []
    elapsed = 0.0
    sequence = 0
    previous_kind = ""

    with tempfile.TemporaryDirectory(prefix="podcast-pipeline-") as temp_name:
        temp_dir = Path(temp_name)

        def add(path: Path) -> None:
            nonlocal elapsed
            timeline.append(path)
            elapsed += duration_seconds(path)

        for block_index, block in enumerate(episode.blocks):
            if block.kind == "ad":
                silence = temp_dir / f"ad-{block_index:03d}.wav"
                ad_marks.append(elapsed)
                make_silence(silence, AD_BREAK_SILENCE)
                add(silence)
                previous_kind = "ad"
                continue

            if timeline and previous_kind != "ad":
                gap = temp_dir / f"chapter-gap-{block_index:03d}.wav"
                make_silence(gap, GAP_BETWEEN_CHAPTERS)
                add(gap)

            chapter_marks.append((block.name, elapsed))
            narration_text = sanitize_narration(block.text)
            chunks = chunk_text(narration_text, options.chunk_limit)

            for chunk_index, chunk in enumerate(chunks):
                sequence += 1
                if options.mock_tts:
                    canonical = temp_dir / f"chunk-{sequence:04d}.wav"
                    make_mock_audio(canonical, chunk)
                else:
                    compressed = temp_dir / f"chunk-{sequence:04d}.mp3"
                    canonical = temp_dir / f"chunk-{sequence:04d}.wav"
                    assert narrator is not None
                    narrator.synthesize(chunk, compressed)
                    normalize_audio(compressed, canonical)
                add(canonical)

                if chunk_index < len(chunks) - 1:
                    gap = temp_dir / f"chunk-gap-{sequence:04d}.wav"
                    make_silence(gap, GAP_BETWEEN_CHUNKS)
                    add(gap)
            previous_kind = "chapter"

        narration_path = options.output_dir / "narration.wav"
        concat_audio(timeline, narration_path, temp_dir / "concat.txt")

    total_duration = duration_seconds(narration_path)
    metadata_path = options.output_dir / "metadata.txt"
    write_metadata(metadata_path, episode, chapter_marks, ad_marks)

    final_audio = narration_path
    if options.music:
        final_audio = options.output_dir / "episode_audio.wav"
        mix_music(narration_path, options.music, final_audio, options.music_volume)

    video_path = None
    if options.background and not options.audio_only:
        video_path = options.output_dir / "episode_final.mp4"
        render_video(
            options.background,
            final_audio,
            video_path,
            preset=options.preset,
            video_bitrate=options.video_bitrate,
        )

    return BuildResult(
        narration=narration_path,
        metadata=metadata_path,
        final_audio=final_audio,
        video=video_path,
        duration=total_duration,
    )


def write_metadata(
    destination: Path,
    episode: EpisodeScript,
    chapter_marks: list[tuple[str, float]],
    ad_marks: list[float],
) -> None:
    lines = [
        episode.metadata.title,
        "",
        "DESCRIPTION",
        episode.metadata.description,
        "",
        "CHAPTERS",
    ]
    lines.extend(f"{format_timestamp(at)}  {name}" for name, at in chapter_marks)
    lines.extend(["", "AD BREAKS"])
    lines.extend(format_timestamp(at) for at in ad_marks)
    if not ad_marks:
        lines.append("None")
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def format_timestamp(seconds: float) -> str:
    rounded = max(0, round(seconds))
    hours, remainder = divmod(rounded, 3_600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _validate(options: BuildOptions) -> None:
    unavailable = missing_tools()
    if unavailable:
        raise PipelineError(
            f"Install these tools and add them to PATH: {', '.join(unavailable)}"
        )
    if not options.mock_tts and not options.api_key:
        raise PipelineError("ELEVENLABS_API_KEY is required for live narration.")
    if not options.mock_tts and not options.voice_id:
        raise PipelineError("A voice ID is required for live narration.")
    if not 0.0 <= options.music_volume <= 1.0:
        raise PipelineError("Music volume must be between 0 and 1.")
    if options.chunk_limit < 1:
        raise PipelineError("Chunk limit must be positive.")
    for label, path in (("background", options.background), ("music", options.music)):
        if path and not path.is_file():
            raise PipelineError(f"The {label} file does not exist: {path}")
