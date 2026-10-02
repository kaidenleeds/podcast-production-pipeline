from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from podcast_pipeline.pipeline import format_timestamp, write_metadata
from podcast_pipeline.script import EpisodeMetadata, EpisodeScript, ScriptBlock


class MetadataTests(unittest.TestCase):
    def test_formats_timestamp(self) -> None:
        self.assertEqual(format_timestamp(3_661.4), "01:01:01")

    def test_writes_chapters_and_ad_breaks(self) -> None:
        episode = EpisodeScript(
            metadata=EpisodeMetadata(title="Sample", description="Description"),
            blocks=(ScriptBlock(kind="chapter", name="Opening", text="Text"),),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "metadata.txt"
            write_metadata(destination, episode, [("Opening", 0.0)], [61.0])
            result = destination.read_text(encoding="utf-8")

        self.assertIn("00:00:00  Opening", result)
        self.assertIn("00:01:01", result)


if __name__ == "__main__":
    unittest.main()
