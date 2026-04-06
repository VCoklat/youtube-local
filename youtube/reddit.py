import json
import urllib.parse

import flask
from flask import request

from youtube import util


reddit_app = flask.Flask(__name__)

REDDIT_JSON_BASE = 'https://www.reddit.com'
REDDIT_USER_AGENT = 'reddit-local/1.0 (+https://localhost)'
MEDIA_ALLOWLIST = {
    'i.redd.it',
    'preview.redd.it',
    'external-preview.redd.it',
    'v.redd.it',
    'www.redditstatic.com',
    'emoji.redditmedia.com',
}
TRACKING_QUERY_PREFIXES = ('utm_',)
TRACKING_QUERY_KEYS = {
    'context',
    'ref',
    'ref_source',
    'ref_campaign',
    'referrer',
    'rdt',
}


def _json_headers():
    return (
        ('User-Agent', REDDIT_USER_AGENT),
        ('Accept', 'application/json'),
    )


def _full_json_url(path, params=None):
    if not path.startswith('/'):
        path = '/' + path
    if not path.endswith('.json'):
        path += '.json'
    url = REDDIT_JSON_BASE + path
    if params:
        encoded = urllib.parse.urlencode(params)
        if encoded:
            url += '?' + encoded
    return url


def _load_json_or_error(content):
    try:
        return json.loads(content.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise util.FetchError('502', reason='Bad Gateway',
                              error_message='Failed to decode Reddit JSON') from exc


def fetch_reddit_json(path, params=None):
    payload = util.fetch_url(_full_json_url(path, params=params),
                             headers=_json_headers(), use_tor=False)
    return _load_json_or_error(payload)


def _is_allowed_media_host(hostname):
    if hostname in MEDIA_ALLOWLIST:
        return True
    return any(hostname.endswith('.' + domain) for domain in MEDIA_ALLOWLIST)


def _sanitize_outbound_url(url):
    if not url:
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None

    if parsed.scheme not in ('http', 'https'):
        return None

    kept = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key in TRACKING_QUERY_KEYS:
            continue
        if any(key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        kept.append((key, value))

    sanitized = parsed._replace(query=urllib.parse.urlencode(kept))
    return urllib.parse.urlunsplit(sanitized)


def _proxy_media_url(url):
    sanitized = _sanitize_outbound_url(url)
    if not sanitized:
        return None

    hostname = (urllib.parse.urlsplit(sanitized).hostname or '').lower()
    if not _is_allowed_media_host(hostname):
        return None

    return '/media?url=' + urllib.parse.quote(sanitized, safe='')


def _thumbnail_url(post_data):
    thumbnail = post_data.get('thumbnail')
    if thumbnail and thumbnail.startswith('http'):
        return thumbnail

    preview = post_data.get('preview') or {}
    images = preview.get('images') or []
    if images:
        source = images[0].get('source') or {}
        if source.get('url'):
            return source['url'].replace('&amp;', '&')
    return None


def _video_url(post_data):
    secure_media = post_data.get('secure_media') or {}
    reddit_video = secure_media.get('reddit_video') or {}
    if reddit_video.get('fallback_url'):
        return reddit_video['fallback_url']

    media = post_data.get('media') or {}
    reddit_video = media.get('reddit_video') or {}
    if reddit_video.get('fallback_url'):
        return reddit_video['fallback_url']
    return None


def normalize_post(post_data):
    permalink = post_data.get('permalink')
    if permalink:
        post_url = 'https://www.reddit.com' + permalink
    else:
        post_url = None

    outbound_url = _sanitize_outbound_url(post_data.get('url_overridden_by_dest')
                                          or post_data.get('url'))
    thumbnail = _proxy_media_url(_thumbnail_url(post_data))
    video = _proxy_media_url(_video_url(post_data))

    return {
        'id': post_data.get('id'),
        'name': post_data.get('name'),
        'title': post_data.get('title') or '',
        'author': post_data.get('author'),
        'subreddit': post_data.get('subreddit'),
        'score': post_data.get('score'),
        'num_comments': post_data.get('num_comments'),
        'created_utc': post_data.get('created_utc'),
        'selftext': post_data.get('selftext') or '',
        'is_self': bool(post_data.get('is_self')),
        'is_video': bool(post_data.get('is_video')),
        'nsfw': bool(post_data.get('over_18')),
        'domain': post_data.get('domain'),
        'permalink': permalink,
        'post_url': post_url,
        'external_url': outbound_url,
        'thumbnail': thumbnail,
        'media_url': video,
    }


def normalize_listing(payload):
    data = payload.get('data') or {}
    children = data.get('children') or []
    posts = []
    for child in children:
        if child.get('kind') != 't3':
            continue
        posts.append(normalize_post(child.get('data') or {}))
    return {
        'after': data.get('after'),
        'before': data.get('before'),
        'posts': posts,
    }


def _normalize_comment_node(comment_data):
    replies = comment_data.get('replies')
    children = []
    if isinstance(replies, dict):
        children = replies.get('data', {}).get('children', []) or []

    return {
        'id': comment_data.get('id'),
        'author': comment_data.get('author'),
        'score': comment_data.get('score'),
        'body': comment_data.get('body') or '',
        'created_utc': comment_data.get('created_utc'),
        'replies': _normalize_comments(children),
    }


def _normalize_comments(children):
    results = []
    for child in children:
        if child.get('kind') != 't1':
            continue
        results.append(_normalize_comment_node(child.get('data') or {}))
    return results


def normalize_post_and_comments(payload):
    if not isinstance(payload, list) or len(payload) < 2:
        raise util.FetchError('502', reason='Bad Gateway',
                              error_message='Unexpected Reddit comments payload')

    post_listing = normalize_listing(payload[0])
    post = post_listing['posts'][0] if post_listing['posts'] else None

    comments_children = payload[1].get('data', {}).get('children', [])
    comments = _normalize_comments(comments_children)

    return {
        'post': post,
        'comments': comments,
    }


def _listing_or_empty(path, params=None):
    payload = fetch_reddit_json(path, params=params)
    return normalize_listing(payload)


@reddit_app.route('/')
def reddit_home_page():
    source = request.args.get('source', 'popular')
    after = request.args.get('after')
    params = {'raw_json': 1}
    if after:
        params['after'] = after

    if source == 'all':
        listing = _listing_or_empty('/r/all', params=params)
    else:
        source = 'popular'
        listing = _listing_or_empty('/r/popular', params=params)

    return flask.render_template(
        'reddit_home.html',
        page_title='Reddit Local',
        source=source,
        listing=listing,
    )


@reddit_app.route('/r/<subreddit>')
def reddit_subreddit_page(subreddit):
    after = request.args.get('after')
    params = {'raw_json': 1}
    if after:
        params['after'] = after

    listing = _listing_or_empty('/r/' + subreddit, params=params)
    return flask.render_template(
        'reddit_subreddit.html',
        page_title='r/' + subreddit + ' - Reddit Local',
        subreddit=subreddit,
        listing=listing,
    )


@reddit_app.route('/r/<subreddit>/comments/<post_id>')
@reddit_app.route('/r/<subreddit>/comments/<post_id>/<slug>')
def reddit_post_page(subreddit, post_id, slug=''):
    _ = slug
    post_payload = fetch_reddit_json('/r/' + subreddit + '/comments/' + post_id,
                                     params={'raw_json': 1})
    data = normalize_post_and_comments(post_payload)
    return flask.render_template(
        'reddit_post.html',
        page_title=(data['post']['title'] if data['post'] else 'Post') + ' - Reddit Local',
        post=data['post'],
        comments=data['comments'],
    )


@reddit_app.route('/search')
def reddit_search_page():
    query = request.args.get('q', '').strip()
    kind = request.args.get('kind', 'posts')
    after = request.args.get('after')

    listing = {'posts': [], 'after': None, 'before': None}
    if query:
        params = {'q': query, 'raw_json': 1, 'restrict_sr': 0}
        if after:
            params['after'] = after
        if kind == 'subreddits':
            payload = fetch_reddit_json('/subreddits/search', params=params)
            subreddit_posts = []
            for item in payload.get('data', {}).get('children', []):
                if item.get('kind') != 't5':
                    continue
                data = item.get('data', {})
                subreddit_posts.append({
                    'id': data.get('id'),
                    'title': 'r/' + (data.get('display_name') or ''),
                    'author': None,
                    'subreddit': data.get('display_name'),
                    'score': data.get('subscribers'),
                    'num_comments': None,
                    'created_utc': None,
                    'selftext': data.get('public_description') or '',
                    'is_self': True,
                    'is_video': False,
                    'nsfw': bool(data.get('over18')),
                    'domain': 'reddit.com',
                    'permalink': '/r/' + (data.get('display_name') or ''),
                    'post_url': 'https://www.reddit.com/r/' + (data.get('display_name') or ''),
                    'external_url': None,
                    'thumbnail': _proxy_media_url((data.get('icon_img') or '').replace('&amp;', '&')),
                    'media_url': None,
                })
            listing = {
                'posts': subreddit_posts,
                'after': payload.get('data', {}).get('after'),
                'before': payload.get('data', {}).get('before'),
            }
        else:
            kind = 'posts'
            listing = _listing_or_empty('/search', params=params)

    return flask.render_template(
        'reddit_search.html',
        page_title='Search - Reddit Local',
        query=query,
        kind=kind,
        listing=listing,
    )


@reddit_app.route('/user/<username>')
def reddit_user_page(username):
    entry_kind = request.args.get('kind', 'all')
    after = request.args.get('after')

    params = {'raw_json': 1}
    if after:
        params['after'] = after

    entries = []
    next_after = None

    if entry_kind in ('all', 'submitted'):
        submitted = _listing_or_empty('/user/' + username + '/submitted', params=params)
        for post in submitted['posts']:
            post['entry_type'] = 'post'
        entries.extend(submitted['posts'])
        if entry_kind == 'submitted':
            next_after = submitted['after']

    if entry_kind in ('all', 'comments'):
        comments_payload = fetch_reddit_json('/user/' + username + '/comments',
                                             params=params)
        comment_data = comments_payload.get('data', {})
        comment_entries = []
        for child in comment_data.get('children', []):
            if child.get('kind') != 't1':
                continue
            data = child.get('data', {})
            comment_entries.append({
                'id': data.get('id'),
                'entry_type': 'comment',
                'title': 'Comment in r/' + (data.get('subreddit') or ''),
                'author': data.get('author'),
                'subreddit': data.get('subreddit'),
                'score': data.get('score'),
                'num_comments': None,
                'created_utc': data.get('created_utc'),
                'selftext': data.get('body') or '',
                'is_self': True,
                'is_video': False,
                'nsfw': False,
                'domain': 'reddit.com',
                'permalink': data.get('permalink'),
                'post_url': ('https://www.reddit.com' + data.get('permalink')) if data.get('permalink') else None,
                'external_url': None,
                'thumbnail': None,
                'media_url': None,
            })
        entries.extend(comment_entries)
        if entry_kind == 'comments':
            next_after = comment_data.get('after')

    if entry_kind == 'all':
        entries.sort(key=lambda item: item.get('created_utc') or 0, reverse=True)

    return flask.render_template(
        'reddit_user.html',
        page_title='u/' + username + ' - Reddit Local',
        username=username,
        entry_kind=entry_kind,
        entries=entries,
        after=next_after,
    )


@reddit_app.route('/media')
def reddit_media_proxy():
    target = request.args.get('url', '').strip()
    if not target:
        return flask.abort(400)

    safe_url = _sanitize_outbound_url(target)
    if not safe_url:
        return flask.abort(400)

    parsed = urllib.parse.urlsplit(safe_url)
    if parsed.scheme not in ('http', 'https'):
        return flask.abort(400)

    hostname = (parsed.hostname or '').lower()
    if not _is_allowed_media_host(hostname):
        return flask.abort(403)

    headers = {
        'User-Agent': REDDIT_USER_AGENT,
        'Accept': '*/*',
    }
    if 'Range' in request.headers:
        headers['Range'] = request.headers['Range']

    response, cleanup_func = util.fetch_url_response(
        safe_url,
        headers=headers,
        use_tor=False,
        max_redirects=3,
    )

    passthrough = []
    for key in ('Content-Type', 'Content-Length', 'Content-Range',
                'Accept-Ranges', 'Cache-Control', 'ETag', 'Last-Modified'):
        if response.headers.get(key):
            passthrough.append((key, response.headers.get(key)))

    def generate():
        try:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            cleanup_func(response)

    return flask.Response(generate(), status=response.status,
                          headers=passthrough)


@reddit_app.route('/api/home')
def api_home():
    source = request.args.get('source', 'popular')
    after = request.args.get('after')

    params = {'raw_json': 1}
    if after:
        params['after'] = after

    if source == 'all':
        listing = _listing_or_empty('/r/all', params=params)
    else:
        source = 'popular'
        listing = _listing_or_empty('/r/popular', params=params)

    return flask.jsonify({'source': source, **listing})


@reddit_app.route('/api/r/<subreddit>')
def api_subreddit(subreddit):
    after = request.args.get('after')
    params = {'raw_json': 1}
    if after:
        params['after'] = after
    listing = _listing_or_empty('/r/' + subreddit, params=params)
    return flask.jsonify({'subreddit': subreddit, **listing})


@reddit_app.route('/api/post/<post_id>')
@reddit_app.route('/api/post/<path:post_path>')
def api_post(post_id=None, post_path=None):
    if post_path:
        path = post_path.strip('/')
        if '/comments/' in path:
            payload = fetch_reddit_json('/' + path, params={'raw_json': 1})
            return flask.jsonify(normalize_post_and_comments(payload))

    subreddit = request.args.get('subreddit', '').strip()
    target_post_id = post_id or request.args.get('post_id', '').strip()
    if not subreddit or not target_post_id:
        return flask.abort(400)

    payload = fetch_reddit_json(
        '/r/' + subreddit + '/comments/' + target_post_id,
        params={'raw_json': 1},
    )
    return flask.jsonify(normalize_post_and_comments(payload))


@reddit_app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return flask.jsonify({'query': query, 'after': None, 'before': None,
                              'posts': []})

    kind = request.args.get('kind', 'posts')
    after = request.args.get('after')

    params = {'q': query, 'raw_json': 1, 'restrict_sr': 0}
    if after:
        params['after'] = after

    if kind == 'subreddits':
        payload = fetch_reddit_json('/subreddits/search', params=params)
        listing = {
            'after': payload.get('data', {}).get('after'),
            'before': payload.get('data', {}).get('before'),
            'posts': [],
        }
        for item in payload.get('data', {}).get('children', []):
            if item.get('kind') != 't5':
                continue
            data = item.get('data', {})
            listing['posts'].append({
                'id': data.get('id'),
                'title': 'r/' + (data.get('display_name') or ''),
                'author': None,
                'subreddit': data.get('display_name'),
                'score': data.get('subscribers'),
                'num_comments': None,
                'created_utc': None,
                'selftext': data.get('public_description') or '',
                'is_self': True,
                'is_video': False,
                'nsfw': bool(data.get('over18')),
                'domain': 'reddit.com',
                'permalink': '/r/' + (data.get('display_name') or ''),
                'post_url': 'https://www.reddit.com/r/' + (data.get('display_name') or ''),
                'external_url': None,
                'thumbnail': _proxy_media_url((data.get('icon_img') or '').replace('&amp;', '&')),
                'media_url': None,
            })
    else:
        kind = 'posts'
        listing = _listing_or_empty('/search', params=params)

    return flask.jsonify({'query': query, 'kind': kind, **listing})


@reddit_app.route('/api/user/<username>')
def api_user(username):
    entry_kind = request.args.get('kind', 'all')
    after = request.args.get('after')

    params = {'raw_json': 1}
    if after:
        params['after'] = after

    entries = []
    next_after = None

    if entry_kind in ('all', 'submitted'):
        submitted = _listing_or_empty('/user/' + username + '/submitted', params=params)
        for post in submitted['posts']:
            post['entry_type'] = 'post'
        entries.extend(submitted['posts'])
        if entry_kind == 'submitted':
            next_after = submitted['after']

    if entry_kind in ('all', 'comments'):
        comments_payload = fetch_reddit_json('/user/' + username + '/comments',
                                             params=params)
        comment_data = comments_payload.get('data', {})
        for child in comment_data.get('children', []):
            if child.get('kind') != 't1':
                continue
            data = child.get('data', {})
            entries.append({
                'id': data.get('id'),
                'entry_type': 'comment',
                'title': 'Comment in r/' + (data.get('subreddit') or ''),
                'author': data.get('author'),
                'subreddit': data.get('subreddit'),
                'score': data.get('score'),
                'num_comments': None,
                'created_utc': data.get('created_utc'),
                'selftext': data.get('body') or '',
                'is_self': True,
                'is_video': False,
                'nsfw': False,
                'domain': 'reddit.com',
                'permalink': data.get('permalink'),
                'post_url': ('https://www.reddit.com' + data.get('permalink')) if data.get('permalink') else None,
                'external_url': None,
                'thumbnail': None,
                'media_url': None,
            })
        if entry_kind == 'comments':
            next_after = comment_data.get('after')

    if entry_kind == 'all':
        entries.sort(key=lambda item: item.get('created_utc') or 0, reverse=True)

    return flask.jsonify({
        'username': username,
        'kind': entry_kind,
        'after': next_after,
        'entries': entries,
    })
