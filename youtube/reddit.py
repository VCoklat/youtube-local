import json
import urllib.parse

import flask
from flask import request

from youtube import util
from youtube import yt_app


REDDIT_JSON_BASE = 'https://www.reddit.com'
REDDIT_USER_AGENT = 'reddit-local/1.0 (+https://github.com/VCoklat/youtube-local)'
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
        raise util.FetchError(
            '502',
            reason='Bad Gateway',
            error_message='Failed to decode Reddit JSON',
        ) from exc


def fetch_reddit_json(path, params=None):
    payload = util.fetch_url(
        _full_json_url(path, params=params),
        headers=_json_headers(),
        use_tor=False,
    )
    return _load_json_or_error(payload)


def _is_allowed_media_host(hostname):
    if hostname in MEDIA_ALLOWLIST:
        return True
    return any(hostname.endswith('.' + host) for host in MEDIA_ALLOWLIST)


def _sanitize_outbound_url(url):
    if not url:
        return None

    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return None

    if parsed.scheme not in ('http', 'https'):
        return None

    kept_query = []
    for key, value in urllib.parse.parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        if key in TRACKING_QUERY_KEYS:
            continue
        if any(key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        kept_query.append((key, value))

    sanitized = parsed._replace(
        query=urllib.parse.urlencode(kept_query),
        fragment='',
    )
    return urllib.parse.urlunsplit(sanitized)


def _proxy_media_url(url):
    if not url:
        return None

    # Do not sanitize! Sanitization breaks Reddit's image signature (s=)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http', 'https'):
        return None

    host = (parsed.hostname or '').lower()
    if not _is_allowed_media_host(host):
        return None

    return '/reddit/media?url=' + urllib.parse.quote(url, safe='')


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
    post_url = 'https://www.reddit.com' + permalink if permalink else None

    outbound = _sanitize_outbound_url(
        post_data.get('url_overridden_by_dest') or post_data.get('url'),
    )

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
        'external_url': outbound,
        'thumbnail': _proxy_media_url(_thumbnail_url(post_data)),
        'media_url': _proxy_media_url(_video_url(post_data)),
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


def _normalize_comments(children):
    normalized = []
    for child in children:
        if child.get('kind') != 't1':
            continue

        comment = child.get('data') or {}
        replies = comment.get('replies')
        nested = []
        if isinstance(replies, dict):
            nested = replies.get('data', {}).get('children', []) or []

        normalized.append({
            'id': comment.get('id'),
            'author': comment.get('author'),
            'score': comment.get('score'),
            'body': comment.get('body') or '',
            'created_utc': comment.get('created_utc'),
            'replies': _normalize_comments(nested),
        })
    return normalized


def normalize_post_and_comments(payload):
    if not isinstance(payload, list) or len(payload) < 2:
        raise util.FetchError(
            '502',
            reason='Bad Gateway',
            error_message='Unexpected Reddit comments payload',
        )

    post_listing = normalize_listing(payload[0])
    comments_children = payload[1].get('data', {}).get('children', [])

    return {
        'post': post_listing['posts'][0] if post_listing['posts'] else None,
        'comments': _normalize_comments(comments_children),
    }


def _normalize_subreddit_result(item_data):
    display_name = item_data.get('display_name') or ''
    return {
        'id': item_data.get('id'),
        'name': item_data.get('name'),
        'title': 'r/' + display_name,
        'author': None,
        'subreddit': display_name,
        'score': item_data.get('subscribers'),
        'num_comments': None,
        'created_utc': None,
        'selftext': item_data.get('public_description') or '',
        'is_self': True,
        'is_video': False,
        'nsfw': bool(item_data.get('over18')),
        'domain': 'reddit.com',
        'permalink': '/r/' + display_name,
        'post_url': 'https://www.reddit.com/r/' + display_name,
        'external_url': None,
        'thumbnail': _proxy_media_url(
            (item_data.get('icon_img') or '').replace('&amp;', '&'),
        ),
        'media_url': None,
    }


def _normalize_comment_history(item_data):
    permalink = item_data.get('permalink')
    post_url = 'https://www.reddit.com' + permalink if permalink else None
    return {
        'id': item_data.get('id'),
        'entry_type': 'comment',
        'title': 'Comment in r/' + (item_data.get('subreddit') or ''),
        'author': item_data.get('author'),
        'subreddit': item_data.get('subreddit'),
        'score': item_data.get('score'),
        'num_comments': None,
        'created_utc': item_data.get('created_utc'),
        'selftext': item_data.get('body') or '',
        'is_self': True,
        'is_video': False,
        'nsfw': False,
        'domain': 'reddit.com',
        'permalink': permalink,
        'post_url': post_url,
        'external_url': None,
        'thumbnail': None,
        'media_url': None,
    }


def _listing_or_empty(path, params=None):
    payload = fetch_reddit_json(path, params=params)
    return normalize_listing(payload)


def _fetch_user_entries(username, entry_kind, after=None):
    params = {'raw_json': 1}
    if after:
        params['after'] = after

    entries = []
    next_after = None

    if entry_kind in ('all', 'submitted'):
        submitted = _listing_or_empty('/user/' + username + '/submitted', params)
        for post in submitted['posts']:
            post['entry_type'] = 'post'
        entries.extend(submitted['posts'])
        if entry_kind == 'submitted':
            next_after = submitted['after']

    if entry_kind in ('all', 'comments'):
        payload = fetch_reddit_json('/user/' + username + '/comments', params)
        comment_data = payload.get('data', {})
        for child in comment_data.get('children', []):
            if child.get('kind') != 't1':
                continue
            entries.append(_normalize_comment_history(child.get('data') or {}))
        if entry_kind == 'comments':
            next_after = comment_data.get('after')

    if entry_kind == 'all':
        entries.sort(key=lambda item: item.get('created_utc') or 0, reverse=True)

    return entries, next_after


def _fetch_search_listing(query, kind='posts', after=None):
    if not query:
        return kind, {'after': None, 'before': None, 'posts': []}

    params = {
        'q': query,
        'raw_json': 1,
        'restrict_sr': 0,
    }
    if after:
        params['after'] = after

    if kind == 'subreddits':
        payload = fetch_reddit_json('/subreddits/search', params)
        data = payload.get('data', {})
        posts = []
        for child in data.get('children', []):
            if child.get('kind') != 't5':
                continue
            posts.append(_normalize_subreddit_result(child.get('data') or {}))
        return kind, {
            'after': data.get('after'),
            'before': data.get('before'),
            'posts': posts,
        }

    kind = 'posts'
    return kind, _listing_or_empty('/search', params)


def _fetch_home_listing(source='popular', after=None):
    params = {'raw_json': 1}
    if after:
        params['after'] = after

    if source == 'all':
        return 'all', _listing_or_empty('/r/all', params)
    return 'popular', _listing_or_empty('/r/popular', params)


def _fetch_post_from_path(path):
    payload = fetch_reddit_json(path, params={'raw_json': 1})
    return normalize_post_and_comments(payload)


@yt_app.route('/reddit')
def reddit_home_page():
    source = request.args.get('source', 'popular')
    after = request.args.get('after')
    source, listing = _fetch_home_listing(source, after)
    return flask.render_template(
        'reddit_home.html',
        page_title='Reddit Local',
        source=source,
        listing=listing,
    )


@yt_app.route('/reddit/r/<subreddit>')
def reddit_subreddit_page(subreddit):
    after = request.args.get('after')
    params = {'raw_json': 1}
    if after:
        params['after'] = after
    listing = _listing_or_empty('/r/' + subreddit, params)
    return flask.render_template(
        'reddit_subreddit.html',
        page_title='r/' + subreddit + ' - Reddit Local',
        subreddit=subreddit,
        listing=listing,
    )


@yt_app.route('/reddit/r/<subreddit>/comments/<post_id>')
@yt_app.route('/reddit/r/<subreddit>/comments/<post_id>/<slug>')
def reddit_post_page(subreddit, post_id, slug=''):
    _ = slug
    data = _fetch_post_from_path('/r/' + subreddit + '/comments/' + post_id)
    title = 'Post' if not data['post'] else data['post']['title']
    return flask.render_template(
        'reddit_post.html',
        page_title=title + ' - Reddit Local',
        post=data['post'],
        comments=data['comments'],
    )

@yt_app.route('/reddit/user/<username>/m/<multireddit>')
@yt_app.route('/reddit/user/<username>/m/<multireddit>.rss')
def reddit_multireddit_page(username, multireddit):
    after = request.args.get('after')
    params = {'raw_json': 1}
    if after:
        params['after'] = after
        
    # Fetch standard post listing for the multireddit
    path = f'/user/{username}/m/{multireddit}'
    listing = _listing_or_empty(path, params)
    
    return flask.render_template(
        'reddit_multireddit.html',
        page_title=f'm/{multireddit} - Reddit Local',
        username=username,
        multireddit=multireddit,
        listing=listing,
    )

@yt_app.route('/reddit/search')
def reddit_search_page():
    query = request.args.get('q', '').strip()
    kind = request.args.get('kind', 'posts')
    after = request.args.get('after')
    kind, listing = _fetch_search_listing(query, kind, after)
    return flask.render_template(
        'reddit_search.html',
        page_title='Search - Reddit Local',
        query=query,
        kind=kind,
        listing=listing,
    )


@yt_app.route('/reddit/user/<username>')
def reddit_user_page(username):
    entry_kind = request.args.get('kind', 'all')
    after = request.args.get('after')
    entries, next_after = _fetch_user_entries(username, entry_kind, after)
    return flask.render_template(
        'reddit_user.html',
        page_title='u/' + username + ' - Reddit Local',
        username=username,
        entry_kind=entry_kind,
        entries=entries,
        after=next_after,
    )


@yt_app.route('/reddit/media')
def reddit_media_proxy():
    target = request.args.get('url', '').strip()
    if not target:
        return flask.abort(400)

    # Use the raw target. Do not use _sanitize_outbound_url!
    parsed = urllib.parse.urlsplit(target)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('http', 'https'):
        return flask.abort(400)
    if not _is_allowed_media_host(host):
        return flask.abort(403)

    # Use a standard browser User-Agent to bypass Reddit CDN bot protection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
    }
    if 'Range' in request.headers:
        headers['Range'] = request.headers['Range']

    response, cleanup_func = util.fetch_url_response(
        target,  # Pass the raw target, not safe_url
        headers=headers,
        use_tor=False,
        max_redirects=3,
    )

    headers_out = []
    for key in (
        'Content-Type',
        'Content-Length',
        'Content-Range',
        'Accept-Ranges',
        'Cache-Control',
        'ETag',
        'Last-Modified',
    ):
        value = response.headers.get(key)
        if value:
            headers_out.append((key, value))

    def generate():
        try:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            cleanup_func(response)

    return flask.Response(generate(), status=response.status, headers=headers_out)


@yt_app.route('/api/home')
def api_home():
    source = request.args.get('source', 'popular')
    after = request.args.get('after')
    source, listing = _fetch_home_listing(source, after)
    return flask.jsonify({'source': source, **listing})


@yt_app.route('/api/r/<subreddit>')
def api_subreddit(subreddit):
    after = request.args.get('after')
    params = {'raw_json': 1}
    if after:
        params['after'] = after
    listing = _listing_or_empty('/r/' + subreddit, params)
    return flask.jsonify({'subreddit': subreddit, **listing})


@yt_app.route('/api/post/<post_id>')
@yt_app.route('/api/post/<path:post_path>')
def api_post(post_id=None, post_path=None):
    if post_path:
        path = post_path.strip('/')
        if '/comments/' in path:
            return flask.jsonify(_fetch_post_from_path('/' + path))

    subreddit = request.args.get('subreddit', '').strip()
    target_post_id = post_id or request.args.get('post_id', '').strip()
    if not subreddit or not target_post_id:
        return flask.abort(400)

    path = '/r/' + subreddit + '/comments/' + target_post_id
    return flask.jsonify(_fetch_post_from_path(path))


@yt_app.route('/api/search')
def api_search():
    query = request.args.get('q', '').strip()
    kind = request.args.get('kind', 'posts')
    after = request.args.get('after')
    kind, listing = _fetch_search_listing(query, kind, after)
    return flask.jsonify({'query': query, 'kind': kind, **listing})


@yt_app.route('/api/user/<username>')
def api_user(username):
    entry_kind = request.args.get('kind', 'all')
    after = request.args.get('after')
    entries, next_after = _fetch_user_entries(username, entry_kind, after)
    return flask.jsonify({
        'username': username,
        'kind': entry_kind,
        'after': next_after,
        'entries': entries,
    })
