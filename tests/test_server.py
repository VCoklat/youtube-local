import server


def _start_response_capture():
    captured = {}

    def start_response(status, headers):
        captured['status'] = status
        captured['headers'] = headers

    return captured, start_response


def test_site_dispatch_routes_reddit_path(monkeypatch):
    def fake_yt_app(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']

    monkeypatch.setattr(server, 'yt_app', fake_yt_app)

    env = {
        'REMOTE_ADDR': '127.0.0.1',
        'REQUEST_METHOD': 'GET',
        'QUERY_STRING': '',
        'PATH_INFO': '/reddit',
    }
    captured, start_response = _start_response_capture()
    body = b''.join(server.site_dispatch(env, start_response))

    assert captured['status'] == '200 OK'
    assert body == b'ok'

