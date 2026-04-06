import urllib.parse

import pytest

from youtube import yt_app
from youtube import util
from youtube import reddit


def test_sanitize_outbound_url_strips_tracking():
    url = (
        'https://example.com/path?utm_source=x&keep=1&ref=abc'
        '&utm_medium=y#frag'
    )
    assert reddit._sanitize_outbound_url(url) == 'https://example.com/path?keep=1'


def test_proxy_media_url_requires_allowlist():
    disallowed = 'https://example.com/image.jpg'
    assert reddit._proxy_media_url(disallowed) is None

    allowed = 'https://i.redd.it/file.png?utm_source=a&x=1'
    proxied = reddit._proxy_media_url(allowed)
    assert proxied is not None
    assert proxied.startswith('/youtube.com/reddit/media?url=')
    target = urllib.parse.unquote(proxied.split('=', 1)[1])
    assert target == 'https://i.redd.it/file.png?x=1'


def test_normalize_comments_recursion():
    payload = [
        {'data': {'children': [{'kind': 't3', 'data': {'id': 'p1', 'title': 't'}}]}},
        {'data': {'children': [
            {'kind': 't1', 'data': {
                'id': 'c1',
                'author': 'a1',
                'body': 'top',
                'replies': {'data': {'children': [
                    {'kind': 't1', 'data': {'id': 'c2', 'author': 'a2', 'body': 'nested'}},
                ]}},
            }},
        ]}},
    ]

    result = reddit.normalize_post_and_comments(payload)
    assert result['comments'][0]['id'] == 'c1'
    assert result['comments'][0]['replies'][0]['id'] == 'c2'


@pytest.fixture
def client():
    yt_app.testing = True
    return yt_app.test_client()


def test_api_home_passes_after(monkeypatch, client):
    captured = {}

    def fake_fetch(path, params=None):
        captured['path'] = path
        captured['params'] = params
        return {'data': {'children': [], 'after': 'next123', 'before': None}}

    monkeypatch.setattr(reddit, 'fetch_reddit_json', fake_fetch)

    response = client.get('/api/home?after=t3_abc')
    assert response.status_code == 200
    body = response.get_json()
    assert body['after'] == 'next123'
    assert captured['path'] == '/r/popular'
    assert captured['params']['after'] == 't3_abc'


def test_api_post_requires_subreddit_for_id_route(client):
    response = client.get('/api/post/abc123')
    assert response.status_code == 400


def test_api_post_path_route(monkeypatch, client):
    def fake_fetch(path, params=None):
        assert path == '/r/python/comments/abc123/test-title'
        return [
            {'data': {'children': [{'kind': 't3', 'data': {'id': 'p1', 'title': 'title'}}]}},
            {'data': {'children': []}},
        ]

    monkeypatch.setattr(reddit, 'fetch_reddit_json', fake_fetch)
    response = client.get('/api/post/r/python/comments/abc123/test-title')
    assert response.status_code == 200
    body = response.get_json()
    assert body['post']['id'] == 'p1'


def test_media_proxy_rejects_disallowed_host(client):
    url = urllib.parse.quote('https://example.com/file.png', safe='')
    response = client.get('/reddit/media?url=' + url)
    assert response.status_code == 403


def test_media_proxy_streams_allowlisted(monkeypatch, client):
    class DummyResponse:
        status = 200
        reason = 'OK'
        headers = {
            'Content-Type': 'image/png',
            'Content-Length': '4',
            'Cache-Control': 'public',
        }

        def __init__(self):
            self._chunks = [b'test', b'']

        def read(self, _size=None):
            return self._chunks.pop(0)

    called = {}

    def fake_fetch_url_response(url, headers=(), timeout=15, data=None,
                                cookiejar_send=None, cookiejar_receive=None,
                                use_tor=True, max_redirects=None):
        called['url'] = url
        called['use_tor'] = use_tor
        called['max_redirects'] = max_redirects
        return DummyResponse(), (lambda _resp: None)

    monkeypatch.setattr(util, 'fetch_url_response', fake_fetch_url_response)

    target = urllib.parse.quote('https://i.redd.it/file.png?utm_source=x&keep=1', safe='')
    response = client.get('/reddit/media?url=' + target)
    assert response.status_code == 200
    assert response.data == b'test'
    assert called['url'] == 'https://i.redd.it/file.png?keep=1'
    assert called['use_tor'] is False
    assert called['max_redirects'] == 3
