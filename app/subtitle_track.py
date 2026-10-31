"""Decide subtitle event timing for a scene's narration.

Two paths:
- sentence_proportional: ported 1:1 from timeline.ts's splitIntoSentences() +
  the proportional-by-character-count split that ran inline in
  buildTimeline() on the Vimo-ai (TypeScript) side. Same rounding/clamping,
  so switching a caller from the old inline TS logic to this service over
  REST produces byte-identical output for the no-word-timing case.
- whisper_word_level: new. Only taken when the caller supplies word_timings
  (see /v1/transcribe); groups consecutive words (same scene) into chunks of
  at most max_words_per_event.
"""
import re
from typing import List, Optional

from app.models import SceneBounds, SubtitleEvent, WordTiming

_SENTENCE_PATTERN = re.compile(r'[^.!?…]+[.!?…]*')


def split_into_sentences(text: str) -> List[str]:
    parts = _SENTENCE_PATTERN.findall(text) or [text]
    return [part.strip() for part in parts if part.strip()]


def _sentence_proportional_track(scenes: List[SceneBounds], offset_ms: int) -> List[SubtitleEvent]:
    events: List[SubtitleEvent] = []
    for scene in scenes:
        sentences = split_into_sentences(scene.narration)
        segment_duration = scene.end_ms - scene.start_ms
        total_chars = sum(len(s) for s in sentences) or 1
        cursor = scene.start_ms + offset_ms
        scene_end = scene.end_ms + offset_ms
        for index, sentence in enumerate(sentences):
            is_last = index == len(sentences) - 1
            if is_last:
                end = scene_end
            else:
                share = len(sentence) / total_chars
                proportional = cursor + round(segment_duration * share)
                remaining_sentences = len(sentences) - index - 1
                end = min(scene_end - remaining_sentences, max(cursor + 1, proportional))
            events.append(SubtitleEvent(scene_id=scene.scene_id, text=sentence, start_ms=cursor, end_ms=end))
            cursor = end
    return events


def _assign_words_to_scenes(words: List[WordTiming], scenes: List[SceneBounds]) -> dict:
    """Buckets each word under the scene whose [start_ms, end_ms) window
    contains it; a word that lands outside every window (Whisper/TTS timing
    drift) goes to whichever scene bound is nearest, so no word is silently
    dropped and every scene still gets a subtitle track."""
    by_scene: dict = {scene.scene_id: [] for scene in scenes}
    for word in words:
        containing = next((s for s in scenes if s.start_ms <= word.start_ms < s.end_ms), None)
        if containing is None:
            containing = min(scenes, key=lambda s: min(abs(word.start_ms - s.start_ms), abs(word.start_ms - s.end_ms)))
        by_scene[containing.scene_id].append(word)
    return by_scene


def _word_level_track(scenes: List[SceneBounds], words: List[WordTiming], offset_ms: int, max_words_per_event: int) -> List[SubtitleEvent]:
    by_scene = _assign_words_to_scenes(words, scenes)
    events: List[SubtitleEvent] = []
    for scene in scenes:
        scene_words = sorted(by_scene[scene.scene_id], key=lambda w: w.start_ms)
        if not scene_words:
            # No transcribed word landed in this scene's window (e.g. a very
            # short scene, or Whisper missed it) -- fall back to the whole
            # scene's narration as one event rather than leaving a silent gap.
            events.append(SubtitleEvent(scene_id=scene.scene_id, text=scene.narration, start_ms=scene.start_ms + offset_ms, end_ms=scene.end_ms + offset_ms))
            continue
        for i in range(0, len(scene_words), max_words_per_event):
            group = scene_words[i:i + max_words_per_event]
            events.append(SubtitleEvent(
                scene_id=scene.scene_id,
                text=' '.join(w.text for w in group),
                start_ms=group[0].start_ms + offset_ms,
                end_ms=group[-1].end_ms + offset_ms,
            ))
    return events


def build_subtitle_track(scenes: List[SceneBounds], word_timings: Optional[List[WordTiming]], offset_ms: int, max_words_per_event: int) -> tuple[List[SubtitleEvent], str]:
    """Returns (track, source) where source is "whisper_word_level" or
    "sentence_proportional" -- callers should log/surface this so a silent
    fallback (e.g. transcription came back empty) is never invisible."""
    if word_timings:
        return _word_level_track(scenes, word_timings, offset_ms, max_words_per_event), 'whisper_word_level'
    return _sentence_proportional_track(scenes, offset_ms), 'sentence_proportional'
