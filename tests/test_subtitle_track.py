from app.models import SceneBounds, WordTiming
from app.subtitle_track import build_subtitle_track, split_into_sentences


def test_split_into_sentences_keeps_terminator_and_trims():
    assert split_into_sentences('Xin chào. Hôm nay trời đẹp!') == ['Xin chào.', 'Hôm nay trời đẹp!']


def test_split_into_sentences_falls_back_to_whole_text_without_terminators():
    assert split_into_sentences('không có dấu câu nào cả') == ['không có dấu câu nào cả']


def test_sentence_proportional_fallback_when_no_word_timings():
    scenes = [SceneBounds(scene_id='scene_01', narration='Một câu ngắn. Một câu khác dài hơn nhiều.', start_ms=0, end_ms=10000)]
    track, source = build_subtitle_track(scenes, None, offset_ms=0, max_words_per_event=4)
    assert source == 'sentence_proportional'
    assert len(track) == 2
    assert track[0].scene_id == 'scene_01'
    assert track[0].start_ms == 0
    assert track[-1].end_ms == 10000
    # strictly ordered, non-overlapping
    for prev, cur in zip(track, track[1:]):
        assert cur.start_ms >= prev.end_ms


def test_sentence_proportional_applies_offset():
    scenes = [SceneBounds(scene_id='scene_01', narration='Chỉ một câu.', start_ms=0, end_ms=5000)]
    track, _source = build_subtitle_track(scenes, None, offset_ms=2000, max_words_per_event=4)
    assert track[0].start_ms == 2000
    assert track[0].end_ms == 7000


def test_word_level_groups_up_to_max_words_per_event():
    scenes = [SceneBounds(scene_id='scene_01', narration='ignored when word timings are present', start_ms=0, end_ms=4000)]
    words = [WordTiming(text=f'từ{i}', start_ms=i * 500, end_ms=i * 500 + 400) for i in range(8)]
    track, source = build_subtitle_track(scenes, words, offset_ms=0, max_words_per_event=3)
    assert source == 'whisper_word_level'
    assert [len(event.text.split()) for event in track] == [3, 3, 2]
    assert track[0].start_ms == 0
    assert track[-1].end_ms == words[-1].end_ms


def test_word_level_assigns_each_word_to_its_containing_scene():
    scenes = [
        SceneBounds(scene_id='scene_01', narration='...', start_ms=0, end_ms=1000),
        SceneBounds(scene_id='scene_02', narration='...', start_ms=1000, end_ms=2000),
    ]
    words = [
        WordTiming(text='a', start_ms=100, end_ms=400),
        WordTiming(text='b', start_ms=1200, end_ms=1500),
    ]
    track, _source = build_subtitle_track(scenes, words, offset_ms=0, max_words_per_event=4)
    by_scene = {event.scene_id: event.text for event in track}
    assert by_scene['scene_01'] == 'a'
    assert by_scene['scene_02'] == 'b'


def test_word_level_scene_with_no_words_falls_back_to_full_narration():
    scenes = [
        SceneBounds(scene_id='scene_01', narration='Có từ.', start_ms=0, end_ms=1000),
        SceneBounds(scene_id='scene_02', narration='Không từ nào rơi vào đây.', start_ms=1000, end_ms=2000),
    ]
    words = [WordTiming(text='a', start_ms=100, end_ms=400)]
    track, _source = build_subtitle_track(scenes, words, offset_ms=0, max_words_per_event=4)
    scene_02_events = [event for event in track if event.scene_id == 'scene_02']
    assert len(scene_02_events) == 1
    assert scene_02_events[0].text == 'Không từ nào rơi vào đây.'
    assert scene_02_events[0].start_ms == 1000
    assert scene_02_events[0].end_ms == 2000
