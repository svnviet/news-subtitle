from app.ass_renderer import render_ass
from app.models import SubtitleEvent


def test_header_reflects_requested_dimensions():
    ass = render_ass([], width=1920, height=1080)
    assert 'PlayResX: 1920' in ass
    assert 'PlayResY: 1080' in ass


def test_header_reflects_portrait_dimensions_too():
    ass = render_ass([], width=1080, height=1920)
    assert 'PlayResX: 1080' in ass
    assert 'PlayResY: 1920' in ass


def test_dialogue_line_format_and_time_codes():
    track = [SubtitleEvent(scene_id='scene_01', text='Xin chào', start_ms=1500, end_ms=63250)]
    ass = render_ass(track, width=1080, height=1920)
    # 1500ms -> 0:00:01.50 ; 63250ms -> 0:01:03.25
    assert 'Dialogue: 0,0:00:01.50,0:01:03.25,Subtitle,,0,0,0,,Xin chào' in ass


def test_text_escaping_for_ass_special_characters():
    track = [SubtitleEvent(scene_id='scene_01', text='A {B} \\C\nD', start_ms=0, end_ms=1000)]
    ass = render_ass(track, width=1080, height=1920)
    assert 'A \\{B\\} \\\\C\\ND' in ass
