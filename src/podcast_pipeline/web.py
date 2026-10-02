from __future__ import annotations

import html
import mimetypes
import os
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from .pipeline import BuildOptions, PipelineError, build_episode, format_timestamp
from .script import EpisodeScript, parse_script

MAX_FORM_BYTES = 1_000_000
DEFAULT_SCRIPT = """TITLE: My episode
DESCRIPTION: A short description of the episode.
VOICE:
---
## CHAPTER: Opening
Paste your narration here.

[AD BREAK]

## CHAPTER: Second section
Continue the episode here.
"""


@dataclass(frozen=True)
class PageResult:
    kind: str
    title: str
    lines: tuple[str, ...]
    downloads: tuple[tuple[str, str], ...] = ()


DOWNLOADS: dict[str, Path] = {}


def inspect_script_text(script_text: str) -> tuple[EpisodeScript, PageResult]:
    episode = _parse_text(script_text)
    estimated_minutes = episode.character_count / 14.0 / 60.0
    result = PageResult(
        kind="success",
        title="Script looks ready",
        lines=(
            f"Title: {episode.metadata.title}",
            f"Chapters: {len(episode.chapters)}",
            f"Ad breaks: {episode.ad_break_count}",
            f"Characters to narrate: {episode.character_count}",
            f"Estimated length: {estimated_minutes:.1f} minutes",
        ),
    )
    return episode, result


def build_script_text(
    script_text: str,
    *,
    mock_tts: bool,
    audio_only: bool,
    music_path: str,
    background_path: str,
    music_volume: float,
) -> PageResult:
    episode = _parse_text(script_text)
    build_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
    output_dir = Path.cwd() / "out" / "ui" / build_id
    result = build_episode(
        episode,
        BuildOptions(
            output_dir=output_dir,
            api_key=os.environ.get("ELEVENLABS_API_KEY", ""),
            voice_id=os.environ.get("ELEVENLABS_VOICE_ID", "") or episode.metadata.voice,
            mock_tts=mock_tts,
            audio_only=audio_only,
            music=_optional_path(music_path),
            background=_optional_path(background_path),
            music_volume=music_volume,
        ),
    )

    files = [
        ("Narration WAV", result.narration),
        ("Episode notes", result.metadata),
    ]
    if result.final_audio != result.narration:
        files.append(("Mixed audio WAV", result.final_audio))
    if result.video:
        files.append(("Final video MP4", result.video))

    downloads: list[tuple[str, str]] = []
    for label, path in files:
        token = secrets.token_urlsafe(18)
        DOWNLOADS[token] = path.resolve()
        downloads.append((label, token))

    voice_label = "test tones" if mock_tts else "ElevenLabs narration"
    return PageResult(
        kind="success",
        title="Episode finished",
        lines=(
            f"Voice: {voice_label}",
            f"Duration: {format_timestamp(result.duration)}",
            f"Saved to: {output_dir}",
        ),
        downloads=tuple(downloads),
    )


def render_page(
    script_text: str = DEFAULT_SCRIPT,
    result: PageResult | None = None,
    form: dict[str, str] | None = None,
) -> str:
    values = form or {}
    mock_checked = values.get("voice_mode", "mock") == "mock"
    audio_checked = values.get("audio_only", "1") == "1"
    music_path = values.get("music_path", "")
    background_path = values.get("background_path", "")
    music_volume = values.get("music_volume", "0.10")

    result_html = ""
    if result:
        lines = "".join(f"<li>{html.escape(line)}</li>" for line in result.lines)
        links = "".join(
            f'<a class="download" href="/download/{html.escape(token)}">{html.escape(label)}</a>'
            for label, token in result.downloads
        )
        result_html = (
            f'<section class="result {html.escape(result.kind)}" aria-live="polite">'
            f"<h2>{html.escape(result.title)}</h2><ul>{lines}</ul>"
            f'<div class="downloads">{links}</div></section>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Podcast Production Pipeline</title>
  <style>
    :root {{ color-scheme: light; --ink:#152238; --muted:#5f6b7a; --line:#d8e0ea; --blue:#245da8; --navy:#132b4f; --pale:#f4f7fb; --good:#eaf7ee; --bad:#fff0f0; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font:16px/1.5 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); background:var(--pale); }}
    header {{ background:var(--navy); color:white; padding:42px 20px 38px; }}
    header div, main {{ width:min(960px,calc(100% - 32px)); margin:auto; }}
    h1 {{ margin:0 0 8px; font-size:clamp(28px,5vw,42px); line-height:1.1; }}
    header p {{ max-width:720px; margin:0; color:#d9e5f6; }}
    main {{ padding:28px 0 60px; }}
    .notice,.card,.result {{ background:white; border:1px solid var(--line); border-radius:14px; box-shadow:0 3px 12px rgba(19,43,79,.06); }}
    .notice {{ padding:16px 18px; margin-bottom:18px; }}
    .card {{ padding:22px; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
    label,legend {{ display:block; font-weight:700; margin-bottom:7px; }}
    textarea,input[type=text],input[type=number] {{ width:100%; border:1px solid #b8c4d2; border-radius:8px; padding:11px 12px; font:inherit; background:white; }}
    textarea {{ min-height:320px; resize:vertical; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:14px; }}
    fieldset {{ border:0; padding:0; margin:0 0 18px; }}
    .choice {{ display:flex; gap:10px; align-items:flex-start; margin:9px 0; font-weight:400; }}
    .choice input {{ margin-top:5px; }}
    .field {{ margin-bottom:16px; }}
    .help {{ margin:5px 0 0; color:var(--muted); font-size:13px; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }}
    button,.download {{ display:inline-block; border:0; border-radius:8px; padding:11px 16px; font:inherit; font-weight:750; cursor:pointer; text-decoration:none; }}
    button.primary,.download {{ background:var(--blue); color:white; }}
    button.secondary {{ background:#e6edf6; color:var(--navy); }}
    button:hover,.download:hover {{ filter:brightness(.94); }}
    .result {{ padding:20px 22px; margin-top:18px; }}
    .result.success {{ background:var(--good); border-color:#a9d8b6; }}
    .result.error {{ background:var(--bad); border-color:#e4b2b2; }}
    .result h2 {{ margin:0 0 8px; font-size:21px; }}
    .result ul {{ margin:0; padding-left:20px; }}
    .downloads {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:14px; }}
    details {{ margin-top:10px; }}
    summary {{ cursor:pointer; font-weight:700; }}
    @media (max-width:760px) {{ .grid {{ grid-template-columns:1fr; }} header {{ padding-top:32px; }} }}
  </style>
</head>
<body>
  <header><div><h1>Podcast Production Pipeline</h1><p>Paste a script, check it, and build the episode from one page.</p></div></header>
  <main>
    <section class="notice"><strong>Runs on this computer.</strong> Test voice stays local. Live narration sends the script text to ElevenLabs and may use paid credits.</section>
    <form class="card" method="post" action="/run">
      <div class="grid">
        <div>
          <label for="script_text">Episode script</label>
          <textarea id="script_text" name="script_text" required>{html.escape(script_text)}</textarea>
          <p class="help">Use the sample format, or paste plain text for one chapter.</p>
        </div>
        <div>
          <fieldset>
            <legend>Voice</legend>
            <label class="choice"><input type="radio" name="voice_mode" value="mock" {'checked' if mock_checked else ''}> <span><strong>Test voice</strong><br><span class="help">Free tones for checking the whole build.</span></span></label>
            <label class="choice"><input type="radio" name="voice_mode" value="live" {'checked' if not mock_checked else ''}> <span><strong>ElevenLabs voice</strong><br><span class="help">Uses the key and voice ID from your local .env file.</span></span></label>
          </fieldset>
          <label class="choice"><input type="checkbox" name="audio_only" value="1" {'checked' if audio_checked else ''}> <span><strong>Audio only</strong><br><span class="help">Turn this off when adding a background video.</span></span></label>
          <details>
            <summary>Optional music and video</summary>
            <div class="field"><label for="music_path">Music file path</label><input id="music_path" name="music_path" type="text" value="{html.escape(music_path)}" placeholder="C:\\Media\\music.mp3"></div>
            <div class="field"><label for="background_path">Background video path</label><input id="background_path" name="background_path" type="text" value="{html.escape(background_path)}" placeholder="C:\\Media\\background.mp4"></div>
            <div class="field"><label for="music_volume">Music volume</label><input id="music_volume" name="music_volume" type="number" min="0" max="1" step="0.01" value="{html.escape(music_volume)}"><p class="help">Use a value from 0 to 1. The default is 0.10.</p></div>
          </details>
          <div class="actions">
            <button class="secondary" data-testid="inspect-button" name="action" value="inspect">Inspect script</button>
            <button class="primary" data-testid="build-button" name="action" value="build">Build episode</button>
          </div>
        </div>
      </div>
    </form>
    {result_html}
  </main>
</body>
</html>"""


class PodcastUIHandler(BaseHTTPRequestHandler):
    server_version = "PodcastPipeline/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(render_page())
            return
        if parsed.path == "/health":
            self._send_bytes(b'{"status":"ok"}', "application/json", HTTPStatus.OK)
            return
        if parsed.path.startswith("/download/"):
            self._send_download(parsed.path.removeprefix("/download/"))
            return
        self._send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/run":
            self._send_bytes(b"Not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            length = 0
        if length < 1 or length > MAX_FORM_BYTES:
            self._send_html(
                render_page(result=PageResult("error", "Could not read the form", ("The submitted form was empty or too large.",))),
                HTTPStatus.BAD_REQUEST,
            )
            return

        form = {
            key: values[-1]
            for key, values in parse_qs(
                self.rfile.read(length).decode("utf-8"), keep_blank_values=True
            ).items()
        }
        script_text = form.get("script_text", "").strip()
        try:
            if form.get("action") == "inspect":
                _, result = inspect_script_text(script_text)
            elif form.get("action") == "build":
                result = build_script_text(
                    script_text,
                    mock_tts=form.get("voice_mode", "mock") == "mock",
                    audio_only=form.get("audio_only") == "1",
                    music_path=form.get("music_path", ""),
                    background_path=form.get("background_path", ""),
                    music_volume=float(form.get("music_volume", "0.10")),
                )
            else:
                raise ValueError("Choose Inspect script or Build episode.")
        except (OSError, ValueError, PipelineError, RuntimeError) as error:
            result = PageResult("error", "The episode was not built", (str(error),))
        self._send_html(render_page(script_text, result, form))

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"UI: {format_string % args}")

    def _send_download(self, token: str) -> None:
        path = DOWNLOADS.get(token)
        if not path or not path.is_file():
            self._send_bytes(b"File not found", "text/plain; charset=utf-8", HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                self.wfile.write(chunk)

    def _send_html(self, page: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(page.encode("utf-8"), "text/html; charset=utf-8", status)

    def _send_bytes(self, body: bytes, content_type: str, status: HTTPStatus) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def run_ui(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> int:
    server = ThreadingHTTPServer((host, port), PodcastUIHandler)
    url = f"http://{host}:{server.server_port}/"
    print(f"Podcast UI is running at {url}")
    print("Press Ctrl+C to stop it.")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPodcast UI stopped.")
    finally:
        server.server_close()
    return 0


def _parse_text(script_text: str) -> EpisodeScript:
    if not script_text.strip():
        raise ValueError("Paste an episode script first.")
    with TemporaryDirectory(prefix="podcast-ui-script-") as directory:
        path = Path(directory) / "episode.md"
        path.write_text(script_text, encoding="utf-8")
        return parse_script(path)


def _optional_path(value: str) -> Path | None:
    cleaned = value.strip().strip('"')
    return Path(cleaned).expanduser() if cleaned else None
