from __future__ import annotations

import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from podcast_pipeline.web import (
    DEFAULT_SCRIPT,
    PodcastUIHandler,
    inspect_script_text,
    render_page,
)


class WebUITests(unittest.TestCase):
    def test_inspects_script_text(self) -> None:
        episode, result = inspect_script_text(DEFAULT_SCRIPT)

        self.assertEqual(episode.metadata.title, "My episode")
        self.assertEqual(len(episode.chapters), 2)
        self.assertEqual(episode.ad_break_count, 1)
        self.assertEqual(result.title, "Script looks ready")

    def test_page_has_button_workflow(self) -> None:
        page = render_page()

        self.assertIn('data-testid="inspect-button"', page)
        self.assertIn('data-testid="build-button"', page)
        self.assertIn("Test voice", page)
        self.assertIn("ElevenLabs voice", page)

    def test_serves_page_health_check_and_inspection(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), PodcastUIHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base_url}/health", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'{"status":"ok"}')

            form = urlencode(
                {
                    "action": "inspect",
                    "script_text": DEFAULT_SCRIPT,
                    "voice_mode": "mock",
                    "audio_only": "1",
                    "music_volume": "0.10",
                }
            ).encode("utf-8")
            request = Request(f"{base_url}/run", data=form, method="POST")
            with urlopen(request, timeout=3) as response:
                page = response.read().decode("utf-8")
                self.assertIn("Script looks ready", page)
                self.assertIn("Chapters: 2", page)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
