"""Turning voice notes into text with OpenAI Whisper.

The language is never forced: Whisper detects it, so French, English or a mix all work.
"""

import logging

import openai

log = logging.getLogger(__name__)

# Whisper costs about $0.006 per minute. A cap stops a long recording by mistake from
# costing much, and Telegram only lets bots download files up to 20 MB anyway.
MAX_SECONDS = 10 * 60


class VoiceError(Exception):
    """Transcription failed. `kind` picks the message shown to the user."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind


class Transcriber:
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.client = openai.AsyncOpenAI(api_key=api_key, timeout=60.0, max_retries=2)
        self.model = model

    async def transcribe(self, audio: bytes, filename: str = "voice.ogg") -> str:
        try:
            # The filename tells OpenAI the audio format (Telegram voice notes are .ogg).
            result = await self.client.audio.transcriptions.create(model=self.model, file=(filename, audio))
        except openai.AuthenticationError as error:
            raise VoiceError("auth", str(error)) from error
        except openai.RateLimitError as error:
            # OpenAI also answers "rate limited" when the account has no credit left.
            kind = "no_credit" if error.code == "insufficient_quota" else "busy"
            raise VoiceError(kind, str(error)) from error
        except openai.APIStatusError as error:
            kind = "busy" if error.status_code >= 500 else "other"
            raise VoiceError(kind, str(error)) from error
        except openai.APIConnectionError as error:  # includes timeouts
            raise VoiceError("network", str(error)) from error

        text = result.text.strip()
        if not text:
            raise VoiceError("empty")
        return text
