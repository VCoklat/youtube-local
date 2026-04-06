"""Tests for image compression and response compression features."""
import gzip
import io
import pytest

from youtube import yt_app
from youtube import util
import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_jpeg():
    """Return a tiny valid JPEG as bytes (via Pillow)."""
    try:
        from PIL import Image
        img = Image.new('RGB', (4, 4), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return buf.getvalue()
    except ImportError:
        pytest.skip('Pillow not installed')


def _make_minimal_png():
    """Return a tiny valid PNG as bytes (via Pillow)."""
    try:
        from PIL import Image
        img = Image.new('RGBA', (4, 4), color=(128, 64, 32, 200))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except ImportError:
        pytest.skip('Pillow not installed')


# ---------------------------------------------------------------------------
# util.compress_image unit tests
# ---------------------------------------------------------------------------

class TestCompressImage:
    def test_jpeg_compression_returns_jpeg(self):
        jpeg_data = _make_minimal_jpeg()
        result, ctype = util.compress_image(jpeg_data, 'image/jpeg', 70)
        assert ctype == 'image/jpeg'
        # Result must still be valid JPEG (starts with SOI marker)
        assert result[:2] == b'\xff\xd8'

    def test_png_with_transparency_stays_png(self):
        png_data = _make_minimal_png()
        result, ctype = util.compress_image(png_data, 'image/png', 70)
        assert ctype == 'image/png'
        # PNG magic bytes
        assert result[:8] == b'\x89PNG\r\n\x1a\n'

    def test_invalid_data_returns_original(self):
        bad_data = b'not an image at all'
        result, ctype = util.compress_image(bad_data, 'image/jpeg', 70)
        assert result == bad_data
        assert ctype == 'image/jpeg'

    def test_jpeg_quality_affects_size(self):
        try:
            from PIL import Image
            img = Image.new('RGB', (200, 200), color=(100, 150, 200))
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=95)
            big_jpeg = buf.getvalue()
        except ImportError:
            pytest.skip('Pillow not installed')

        high_q, _ = util.compress_image(big_jpeg, 'image/jpeg', 95)
        low_q, _ = util.compress_image(big_jpeg, 'image/jpeg', 10)
        assert len(low_q) < len(high_q)

    def test_no_pillow_returns_original(self, monkeypatch):
        monkeypatch.setattr(util, 'have_pillow', False)
        data = b'fake image data'
        result, ctype = util.compress_image(data, 'image/jpeg', 70)
        assert result == data
        assert ctype == 'image/jpeg'


# ---------------------------------------------------------------------------
# Response compression (gzip) tests via Flask test client
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    yt_app.testing = True
    return yt_app.test_client()


class TestResponseCompression:
    def test_html_compressed_when_enabled(self, monkeypatch, client):
        monkeypatch.setattr(settings, 'enable_response_compression', True)
        response = client.get(
            '/',
            headers={'Accept-Encoding': 'gzip'},
        )
        assert response.status_code == 200
        assert response.headers.get('Content-Encoding') == 'gzip'
        # Decompressed body should be valid HTML
        body = gzip.decompress(response.data)
        assert b'<html' in body.lower() or b'<!doctype' in body.lower()

    def test_html_not_compressed_when_disabled(self, monkeypatch, client):
        monkeypatch.setattr(settings, 'enable_response_compression', False)
        response = client.get(
            '/',
            headers={'Accept-Encoding': 'gzip'},
        )
        assert response.status_code == 200
        assert response.headers.get('Content-Encoding') is None

    def test_no_compression_without_accept_encoding(self, monkeypatch, client):
        monkeypatch.setattr(settings, 'enable_response_compression', True)
        response = client.get('/')
        assert response.headers.get('Content-Encoding') is None

    def test_css_compressed_when_enabled(self, monkeypatch, client):
        monkeypatch.setattr(settings, 'enable_response_compression', True)
        response = client.get(
            '/shared.css',
            headers={'Accept-Encoding': 'gzip'},
        )
        assert response.status_code == 200
        assert response.headers.get('Content-Encoding') == 'gzip'
        body = gzip.decompress(response.data)
        assert len(body) > 0

    def test_vary_header_set(self, monkeypatch, client):
        monkeypatch.setattr(settings, 'enable_response_compression', True)
        response = client.get(
            '/',
            headers={'Accept-Encoding': 'gzip'},
        )
        assert 'Accept-Encoding' in response.headers.get('Vary', '')
