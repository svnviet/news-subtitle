# subtitle-service

Standalone FastAPI service for subtitle timing + rendering. Separate deployable unit from the main
`server/` (NestJS) app — Vimo-ai calls this over REST, no shared process/code.

Replaces what would otherwise be duplicated subtitle-timing/ASS-rendering logic across
`renderer.ts`/`kenburns-renderer.ts`/`landscape-video-renderer.ts` on the Vimo-ai side (same
`assTime`/`assText`/`assHeader` block was copy-pasted in all three), plus adds real word-level subtitle
timing via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper transcription of the
already-synthesized narration audio) — the sentence-proportional split Vimo-ai uses today is kept here
as the automatic fallback when transcription isn't available or fails, so this service never needs to
hard-fail a caller's pipeline over it.

## Run locally

```bash
cd subtitle-service
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8100
```

## Test

```bash
pytest
```

`test_api.py`/`test_subtitle_track.py`/`test_ass_renderer.py` need no Whisper model or audio file —
they only exercise `/v1/subtitles/track` and `/v1/subtitles/ass`, which take plain JSON. Exercising
`/v1/transcribe` or `/v1/subtitles/generate` for real needs `faster-whisper` to download/load a model on
first call (`WHISPER_MODEL_SIZE`, default `medium`) and an actual audio file.

## Docker

```bash
docker build -t vimo-subtitle-service .
docker run -p 8100:8100 vimo-subtitle-service
```

## Auth

Every `/v1/*` route requires an `X-API-Key: <SUBTITLE_SERVICE_API_KEY>` header — 401 if missing or
wrong. `GET /health` is the one open route (infra liveness probes shouldn't need a secret). The process
**refuses to start** if `SUBTITLE_SERVICE_API_KEY` isn't set (`app/auth.py`) — there's no
"auth disabled" fallback. This is a private, same-host/trusted-network gate (Vimo-ai calling it over
localhost), not a general-purpose auth system — no users/roles, one shared key.

## API

All endpoints are under no version prefix except `/v1/...`; `GET /health` returns `{"status":"ok"}`.

### `POST /v1/subtitles/generate` — main entry point

`multipart/form-data`:
- `audio` (file, required) — the final concatenated narration audio (Vimo-ai: `AudioTrack.storageUri`).
- `scenes` (string, required) — JSON array of `{scene_id, narration, start_ms, end_ms}` (Vimo-ai:
  built from `scenes[]` + `AudioTrack.segments[]`, same bounds already used today).
- `offset_ms` (int, default `0`) — shifts every output timestamp (Vimo-ai: `THUMBNAIL_FRAME_MS` when a
  lead-in thumbnail frame is present, `0` otherwise).
- `max_words_per_event` (int, default `4`) — only used when transcription succeeds.
- `language` (string, default `vi`).

Response `200`:
```json
{
  "track": [{"scene_id": "scene_01", "text": "...", "start_ms": 0, "end_ms": 1200}],
  "source": "whisper_word_level",
  "warning": null
}
```

`source` is `"whisper_word_level"` or `"sentence_proportional"` — **always check this**, since a
fallback never surfaces as an HTTP error; `warning` carries why when it fell back.

### `POST /v1/transcribe` — low-level, word timings only

`multipart/form-data`: `audio` (file, required), `language` (string, default `vi`).
Response `200`: `{"words": [{"text","start_ms","end_ms"}], "engine": "faster-whisper", "model": "medium"}`.
Response `502` if transcription itself fails (no audio-less fallback at this layer — the caller of this
endpoint is expected to handle that, unlike `/v1/subtitles/generate` which does it for you).

### `POST /v1/subtitles/track` — pure track-building, no audio/model

JSON body: `GenerateTrackRequest` (see `app/models.py`) — same shape as `/v1/subtitles/generate`'s
`scenes`/`offset_ms`/`max_words_per_event`, plus optional `word_timings` (pre-computed, e.g. from a
prior `/v1/transcribe` call you want to reuse/cache). Omit `word_timings` to force the
sentence-proportional path directly. This is what the test suite exercises — no Whisper model needed.

### `POST /v1/subtitles/ass` — ASS file rendering

JSON body: `{"track": [...], "width": 1920, "height": 1080}` → `{"ass": "<file contents>"}`. Caller
(Vimo-ai) is responsible for storing the returned string wherever it stores other render artifacts
(`ArtifactStorage.put('timelines', 'ass', ...)` today) — this service is storage-agnostic, it only
builds the file content.

## Integrating with Vimo-ai (not yet wired up)

The NestJS side (`server/src/video/`) needs a small HTTP client calling `/v1/subtitles/generate` from
`runTimeline()` instead of `timeline.ts`'s inline `splitIntoSentences()`-based loop, and calling
`/v1/subtitles/ass` from `renderer.ts`/`kenburns-renderer.ts`/`landscape-video-renderer.ts` instead of
their duplicated `assTime`/`assText`/`assHeader` blocks. Deliberately not built yet — wiring details
(base URL/port, how this service is deployed/reached from the Windows host, timeout/retry policy)
depend on where this ends up deployed, which isn't decided yet.
