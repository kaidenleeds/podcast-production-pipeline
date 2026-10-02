from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from podcast_pipeline.script import chunk_text, parse_script, sanitize_narration


class ScriptParsingTests(unittest.TestCase):
    def write_script(self, content: str, suffix: str = ".md") -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / f"episode{suffix}"
        path.write_text(content, encoding="utf-8")
        return path

    def test_parses_header_chapters_and_ad_break(self) -> None:
        path = self.write_script(
            "TITLE: Sample\n"
            "DESCRIPTION: Short test\n"
            "VOICE:\n"
            "---\n"
            "## CHAPTER: Open\n"
            "First line.\n"
            "[AD BREAK]\n"
            "## CHAPTER: Close\n"
            "Second line.\n"
            "// remove this\n"
        )

        episode = parse_script(path)

        self.assertEqual(episode.metadata.title, "Sample")
        self.assertEqual(
            [chapter.name for chapter in episode.chapters], ["Open", "Close"]
        )
        self.assertEqual(episode.ad_break_count, 1)
        self.assertNotIn("remove this", episode.chapters[-1].text)

    def test_plain_text_becomes_one_chapter(self) -> None:
        path = self.write_script("A plain episode script.", suffix=".txt")

        episode = parse_script(path)

        self.assertEqual(len(episode.chapters), 1)
        self.assertEqual(episode.chapters[0].name, "Episode")
        self.assertEqual(episode.chapters[0].text, "A plain episode script.")

    def test_empty_script_is_rejected(self) -> None:
        path = self.write_script("TITLE: Empty\n---\n")
        with self.assertRaisesRegex(ValueError, "no narration"):
            parse_script(path)


class TextPreparationTests(unittest.TestCase):
    def test_sanitize_narration_converts_pause_and_removes_cues(self) -> None:
        cleaned = sanitize_narration("Wait [pause] now. [REMOVE] Continue.")
        self.assertEqual(cleaned, "Wait … now. Continue.")

    def test_chunks_never_exceed_limit(self) -> None:
        text = "First sentence. " + ("word " * 40) + ("x" * 45)
        chunks = chunk_text(text, limit=32)
        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk) <= 32 for chunk in chunks))
        self.assertEqual("".join(chunks).replace(" ", ""), text.replace(" ", ""))

    def test_chunk_limit_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            chunk_text("text", limit=0)


if __name__ == "__main__":
    unittest.main()
