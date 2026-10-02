from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import quote

import requests

API_ROOT = "https://api.elevenlabs.io/v1/text-to-speech"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class NarrationError(RuntimeError):
    pass


class ElevenLabsNarrator:
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str,
        retries: int = 4,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self.retries = retries
        self.session = session or requests.Session()

    def synthesize(self, text: str, destination: Path) -> None:
        url = f"{API_ROOT}/{quote(self.voice_id, safe='')}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.60,
                "similarity_boost": 0.80,
                "style": 0.30,
                "use_speaker_boost": True,
            },
        }

        for attempt in range(self.retries):
            try:
                response = self.session.post(
                    url,
                    params={"output_format": "mp3_44100_128"},
                    json=payload,
                    headers=headers,
                    timeout=300,
                )
            except requests.RequestException as error:
                if attempt == self.retries - 1:
                    raise NarrationError("Could not reach ElevenLabs.") from error
                time.sleep(2**attempt)
                continue

            if response.status_code == 200:
                destination.write_bytes(response.content)
                return
            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < self.retries - 1
            ):
                time.sleep(_retry_delay(response, attempt))
                continue
            raise NarrationError(f"ElevenLabs returned HTTP {response.status_code}.")

        raise NarrationError("ElevenLabs did not respond after several tries.")


def _retry_delay(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After", "")
    try:
        return min(float(retry_after), 30.0)
    except ValueError:
        return float(2**attempt)
