import os

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
AUTH_HEADERS = {'X-API-Key': os.environ['SUBTITLE_SERVICE_API_KEY']}


def test_health_does_not_require_api_key():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_v1_route_rejects_missing_api_key():
    response = client.post('/v1/subtitles/ass', json={'track': [], 'width': 1080, 'height': 1920})
    assert response.status_code == 401


def test_v1_route_rejects_wrong_api_key():
    response = client.post(
        '/v1/subtitles/ass', json={'track': [], 'width': 1080, 'height': 1920}, headers={'X-API-Key': 'wrong-key'},
    )
    assert response.status_code == 401


def test_subtitles_track_sentence_fallback_without_word_timings():
    body = {
        'scenes': [{'scene_id': 'scene_01', 'narration': 'Một câu. Câu nữa.', 'start_ms': 0, 'end_ms': 4000}],
        'offset_ms': 0,
    }
    response = client.post('/v1/subtitles/track', json=body, headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload['source'] == 'sentence_proportional'
    assert len(payload['track']) == 2


def test_subtitles_track_word_level_with_provided_timings():
    body = {
        'scenes': [{'scene_id': 'scene_01', 'narration': 'ignored', 'start_ms': 0, 'end_ms': 2000}],
        'word_timings': [
            {'text': 'xin', 'start_ms': 0, 'end_ms': 300},
            {'text': 'chào', 'start_ms': 300, 'end_ms': 600},
        ],
        'max_words_per_event': 1,
    }
    response = client.post('/v1/subtitles/track', json=body, headers=AUTH_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload['source'] == 'whisper_word_level'
    assert [event['text'] for event in payload['track']] == ['xin', 'chào']


def test_subtitles_ass_endpoint():
    body = {
        'track': [{'scene_id': 'scene_01', 'text': 'Hello', 'start_ms': 0, 'end_ms': 1000}],
        'width': 1920,
        'height': 1080,
    }
    response = client.post('/v1/subtitles/ass', json=body, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert 'PlayResX: 1920' in response.json()['ass']


def test_subtitles_track_rejects_invalid_scene_bounds():
    body = {'scenes': [{'scene_id': 'scene_01', 'narration': 'x', 'start_ms': -1, 'end_ms': 1000}]}
    response = client.post('/v1/subtitles/track', json=body, headers=AUTH_HEADERS)
    assert response.status_code == 422
