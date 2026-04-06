import re
import flask
from youtube import util
from youtube import yt_app

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

@yt_app.route('/gold')
def gold_price_page():
    url = 'https://goldprice.org/spot-gold.html'
    try:
        # Add more realistic browser headers to bypass Cloudflare/bot protection
        headers = (
            ('User-Agent', USER_AGENT),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'),
            ('Accept-Language', 'en-US,en;q=0.5'),
            ('Sec-Fetch-Dest', 'document'),
            ('Sec-Fetch-Mode', 'navigate'),
            ('Sec-Fetch-Site', 'none'),
            ('Upgrade-Insecure-Requests', '1'),
        )
        
        # Fetch the page using your real IP (use_tor=False) to avoid Tor blocks
        content = util.fetch_url(
            url,
            headers=headers,
            use_tor=False  # <--- Changed this from True to False
        )
        html = content.decode('utf-8', errors='ignore')
        
        # Extract the title of the page
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else 'Spot Gold'
        
        # Find all formatted prices (e.g., $2,345.67) in the HTML
        raw_prices = re.findall(r'\$[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?', html)
        
        # Filter duplicates while keeping order
        seen = set()
        unique_prices = []
        for p in raw_prices:
            if p not in seen:
                seen.add(p)
                unique_prices.append(p)
                
        return flask.render_template(
            'gold_page.html',
            page_title=title,
            prices=unique_prices[:5]  # Take the top 5 extracted prices
        )
        
    except util.FetchError as e:
        return flask.render_template('error.html', error_message=f"Failed to fetch gold price: {e}")