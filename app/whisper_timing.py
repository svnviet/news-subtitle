"""Word-level transcription via faster-whisper (CTranslate2 backend -- no
torch dependency, far lighter than openai-whisper). The model is loaded once
and reused across requests; loading it per-request would dominate latency
for short narration clips.
"""
import os
import subprocess
from functools import lru_cache
from typing import List

import numpy as np

from app.models import WordTiming

_DEFAULT_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'medium')
_DEFAULT_DEVICE = os.environ.get('WHISPER_DEVICE', 'cpu')
_DEFAULT_COMPUTE_TYPE = os.environ.get('WHISPER_COMPUTE_TYPE', 'int8')
_FFMPEG_BINARY = os.environ.get('FFMPEG_BINARY', 'ffmpeg')

# Whisper models expect 16kHz mono float32 PCM in [-1, 1].
_SAMPLE_RATE = 16000


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily so the rest of the service (track-building, ASS
    # rendering) stays importable/testable even before faster-whisper and
    # its model weights are installed on a given machine.
    from faster_whisper import WhisperModel
    return WhisperModel(_DEFAULT_MODEL_SIZE, device=_DEFAULT_DEVICE, compute_type=_DEFAULT_COMPUTE_TYPE)


def _decode_audio_ffmpeg(audio_path: str) -> np.ndarray:
    # faster-whisper's own decode_audio() shells out to PyAV's av.open(),
    # which on this machine's installed PyAV version (19.0.2) no longer
    # accepts the metadata_errors kwarg faster-whisper 1.2.1 calls it with
    # (TypeError: open() got an unexpected keyword argument 'metadata_errors')
    # -- a real version mismatch between the two packages, not fixable by
    # pinning an older PyAV here (no prebuilt wheel for this Python/Windows
    # combo without a full MSVC toolchain). Decoding via ffmpeg directly --
    # already a hard dependency of this whole project (same binary the main
    # Vimo-ai TS codebase shells out to) -- and handing faster-whisper a
    # plain numpy array instead of a file path skips PyAV's decode path
    # entirely, since WhisperModel.transcribe() accepts a pre-decoded array.
    process = subprocess.run(
        [_FFMPEG_BINARY, '-v', 'error', '-i', audio_path, '-f', 'f32le', '-ac', '1', '-ar', str(_SAMPLE_RATE), '-'],
        capture_output=True, check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f'ffmpeg failed to decode audio for transcription: {process.stderr.decode(errors="replace")}')
    return np.frombuffer(process.stdout, dtype=np.float32)


def transcribe_word_timings(audio_path: str, language: str = 'vi') -> List[WordTiming]:
    model = _get_model()
    audio_array = _decode_audio_ffmpeg(audio_path)
    segments, _info = model.transcribe(audio_array, word_timestamps=True, language=language)
    words: List[WordTiming] = []
    for segment in segments:
        for word in segment.words or []:
            # faster-whisper reports start/end in fractional seconds.
            words.append(WordTiming(
                text=word.word.strip(),
                start_ms=round(word.start * 1000),
                end_ms=round(word.end * 1000),
            ))
    return words


def model_name() -> str:
    return _DEFAULT_MODEL_SIZE
