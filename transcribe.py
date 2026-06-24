"""Optional verification transcript built from the recorded audio.

The primary transcript is captured live from the Realtime session (see
server.py). This module re-transcribes the *recording* independently so you
can sanity-check the live transcript against the actual audio — useful when
you're documenting a bug and want to be sure of the exact wording.

It splits the stereo recording (left = agent, right = bot), transcribes each
channel separately (so speaker labels are certain, not guessed), and merges
the segments by timestamp.

Usage:
    python -m src.transcribe recordings/20260101-120000_weekend_trap.mp3
"""

from __future__ import annotations

import sys
from pathlib import Path

from openai import OpenAI
from pydub import AudioSegment

from .config import settings


def _transcribe_channel(path: Path) -> list[tuple[float, str]]:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    with open(path, "rb") as fh:
        result = client.audio.transcriptions.create(
            model=settings.TRANSCRIBE_MODEL,
            file=fh,
            response_format="verbose_json",
        )
    segments = getattr(result, "segments", None) or []
    return [(float(s.start), s.text.strip()) for s in segments if s.text.strip()]


def transcribe_recording(recording: str | Path) -> Path:
    recording = Path(recording)
    audio = AudioSegment.from_file(recording)
    if audio.channels != 2:
        raise ValueError("Expected a stereo recording (agent=L, bot=R).")

    left, right = audio.split_to_mono()
    tmp = recording.with_suffix(".left.wav")
    tmp2 = recording.with_suffix(".right.wav")
    left.export(tmp, format="wav")
    right.export(tmp2, format="wav")

    rows: list[tuple[float, str, str]] = []
    for ts, text in _transcribe_channel(tmp):
        rows.append((ts, "AGENT", text))
    for ts, text in _transcribe_channel(tmp2):
        rows.append((ts, "PATIENT_BOT", text))
    rows.sort(key=lambda r: r[0])

    tmp.unlink(missing_ok=True)
    tmp2.unlink(missing_ok=True)

    out = recording.with_name(recording.stem + ".verified.txt")
    lines = [f"# Verification transcript for {recording.name}", ""]
    for ts, speaker, text in rows:
        mm, ss = divmod(int(ts), 60)
        lines.append(f"[{mm:02d}:{ss:02d}] {speaker}: {text}")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m src.transcribe <recording.mp3|wav>")
        raise SystemExit(1)
    out = transcribe_recording(sys.argv[1])
    print(f"Wrote {out}")
