import asyncio
from types import SimpleNamespace

import pytest

from majordome.voice import Transcriber, VoiceError


def fake_transcriber(text: str, scores=(-0.3,)) -> Transcriber:
    """A Transcriber whose OpenAI client returns `text` instead of calling the API."""
    transcriber = Transcriber(api_key="test")
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        segments = [SimpleNamespace(avg_logprob=score) for score in scores]
        return SimpleNamespace(text=text, segments=segments, duration=4.2)

    transcriber.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    transcriber.calls = calls
    return transcriber


def test_transcribe_strips_text_and_never_forces_language():
    transcriber = fake_transcriber("  J'ai pris mes compléments \n")
    transcript = asyncio.run(transcriber.transcribe(b"audio"))
    assert transcript.text == "J'ai pris mes compléments" and not transcript.uncertain and transcript.seconds == 4.2
    call = transcriber.calls[0]
    assert call["file"] == ("voice.ogg", b"audio")
    assert "language" not in call  # Whisper must detect French/English by itself


def test_silence_is_an_error():
    with pytest.raises(VoiceError) as error:
        asyncio.run(fake_transcriber("   ").transcribe(b"audio"))
    assert error.value.kind == "empty"


def test_low_confidence_is_flagged():
    transcript = asyncio.run(fake_transcriber("appeler Blanche", scores=(-0.2, -1.4)).transcribe(b"audio"))
    assert transcript.uncertain
