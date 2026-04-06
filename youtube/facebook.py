import re
import urllib.parse
import flask
from flask import request

from youtube import util
from youtube import yt_app

# Mimic a standard mobile browser so mbasic.facebook.com serves us the page
FB_USER_AGENT = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

def _fetch_mbasic_page(page_name):
    url = f'https://mbasic.facebook.com/{page_name}'
    try:
        # We use_tor=True because Facebook heavily rate-limits data center IPs
        content = util.fetch_url(
            url, 
            headers=(('User-Agent', FB_USER_AGENT), ('Accept-Language', 'en-US,en;q=0.9')),
            use_tor=True
        )
        html = content.decode('utf-8', errors='ignore')
        
        # Proof-of-concept: extract paragraph texts from the messy mbasic HTML
        # A more robust solution would require adding BeautifulSoup to requirements.txt
        raw_paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.IGNORECASE)
        
        # Strip internal HTML tags (like bold/links) from the extracted text
        clean_posts = []
        for p in raw_paragraphs:
            clean_text = re.sub(r'<[^>]+>', ' ', p).strip()
            if clean_text and len(clean_text) > 10:  # Ignore tiny UI fragments
                clean_posts.append(clean_text)
                
        return clean_posts
    except util.FetchError as e:
        print(f"Facebook Fetch Error: {e}")
        return None

@yt_app.route('/facebook')
def facebook_home():
    return flask.render_template('facebook_home.html', page_title='Facebook Local')

@yt_app.route('/facebook/<page_name>')
def facebook_public_page(page_name):
    posts = _fetch_mbasic_page(page_name)
    return flask.render_template(
        'facebook_page.html',
        page_title=f'{page_name} - Facebook Local',
        page_name=page_name,
        posts=posts,
    )