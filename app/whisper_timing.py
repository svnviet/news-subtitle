"""Word-level transcription via faster-whisper (CTranslate2 backend -- no
torch dependency, far lighter than openai-whisper). The model is loaded once
and reused across requests; loading it per-request would dominate latency
for short narration clips.
"""
import os
from functools import lru_cache
from typing import List

from app.models import WordTiming

_DEFAULT_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'medium')
_DEFAULT_DEVICE = os.environ.get('WHISPER_DEVICE', 'cpu')
_DEFAULT_COMPUTE_TYPE = os.environ.get('WHISPER_COMPUTE_TYPE', 'int8')


@lru_cache(maxsize=1)
def _get_model():
    # Imported lazily so the rest of the service (track-building, ASS
    # rendering) stays importable/testable even before faster-whisper and
    # its model weights are installed on a given machine.
    from faster_whisper import WhisperModel
    return WhisperModel(_DEFAULT_MODEL_SIZE, device=_DEFAULT_DEVICE, compute_type=_DEFAULT_COMPUTE_TYPE)


def transcribe_word_timings(audio_path: str, language: str = 'vi') -> List[WordTiming]:
    model = _get_model()
    segments, _info = model.transcribe(audio_path, word_timestamps=True, language=language)
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
