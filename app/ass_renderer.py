"""Builds an ASS (Advanced SubStation Alpha) subtitle file from a subtitle
track. Ported 1:1 from the assTime()/assText()/assHeader template that used
to be copy-pasted byte-for-byte across renderer.ts, kenburns-renderer.ts and
landscape-video-renderer.ts (Vimo-ai, TypeScript side) -- same style line
(Arial 48, same colours/margins/border), parameterized by width/height
instead of hardcoded, so every caller gets a correctly-sized header instead
of only the one renderer that already parameterized it.
"""
from typing import List

from app.models import SubtitleEvent


def _ass_time(ms: int) -> str:
    hours = ms // 3_600_000
    minutes = ms % 3_600_000 // 60_000
    seconds = ms % 60_000 // 1000
    centiseconds = ms % 1000 // 10
    return f'{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}'


def _ass_text(value: str) -> str:
    return value.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').replace('\n', '\\N')


def _ass_header(width: int, height: int) -> str:
    return (
        '[Script Info]\n'
        'ScriptType: v4.00+\n'
        f'PlayResX: {width}\n'
        f'PlayResY: {height}\n'
        'WrapStyle: 0\n\n'
        '[V4+ Styles]\n'
        'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, '
        'Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, '
        'Alignment, MarginL, MarginR, MarginV, Encoding\n'
        'Style: Subtitle,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,3,2,0,2,90,90,140,1\n\n'
        '[Events]\n'
        'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
    )


def render_ass(track: List[SubtitleEvent], width: int, height: int) -> str:
    header = _ass_header(width, height)
    lines = [
        f'Dialogue: 0,{_ass_time(item.start_ms)},{_ass_time(item.end_ms)},Subtitle,,0,0,0,,{_ass_text(item.text)}'
        for item in track
    ]
    return header + '\n'.join(lines)
