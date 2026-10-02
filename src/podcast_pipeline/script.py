from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

HEADER_PATTERN = re.compile(r"^(TITLE|DESCRIPTION|VOICE):\s*(.*)$", re.IGNORECASE)
CHAPTER_PREFIX = "## CHAPTER:"
AD_BREAK = "[AD BREAK]"


@dataclass(frozen=True)
class EpisodeMetadata:
    title: str
    description: str = ""
    voice: str = ""


@dataclass(frozen=True)
class ScriptBlock:
    kind: str
    name: str = ""
    text: str = ""


@dataclass(frozen=True)
class EpisodeScript:
    metadata: EpisodeMetadata
    blocks: tuple[ScriptBlock, ...]

    @property
    def chapters(self) -> tuple[ScriptBlock, ...]:
        return tuple(block for block in self.blocks if block.kind == "chapter")

    @property
    def ad_break_count(self) -> int:
        return sum(block.kind == "ad" for block in self.blocks)

    @property
    def character_count(self) -> int:
        return sum(len(block.text) for block in self.chapters)


def parse_script(path: Path) -> EpisodeScript:
    if path.suffix.lower() not in {".md", ".txt"}:
        raise ValueError("Episode scripts must use the .md or .txt extension.")

    raw = path.read_text(encoding="utf-8-sig")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)

    metadata = {
        "title": path.stem.replace("_", " ").strip(),
        "description": "",
        "voice": "",
    }
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    header_open = True
    unnamed_segment = 0

    def start_chapter(name: str = "") -> dict[str, str]:
        nonlocal unnamed_segment
        unnamed_segment += 1
        chapter = {
            "kind": "chapter",
            "name": name.strip() or f"Segment {unnamed_segment}",
            "text": "",
        }
        blocks.append(chapter)
        return chapter

    for line in raw.splitlines():
        stripped = line.strip()

        if header_open:
            header_match = HEADER_PATTERN.match(stripped)
            if header_match:
                metadata[header_match.group(1).lower()] = header_match.group(2).strip()
                continue
            if stripped == "---":
                header_open = False
                continue
            if not stripped:
                continue
            header_open = False

        if stripped.startswith("//"):
            continue
        if stripped.upper().startswith(CHAPTER_PREFIX):
            current = start_chapter(stripped[len(CHAPTER_PREFIX) :])
            continue
        if stripped.upper() == AD_BREAK:
            blocks.append({"kind": "ad", "name": "", "text": ""})
            current = None
            continue
        if not stripped:
            if current is not None and current["text"]:
                current["text"] += "\n"
            continue
        if current is None:
            current = start_chapter("Episode" if not blocks else "")
        current["text"] += line + "\n"

    parsed_blocks = tuple(
        ScriptBlock(
            kind=block["kind"],
            name=block["name"],
            text=block["text"].strip(),
        )
        for block in blocks
        if block["kind"] == "ad" or block["text"].strip()
    )
    if not any(block.kind == "chapter" for block in parsed_blocks):
        raise ValueError("The script contains no narration.")

    return EpisodeScript(
        metadata=EpisodeMetadata(**metadata),
        blocks=parsed_blocks,
    )


def sanitize_narration(text: str) -> str:
    text = re.sub(r"\[\s*pause\s*\]", "…", text, flags=re.IGNORECASE)
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_text(text: str, limit: int = 2_500) -> list[str]:
    if limit < 1:
        raise ValueError("Chunk limit must be positive.")

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        pieces.extend(_split_to_limit(paragraph, limit))

    chunks: list[str] = []
    buffer = ""
    for piece in pieces:
        candidate = f"{buffer}\n\n{piece}" if buffer else piece
        if len(candidate) <= limit:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)
    return chunks


def _split_to_limit(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    sentences = [
        part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()
    ]
    if len(sentences) > 1:
        result: list[str] = []
        buffer = ""
        for sentence in sentences:
            for piece in _split_to_limit(sentence, limit):
                candidate = f"{buffer} {piece}" if buffer else piece
                if len(candidate) <= limit:
                    buffer = candidate
                else:
                    if buffer:
                        result.append(buffer)
                    buffer = piece
        if buffer:
            result.append(buffer)
        return result

    words = text.split()
    if len(words) > 1:
        result = []
        buffer = ""
        for word in words:
            for piece in _split_to_limit(word, limit):
                candidate = f"{buffer} {piece}" if buffer else piece
                if len(candidate) <= limit:
                    buffer = candidate
                else:
                    if buffer:
                        result.append(buffer)
                    buffer = piece
        if buffer:
            result.append(buffer)
        return result

    return [text[index : index + limit] for index in range(0, len(text), limit)]
