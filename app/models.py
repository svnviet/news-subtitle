from typing import List, Optional

from pydantic import BaseModel, Field


class SceneBounds(BaseModel):
    """One scene's narration text plus the audio window it occupies in the
    final concatenated narration track -- mirrors AudioTrack.segments on the
    Vimo-ai (TypeScript) side: scene_id, start_ms, end_ms are already
    authoritative there (measured from real TTS audio), this service never
    invents its own timing, only slices within these bounds.
    """

    scene_id: str
    narration: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class WordTiming(BaseModel):
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class SubtitleEvent(BaseModel):
    scene_id: str
    text: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class GenerateTrackRequest(BaseModel):
    scenes: List[SceneBounds]
    # Pre-computed global word timings (same time axis as scenes[].start_ms/
    # end_ms -- i.e. measured against the original un-padded narration
    # track). Omit to force the sentence-proportional fallback directly,
    # without needing an audio file at all -- this is what makes
    # /v1/subtitles/track unit-testable without a loaded Whisper model.
    word_timings: Optional[List[WordTiming]] = None
    # Leading offset in ms applied to every timestamp -- mirrors the
    # THUMBNAIL_FRAME_MS lead-in-frame offset in timeline.ts; this service
    # stays agnostic of *why* the offset exists, it just shifts output by it.
    offset_ms: int = 0
    # Max consecutive words grouped into one on-screen subtitle event when
    # real word timing is available. 1 = one word at a time (MPT-style
    # "spring" word-by-word look); higher values read calmer on screen.
    # Sentence-fallback mode (no word_timings) ignores this.
    max_words_per_event: int = Field(default=4, ge=1, le=20)


class TranscribeRequest(BaseModel):
    language: str = 'vi'


class TranscribeResponse(BaseModel):
    words: List[WordTiming]
    engine: str
    model: str


class GenerateTrackResponse(BaseModel):
    track: List[SubtitleEvent]
    # Which path actually produced the track -- lets the caller log/alert
    # when it silently fell back (e.g. transcription failed or wasn't asked
    # for), instead of the fallback being invisible.
    source: str  # "whisper_word_level" | "sentence_proportional"
    warning: Optional[str] = None


class RenderAssRequest(BaseModel):
    track: List[SubtitleEvent]
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class RenderAssResponse(BaseModel):
    ass: str
