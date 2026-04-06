import re
import os
import urllib.parse
import flask
from flask import request

from youtube import util
from youtube import yt_app
import settings  

# Mimic a standard mobile browser so mbasic.facebook.com serves us the page
FB_USER_AGENT = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'

def _load_facebook_cookies():
    cookie_file = os.path.join(settings.program_directory, 'facebook_cookies.txt')
    print(f"DEBUG: Looking for cookies exactly here: {cookie_file}") 
    if not os.path.exists(cookie_file):
        return None
        
    cookie_string = ""
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip comments and empty lines in the Netscape format
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.strip().split('\t')
                # A valid Netscape cookie line has 7 tab-separated columns
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookie_string += f"{name}={value}; "
        return cookie_string
    except Exception as e:
        print(f"Error loading facebook_cookies.txt: {e}")
        return None

def _fetch_mbasic_page(page_name):
    url = f'https://mbasic.facebook.com/{page_name}'
    
    # Load your exported cookies
    cookie_string = _load_facebook_cookies()
    
    # Build the headers list dynamically
    headers_list = [
        ('User-Agent', FB_USER_AGENT), 
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'),
        ('Accept-Language', 'en-US,en;q=0.9'),
        ('Upgrade-Insecure-Requests', '1'),
        ('Sec-Fetch-Dest', 'document'),
        ('Sec-Fetch-Mode', 'navigate'),
        ('Sec-Fetch-Site', 'none'),
        ('Sec-Fetch-User', '?1'),
        ('Connection', 'keep-alive'),
    ]
    
    # If we found the cookies.txt file, attach it to the headers!
    if cookie_string:
        headers_list.append(('Cookie', cookie_string))
    else:
        print("WARNING: facebook_cookies.txt not found. Facebook will likely block the request.")

    try:
        content = util.fetch_url(
            url, 
            headers=tuple(headers_list),  # util.fetch_url expects a tuple
            use_tor=False
        )
        html = content.decode('utf-8', errors='ignore')
        
        raw_paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.IGNORECASE)
        
        clean_posts = []
        for p in raw_paragraphs:
            clean_text = re.sub(r'<[^>]+>', ' ', p).strip()
            if clean_text and len(clean_text) > 10:
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