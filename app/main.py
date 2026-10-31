import json as json_lib
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.ass_renderer import render_ass
from app.auth import require_api_key
from app.models import (
    GenerateTrackRequest,
    GenerateTrackResponse,
    RenderAssRequest,
    RenderAssResponse,
    SceneBounds,
    TranscribeResponse,
)
from app.subtitle_track import build_subtitle_track
from app.whisper_timing import model_name, transcribe_word_timings

logger = logging.getLogger('subtitle-service')

app = FastAPI(title='Vimo-ai Subtitle Service', version='0.1.0')

# /health stays open (no API key) -- it's meant for infra liveness probes
# (Docker HEALTHCHECK, a process supervisor) that shouldn't need a secret
# just to ask "is the process up". Every actual capability lives under this
# router instead, which requires X-API-Key on every route.
v1 = APIRouter(prefix='/v1', dependencies=[Depends(require_api_key)])


@app.get('/health')
def health():
    return {'status': 'ok'}


@v1.post('/transcribe', response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...), language: str = Form('vi')):
    """Word-level transcription of an uploaded audio file. Low-level
    endpoint -- most callers want /v1/subtitles/generate instead, which
    transcribes AND builds the scene-aligned track (with automatic fallback)
    in one call."""
    suffix = Path(audio.filename or 'audio.wav').suffix or '.wav'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        words = transcribe_word_timings(tmp_path, language=language)
    except Exception as error:  # noqa: BLE001 -- surfaced as a 502, caller decides whether to fall back
        logger.warning('transcription failed: %s', error)
        raise HTTPException(status_code=502, detail=f'Transcription failed: {error}') from error
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return TranscribeResponse(words=words, engine='faster-whisper', model=model_name())


@v1.post('/subtitles/track', response_model=GenerateTrackResponse)
def subtitles_track(body: GenerateTrackRequest):
    """Pure track-building: given scenes (+ optional pre-computed word
    timings), decide subtitle event timing. No audio/model involved --
    this is what makes the sentence-proportional and word-grouping logic
    unit-testable without a loaded Whisper model."""
    track, source = build_subtitle_track(body.scenes, body.word_timings, body.offset_ms, body.max_words_per_event)
    return GenerateTrackResponse(track=track, source=source)


@v1.post('/subtitles/generate', response_model=GenerateTrackResponse)
async def subtitles_generate(
    audio: UploadFile = File(...),
    scenes: str = Form(..., description='JSON array of {scene_id, narration, start_ms, end_ms}'),
    offset_ms: int = Form(0),
    max_words_per_event: int = Form(4),
    language: str = Form('vi'),
):
    """Main entry point: transcribe the given narration audio and build a
    scene-aligned subtitle track from real word timing. Never hard-fails --
    if transcription errors or the model isn't installed, falls back to the
    sentence-proportional split and reports that in `source`/`warning`
    rather than failing the caller's pipeline stage over it (same
    best-effort posture as compositeThumbnail()/ThumbnailSelector.select()
    on the Vimo-ai side)."""
    try:
        parsed_scenes = [SceneBounds(**scene) for scene in json_lib.loads(scenes)]
    except (json_lib.JSONDecodeError, ValidationError, TypeError) as error:
        raise HTTPException(status_code=400, detail=f'Invalid scenes payload: {error}') from error

    suffix = Path(audio.filename or 'audio.wav').suffix or '.wav'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    warning = None
    word_timings = None
    try:
        word_timings = transcribe_word_timings(tmp_path, language=language)
        if not word_timings:
            warning = 'Transcription returned no words; falling back to sentence-proportional timing.'
    except Exception as error:  # noqa: BLE001 -- best-effort fallback, never fail the request over this
        logger.warning('transcription failed, falling back to sentence-proportional: %s', error)
        warning = f'Transcription failed ({error}); fell back to sentence-proportional timing.'
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    track, source = build_subtitle_track(parsed_scenes, word_timings, offset_ms, max_words_per_event)
    return GenerateTrackResponse(track=track, source=source, warning=warning)


@v1.post('/subtitles/ass', response_model=RenderAssResponse)
def subtitles_ass(body: RenderAssRequest):
    return RenderAssResponse(ass=render_ass(body.track, body.width, body.height))


app.include_router(v1)
