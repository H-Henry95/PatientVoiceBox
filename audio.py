"""Audio helpers.

Twilio Media Streams and the OpenAI Realtime API both speak G.711 mu-law
(`g711_ulaw`) at 8 kHz here, so we never have to resample mid-call. The only
decoding we do is mu-law -> linear PCM16, and that is purely so we can write a
listenable stereo recording at the end of the call.

We implement the mu-law decode in NumPy on purpose: Python's stdlib `audioop`
module was removed in 3.13, and depending on it would make the project fragile
across interpreter versions.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 8000  # Hz, both Twilio and our Realtime session use 8 kHz mu-law


def ulaw_to_pcm16(ulaw_bytes: bytes) -> np.ndarray:
    """Decode G.711 mu-law bytes into an int16 PCM NumPy array."""
    if not ulaw_bytes:
        return np.zeros(0, dtype=np.int16)
    u = np.frombuffer(ulaw_bytes, dtype=np.uint8).astype(np.int16)
    u = ~u & 0xFF
    sign = u & 0x80
    exponent = (u >> 4) & 0x07
    mantissa = u & 0x0F
    sample = ((mantissa << 3) + 0x84) << exponent
    sample = sample - 0x84
    sample = np.where(sign != 0, -sample, sample)
    return np.clip(sample, -32768, 32767).astype(np.int16)


class StereoRecorder:
    """Reconstructs a roughly time-aligned stereo recording of a call.

    Channel layout:
        left  = the clinic agent (audio Twilio sends us)
        right = our patient bot  (audio the Realtime model sends back)

    Chunks arrive ~20 ms at a time. We place each chunk at its wall-clock
    arrival offset and pad gaps with silence, so the two sides line up well
    enough to follow the conversation. It is intentionally simple rather than
    sample-perfect.
    """

    def __init__(self, start_time: float):
        self.start_time = start_time
        self._agent: list[tuple[float, np.ndarray]] = []
        self._bot: list[tuple[float, np.ndarray]] = []

    def add_agent(self, offset: float, ulaw_bytes: bytes) -> None:
        self._agent.append((offset, ulaw_to_pcm16(ulaw_bytes)))

    def add_bot(self, offset: float, ulaw_bytes: bytes) -> None:
        self._bot.append((offset, ulaw_to_pcm16(ulaw_bytes)))

    @staticmethod
    def _build_channel(chunks: list[tuple[float, np.ndarray]], total_samples: int) -> np.ndarray:
        track = np.zeros(total_samples, dtype=np.int16)
        for offset, pcm in chunks:
            start = int(offset * SAMPLE_RATE)
            end = min(start + len(pcm), total_samples)
            if end > start:
                track[start:end] = pcm[: end - start]
        return track

    def _total_samples(self) -> int:
        end = 0.0
        for offset, pcm in self._agent + self._bot:
            end = max(end, offset + len(pcm) / SAMPLE_RATE)
        return int(end * SAMPLE_RATE) + 1

    def write_wav(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        total = self._total_samples()
        left = self._build_channel(self._agent, total)
        right = self._build_channel(self._bot, total)
        stereo = np.stack([left, right], axis=1).reshape(-1)  # interleave L,R
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(stereo.tobytes())
        return path


def wav_to_mp3(wav_path: str | Path, mp3_path: str | Path) -> Path:
    """Convert WAV -> MP3 (requires ffmpeg). The brief requires ogg/mp3."""
    from pydub import AudioSegment

    mp3_path = Path(mp3_path)
    AudioSegment.from_wav(str(wav_path)).export(str(mp3_path), format="mp3")
    return mp3_path
