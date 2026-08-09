from flask import Flask, jsonify, request, render_template_string
import requests
import re
import json
import os
from functools import lru_cache
from datetime import datetime, timedelta
import time
import logging
import zlib
import gzip
from io import BytesIO

app = Flask(__name__)

# ============ LOGGING CONFIG ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIG ============
BASE_URL = "https://faphouse2.com"
EMAIL = os.environ.get('EMAIL', 'rockstarga69@gmail.com')
PASSWORD = os.environ.get('PASSWORD', 'Jaiisbeast@1')

# Cache settings
CACHE_DURATION = 300

# ============ SESSION MANAGER ============
class FaphouseClient:
    def __init__(self):
        self.session = None
        self.logged_in = False
        self.session_created = False
        
    def ensure_session(self):
        """Ensure we have a valid session"""
        if not self.session or not self.logged_in:
            logger.info("🔄 Creating new session...")
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            self.login()
        return self.session
    
    def login(self):
        """Login and store session"""
        logger.info(f"🔐 Attempting login with email: {EMAIL[:5]}...")
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/json',
            'Origin': BASE_URL,
            'Referer': f'{BASE_URL}/',
            'DNT': '1',
            'Connection': 'keep-alive'
        })
        
        try:
            logger.info("  📡 Getting initial page...")
            init_res = self.session.get(BASE_URL, timeout=10)
            logger.info(f"  📡 Initial page status: {init_res.status_code}")
            
            payload = {
                "login": EMAIL,
                "password": PASSWORD,
                "rememberMe": "1",
                "recaptcha": "",
                "trackingParamsBag": "eyJwcm9tb19pZCI6IiIsInZpZGVvX2lkIjpudWxsLCJzdHVkaW9faWQiOm51bGwsInByb2R1Y2VyX2lkIjpudWxsLCJvcmllbnRhdGlvbiI6InN0cmFpZ2h0IiwibWxfcGFnZSI6Im1haW5fcGFnZSIsIm1sX3BhZ2VfdmFsdWVfaWQiOm51bGwsIm1sX3BhZ2VfdmFsdWUiOm51bGwsIm1sX3BhZ2VfbnVtYmVyIjpudWxsLCJtbF9yZWZfcGFnZV92YWx1ZV9pZCI6bnVsbCwibWxfcmVmX3BhZ2VfdmFsdWUiOiIiLCJtbF9yZWZfcGFnZV9udW1iZXIiOm51bGwsIm1sX3JlZl9wYWdlIjoiZGlyZWN0In0="
            }
            
            logger.info("  📡 Sending login request...")
            login_res = self.session.post(
                f"{BASE_URL}/api/auth/signin",
                json=payload,
                timeout=15
            )
            
            logger.info(f"  📡 Login response status: {login_res.status_code}")
            
            if login_res.status_code == 200:
                try:
                    data = login_res.json()
                    if data.get('success') or data.get('data'):
                        self.logged_in = True
                        logger.info("✅ Login successful!")
                        return True
                except:
                    pass
                
                if len(self.session.cookies) > 0:
                    self.logged_in = True
                    logger.info(f"✅ Login successful (session established)!")
                    return True
            
            self.logged_in = False
            return False
            
        except Exception as e:
            logger.error(f"❌ Login error: {str(e)}")
            self.logged_in = False
            return False
    
    def _decode_response(self, response):
        """Decode compressed response properly"""
        try:
            content_encoding = response.headers.get('Content-Encoding', '')
            
            if content_encoding:
                logger.info(f"  🔓 Decoding {content_encoding} response...")
            
            # If it's gzip
            if 'gzip' in content_encoding:
                try:
                    return gzip.decompress(response.content).decode('utf-8', errors='ignore')
                except:
                    pass
            
            # If it's deflate
            if 'deflate' in content_encoding:
                try:
                    return zlib.decompress(response.content).decode('utf-8', errors='ignore')
                except:
                    try:
                        return zlib.decompress(response.content, -zlib.MAX_WBITS).decode('utf-8', errors='ignore')
                    except:
                        pass
            
            # Try brotli if available
            if 'br' in content_encoding:
                try:
                    import brotli
                    return brotli.decompress(response.content).decode('utf-8', errors='ignore')
                except ImportError:
                    logger.warning("  ⚠️ Brotli not installed, skipping...")
                except:
                    pass
            
            # Try to decode as UTF-8
            try:
                return response.text
            except:
                pass
            
            return response.text if response.text else str(response.content)
            
        except Exception as e:
            logger.error(f"  ❌ Decoding error: {str(e)}")
            return response.text if response.text else str(response.content)
    
    @lru_cache(maxsize=100)
    def get_m3u8_url(self, video_url):
        """Get M3U8 URL with proper decoding"""
        logger.info(f"🔍 Processing video URL: {video_url[:80]}...")
        
        if '#' in video_url:
            video_url = video_url.split('#')[0]
        
        # Try with session first
        session = self.ensure_session()
        if session:
            try:
                logger.info("📡 Attempt 1: Using authenticated session...")
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': BASE_URL,
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                response = session.get(video_url, timeout=15, headers=headers)
                logger.info(f"📡 Session GET Status: {response.status_code}")
                
                if response.status_code == 200:
                    html = self._decode_response(response)
                    if html:
                        m3u8 = self._extract_m3u8(html)
                        if m3u8:
                            logger.info("✅ Found M3U8 URL with session!")
                            return m3u8
            except Exception as e:
                logger.warning(f"⚠️ Session attempt failed: {str(e)}")
        
        # Try guest as fallback
        logger.info("🔄 Attempt 2: Trying guest fetch...")
        try:
            guest_session = requests.Session()
            guest_session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': BASE_URL,
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            response = guest_session.get(video_url, timeout=15)
            logger.info(f"📡 Guest Status: {response.status_code}")
            
            if response.status_code == 200:
                html = self._decode_response(response)
                if html:
                    m3u8 = self._extract_m3u8(html)
                    if m3u8:
                        logger.info("✅ Found M3U8 URL with guest!")
                        return m3u8
        except Exception as e:
            logger.warning(f"⚠️ Guest attempt failed: {str(e)}")
        
        logger.error("❌ Failed to find M3U8 URL with all attempts.")
        return None
    
    def _extract_m3u8(self, html_content):
        """Extract M3U8 URL from HTML content"""
        if not html_content:
            return None
        
        # Clean the content - remove null bytes and control characters
        html_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', html_content)
        
        # Look for M3U8 URLs in various formats
        patterns = [
            # Standard M3U8 URLs
            r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
            r'//[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            
            # With quotes
            r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'href\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            
            # JavaScript objects
            r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'file\s*:\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'source\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]
        
        found_urls = []
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    # Clean up the URL
                    m3u8_url = match.strip()
                    if '"' in m3u8_url:
                        m3u8_url = m3u8_url.split('"')[0]
                    if "'" in m3u8_url:
                        m3u8_url = m3u8_url.split("'")[0]
                    if '&amp;' in m3u8_url:
                        m3u8_url = m3u8_url.replace('&amp;', '&')
                    
                    # Add protocol if missing
                    if m3u8_url.startswith('//'):
                        m3u8_url = 'https:' + m3u8_url
                    
                    # Validate it's a proper URL
                    if m3u8_url.startswith('http') and '.m3u8' in m3u8_url:
                        found_urls.append(m3u8_url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in found_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        if unique_urls:
            logger.info(f"✅ Found {len(unique_urls)} M3U8 URLs")
            return unique_urls[0]  # Return the first one
        
        return None

# Initialize client
client = FaphouseClient()

# ============ FLASK APP ============

# HTML template for the main page with premium UI
MAIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Faphouse</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@300;400;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: #000000;
            font-family: "Unbounded", sans-serif;
            color: #f5f0e6;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0;
            margin: 0;
            overflow: hidden;
        }

        .app {
            width: 100%;
            height: 100vh;
            position: relative;
            overflow: hidden;
            background: #000000;
        }

        /* 18+ SPLASH SCREEN */
        .splash-overlay {
            position: fixed;
            inset: 0;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: #000000;
            transition: opacity 1.2s ease, visibility 1.2s ease;
        }

        .splash-overlay.hidden {
            opacity: 0;
            visibility: hidden;
            pointer-events: none;
        }

        .splash-content {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2.5rem;
        }

        .splash-18 {
            font-family: "Unbounded", sans-serif;
            font-size: 8rem;
            font-weight: 900;
            background: linear-gradient(135deg, #f5c518, #d4a800);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1;
            text-shadow: 0 0 80px rgba(245,197,24,0.05);
        }

        .splash-18 span {
            font-size: 3rem;
            display: block;
            font-weight: 300;
            letter-spacing: 0.3em;
            -webkit-text-fill-color: #3d3930;
            background: none;
            margin-top: 0.5rem;
        }

        .splash-btn {
            background: transparent;
            border: 2px solid rgba(245,197,24,0.1);
            padding: 0.8rem 3.5rem;
            font-family: "Unbounded", sans-serif;
            font-size: 0.7rem;
            color: #8a8477;
            cursor: pointer;
            transition: all 0.3s ease;
            letter-spacing: 0.3em;
            text-transform: uppercase;
            border-radius: 60px;
        }

        .splash-btn:hover {
            border-color: rgba(245,197,24,0.2);
            color: #f5f0e6;
            transform: scale(0.97);
        }

        .splash-sub {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.5rem;
            color: #1a1814;
            letter-spacing: 0.3em;
            text-transform: uppercase;
        }

        /* PAGE 1: PASTE */
        .page-paste {
            width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            position: relative;
            opacity: 0;
            transition: opacity 1.2s ease;
            padding: 2rem;
        }

        .page-paste.visible {
            opacity: 1;
        }

        .bg-glow {
            position: absolute;
            inset: 0;
            background: radial-gradient(ellipse at 50% 40%, rgba(245,197,24,0.02), transparent 70%);
            pointer-events: none;
        }

        .bg-grid {
            position: absolute;
            inset: 0;
            background-image: 
                linear-gradient(rgba(255,215,0,0.008) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,215,0,0.008) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
        }

        .brand-container {
            text-align: center;
            margin-bottom: 3rem;
            position: relative;
        }

        .brand-pulse {
            display: flex;
            align-items: baseline;
            gap: 0.1rem;
            font-family: "Unbounded", sans-serif;
            font-size: 6rem;
            font-weight: 900;
            line-height: 1;
            letter-spacing: -0.02em;
            position: relative;
        }

        .brand-pulse .fap {
            background: linear-gradient(135deg, #f5c518, #d4a800);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: pulseBlurSmooth 4s ease-in-out infinite;
            position: relative;
            display: inline-block;
        }

        @keyframes pulseBlurSmooth {
            0%, 100% {
                filter: blur(0px);
                text-shadow: 0 0 40px rgba(245,197,24,0.03);
                transform: scale(1);
            }
            30% {
                filter: blur(5px);
                text-shadow: 0 0 60px rgba(245,197,24,0.08);
                transform: scale(1.015);
            }
            50% {
                filter: blur(0px);
                text-shadow: 0 0 40px rgba(245,197,24,0.03);
                transform: scale(1);
            }
            80% {
                filter: blur(5px);
                text-shadow: 0 0 60px rgba(245,197,24,0.08);
                transform: scale(1.015);
            }
        }

        .brand-pulse .house {
            color: #f5f0e6;
            -webkit-text-fill-color: #f5f0e6;
            position: relative;
            display: inline-block;
        }

        .badge-18 {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.55rem;
            font-weight: 700;
            color: #f5c518;
            background: rgba(245,197,24,0.04);
            border: 1px solid rgba(245,197,24,0.06);
            padding: 0.05rem 0.5rem;
            border-radius: 20px;
            display: inline-block;
            margin-left: 0.3rem;
            vertical-align: middle;
            -webkit-text-fill-color: #f5c518;
            letter-spacing: 0.05em;
        }

        .brand-tagline {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.55rem;
            color: #3d3930;
            letter-spacing: 0.3em;
            text-transform: uppercase;
            margin-top: 0.8rem;
        }

        .input-area {
            width: 100%;
            max-width: 640px;
            position: relative;
        }

        .input-wrapper {
            display: flex;
            align-items: center;
            background: rgba(8,8,8,0.9);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-radius: 80px;
            padding: 0.2rem 0.2rem 0.2rem 2rem;
            border: 1px solid rgba(255,215,0,0.03);
            transition: all 0.3s ease;
        }

        .input-wrapper:focus-within {
            border-color: rgba(255,215,0,0.06);
        }

        .input-wrapper input {
            flex: 1;
            background: transparent;
            border: none;
            padding: 1rem 0.5rem 1rem 0;
            font-size: 0.8rem;
            font-family: "JetBrains Mono", monospace;
            color: #ece4d6;
            outline: none;
            font-weight: 300;
        }

        .input-wrapper input::placeholder {
            color: #3a362e;
            font-weight: 200;
        }

        .input-wrapper .btn-load {
            background: #f5c518;
            border: none;
            padding: 0.8rem 2.5rem;
            border-radius: 60px;
            font-family: "Unbounded", sans-serif;
            font-weight: 700;
            font-size: 0.65rem;
            color: #000000;
            cursor: pointer;
            transition: all 0.3s ease;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .input-wrapper .btn-load:hover {
            background: #ffd93d;
            transform: scale(0.96);
        }

        .input-example {
            margin-top: 1rem;
            text-align: center;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.5rem;
            color: #3a362e;
        }

        .input-example .example-link {
            color: #6b6558;
            cursor: pointer;
            transition: color 0.2s ease;
            border-bottom: 1px solid rgba(255,215,0,0.02);
        }

        .input-example .example-link:hover {
            color: #c4bbaa;
        }

        .paste-footer {
            position: absolute;
            bottom: 2rem;
            left: 0;
            right: 0;
            text-align: center;
            z-index: 10;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.45rem;
            color: #1a1814;
            letter-spacing: 0.3em;
            text-transform: uppercase;
        }

        @media (max-width: 900px) {
            .brand-pulse { font-size: 4rem; }
            .input-wrapper { flex-wrap: wrap; background: transparent; padding: 0; border: none; backdrop-filter: none; }
            .input-wrapper input { padding: 0.8rem 1.2rem; background: rgba(8,8,8,0.9); border-radius: 60px; border: 1px solid rgba(255,215,0,0.03); width: 100%; margin-bottom: 0.5rem; }
            .input-wrapper .btn-load { width: 100%; justify-content: center; }
            .splash-18 { font-size: 5rem; }
            .badge-18 { font-size: 0.45rem; padding: 0.02rem 0.4rem; }
        }

        @media (max-width: 500px) {
            .brand-pulse { font-size: 2.8rem; }
            .splash-18 { font-size: 3.5rem; }
            .splash-18 span { font-size: 1.5rem; }
            .badge-18 { font-size: 0.4rem; padding: 0.02rem 0.3rem; }
        }
    </style>
</head>
<body>
<div class="app" id="app">
    <!-- 18+ SPLASH -->
    <div class="splash-overlay" id="splashOverlay">
        <div class="splash-content">
            <div class="splash-18">
                18+
                <span>adult content</span>
            </div>
            <button class="splash-btn" id="enterBtn">enter</button>
            <div class="splash-sub">you must be 18 or older to continue</div>
        </div>
    </div>

    <!-- PAGE 1: PASTE -->
    <div class="page-paste" id="pagePaste">
        <div class="bg-glow"></div>
        <div class="bg-grid"></div>
        
        <div class="brand-container">
            <div class="brand-pulse">
                <span class="fap">FAP</span>
                <span class="house">HOUSE</span>
                <span class="badge-18">18+</span>
            </div>
            <div class="brand-tagline">player · zero latency</div>
        </div>

        <div class="input-area">
            <form method="GET" action="/play" style="width:100%;">
                <div class="input-wrapper">
                    <input type="text" name="url" id="videoUrlInput" placeholder="https://faphouse2.com/videos/..." spellcheck="false" autofocus value="{{ video_url or '' }}">
                    <button type="submit" class="btn-load">load</button>
                </div>
            </form>
            <div class="input-example">
                <span>try </span>
                <span class="example-link" onclick="document.getElementById('videoUrlInput').value='https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u'; document.querySelector('.input-wrapper form').submit();">https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u</span>
            </div>
        </div>
        <div class="paste-footer">premium · yellow black · faphouse</div>
    </div>
</div>

<script>
    document.getElementById('enterBtn').addEventListener('click', function() {
        document.getElementById('splashOverlay').classList.add('hidden');
        document.getElementById('pagePaste').classList.add('visible');
        document.getElementById('videoUrlInput').focus();
    });
</script>
</body>
</html>
"""

PLAYER_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Faphouse Player</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@300;400;700;900&family=JetBrains+Mono:wght@300;400;700&family=Playfair+Display:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
    <link href="https://vjs.zencdn.net/8.0.0/video-js.css" rel="stylesheet" />
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            background: #000000;
            font-family: "Unbounded", sans-serif;
            color: #f5f0e6;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0;
            margin: 0;
            overflow: hidden;
        }

        .app {
            width: 100%;
            height: 100vh;
            position: relative;
            overflow: hidden;
            background: #000000;
        }

        /* Velvet Noir Background */
        .velvet-bg {
            position: absolute;
            inset: 0;
            z-index: 1;
            background: 
                radial-gradient(ellipse at 50% 50%, rgba(245,197,24,0.02), transparent 70%),
                radial-gradient(ellipse at 30% 80%, rgba(245,197,24,0.01), transparent 50%),
                radial-gradient(ellipse at 70% 20%, rgba(245,197,24,0.01), transparent 50%);
        }

        .velvet-curtains {
            position: absolute;
            inset: 0;
            z-index: 2;
            pointer-events: none;
            overflow: hidden;
        }

        .velvet-curtains .curtain {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 15%;
        }

        .velvet-curtains .curtain-left {
            left: 0;
            background: linear-gradient(90deg, rgba(0,0,0,0.7), transparent);
        }

        .velvet-curtains .curtain-right {
            right: 0;
            background: linear-gradient(270deg, rgba(0,0,0,0.7), transparent);
        }

        /* Character */
        .player-bg {
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            pointer-events: none;
            z-index: 3;
        }

        .character-svg {
            width: 100%;
            height: 100%;
            max-width: 1000px;
            max-height: 1000px;
            opacity: 0.5;
        }

        /* Video player */
        .player-container {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 70%;
            max-width: 800px;
            aspect-ratio: 16/9;
            background: #000000;
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 
                0 0 0 1px rgba(245,197,24,0.02),
                0 40px 80px -20px rgba(0,0,0,0.95);
            z-index: 10;
            transition: all 0.5s ease;
        }

        #videoPlayer {
            width: 100%;
            height: 100%;
            display: block;
            background: #000000;
        }

        /* Vignette overlay */
        .vignette-overlay {
            position: absolute;
            inset: 0;
            z-index: 15;
            pointer-events: none;
            background: radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.4) 100%);
            transition: opacity 0.5s ease;
        }

        .vignette-overlay.disabled {
            opacity: 0;
        }

        /* After Dark */
        .app.after-dark .velvet-bg {
            opacity: 0.3;
        }

        .app.after-dark .player-container {
            box-shadow: 0 0 0 1px rgba(245,197,24,0.01), 0 40px 80px -20px rgba(0,0,0,0.98);
        }

        /* Discreet */
        .app.discreet .webplayer-controls button,
        .app.discreet .controls-panel button,
        .app.discreet .back-player {
            opacity: 0.3;
            transition: opacity 0.3s ease;
        }

        .app.discreet .webplayer-controls button:hover,
        .app.discreet .controls-panel button:hover,
        .app.discreet .back-player:hover {
            opacity: 0.8;
        }

        .app.discreet .brand-pulse .fap {
            animation: none;
            filter: blur(0px);
            opacity: 0.5;
        }

        .app.discreet .badge-18 {
            opacity: 0.3;
        }

        .app.discreet .character-svg {
            opacity: 0.2;
        }

        /* Webplayer controls */
        .webplayer-controls {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 1.5rem 2rem 2rem;
            background: linear-gradient(0deg, rgba(0,0,0,0.85) 0%, transparent 100%);
            display: flex;
            align-items: center;
            gap: 0.8rem;
            flex-wrap: wrap;
            opacity: 0;
            transition: opacity 0.4s ease;
            z-index: 20;
        }

        .player-container:hover .webplayer-controls,
        .player-container.show-controls .webplayer-controls {
            opacity: 1;
        }

        .webplayer-controls button {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,215,0,0.03);
            color: #c4bcae;
            padding: 0.4rem 0.8rem;
            border-radius: 40px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.5rem;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
        }

        .webplayer-controls button:hover {
            background: rgba(255,215,0,0.02);
            border-color: rgba(255,215,0,0.04);
            color: #f5f0e6;
        }

        .webplayer-controls .play-btn {
            background: rgba(245,197,24,0.04);
            border-color: rgba(245,197,24,0.04);
            padding: 0.4rem 1.2rem;
            font-family: "Unbounded", sans-serif;
            font-size: 0.6rem;
            color: #f5f0e6;
        }

        .webplayer-controls .play-btn:hover {
            background: rgba(245,197,24,0.06);
            border-color: rgba(245,197,24,0.06);
        }

        .webplayer-controls .seek-btn {
            font-size: 0.45rem;
            color: #6b6558;
        }

        .webplayer-controls .seek-btn:hover {
            color: #c4bcae;
        }

        .webplayer-controls .time {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.45rem;
            color: #5a5548;
            padding: 0.1rem 0.4rem;
            letter-spacing: 0.02em;
        }

        .webplayer-controls .spacer {
            flex: 1;
        }

        .webplayer-controls .fs-btn {
            font-size: 0.45rem;
            color: #4a453a;
            letter-spacing: 0.05em;
        }

        .webplayer-controls .fs-btn:hover {
            color: #8a8477;
        }

        /* Progress bar */
        .progress-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: rgba(255,255,255,0.03);
            z-index: 21;
            cursor: pointer;
        }

        .progress-bar .progress-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #f5c518, #d4a800);
            transition: width 0.1s ease;
        }

        /* Back button */
        .back-player {
            position: absolute;
            top: 1.5rem;
            left: 1.5rem;
            z-index: 30;
            background: rgba(0,0,0,0.4);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 0.3rem 1.2rem;
            border: 1px solid rgba(255,215,0,0.02);
            border-radius: 40px;
            color: #5a5548;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.45rem;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            text-decoration: none;
        }

        .back-player:hover {
            border-color: rgba(255,215,0,0.04);
            color: #a69f90;
        }

        /* Controls Panel */
        .controls-panel {
            position: absolute;
            bottom: 5.5rem;
            right: 1.5rem;
            z-index: 25;
            background: rgba(8,8,8,0.7);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255,215,0,0.02);
            border-radius: 16px;
            padding: 1rem 1.2rem;
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
            min-width: 160px;
            opacity: 0;
            transition: opacity 0.4s ease, transform 0.3s ease;
            transform: translateY(10px);
        }

        .controls-panel.visible {
            opacity: 1;
            transform: translateY(0);
        }

        .controls-panel .panel-label {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.45rem;
            color: #5a5548;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            border-bottom: 1px solid rgba(255,215,0,0.02);
            padding-bottom: 0.4rem;
        }

        .controls-panel .control-group {
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }

        .controls-panel .control-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.8rem;
        }

        .controls-panel .control-row span {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.4rem;
            color: #6b6558;
            letter-spacing: 0.02em;
        }

        .controls-panel .toggle-btn {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,215,0,0.03);
            color: #6b6558;
            padding: 0.15rem 0.6rem;
            border-radius: 30px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.35rem;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .controls-panel .toggle-btn.active {
            border-color: rgba(245,197,24,0.04);
            color: #f5c518;
        }

        .controls-panel .toggle-btn:hover {
            border-color: rgba(245,197,24,0.04);
            color: #c4bcae;
        }

        .controls-panel .slider-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .controls-panel .slider-group input[type="range"] {
            flex: 1;
            -webkit-appearance: none;
            height: 2px;
            background: rgba(255,215,0,0.04);
            outline: none;
            transition: background 0.2s ease;
        }

        .controls-panel .slider-group input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #f5c518;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .controls-panel .slider-group input[type="range"]::-webkit-slider-thumb:hover {
            transform: scale(1.2);
        }

        .controls-panel .slider-value {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.35rem;
            color: #4a453a;
            min-width: 20px;
            text-align: center;
        }

        .panel-toggle {
            position: absolute;
            bottom: 1.5rem;
            right: 1.5rem;
            z-index: 26;
            background: rgba(8,8,8,0.4);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255,215,0,0.02);
            border-radius: 50%;
            width: 36px;
            height: 36px;
            color: #5a5548;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .panel-toggle:hover {
            border-color: rgba(255,215,0,0.04);
            color: #c4bcae;
        }

        .panel-toggle.active {
            border-color: rgba(245,197,24,0.04);
            color: #f5c518;
        }

        .character-hint {
            position: absolute;
            bottom: 1.5rem;
            left: 2rem;
            z-index: 5;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.4rem;
            color: #1a1814;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            pointer-events: none;
        }

        /* Status dot */
        .status-dot {
            position: absolute;
            top: 1.5rem;
            right: 1.5rem;
            z-index: 30;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.4rem;
            color: #3d3930;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .status-dot .dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #4CAF50;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }

        @media (max-width: 900px) {
            .player-container { width: 92%; }
            .webplayer-controls { padding: 1rem 1.2rem 1.5rem; gap: 0.5rem; }
            .webplayer-controls button { font-size: 0.4rem; padding: 0.3rem 0.6rem; }
            .character-svg { opacity: 0.25; max-width: 600px; }
            .back-player { top: 1rem; left: 1rem; font-size: 0.4rem; padding: 0.2rem 1rem; }
            .controls-panel { bottom: 4.5rem; right: 0.8rem; min-width: 140px; padding: 0.8rem 1rem; }
            .panel-toggle { bottom: 1rem; right: 1rem; width: 32px; height: 32px; font-size: 0.7rem; }
            .velvet-curtains .curtain { width: 8%; }
            .status-dot { top: 1rem; right: 1rem; }
        }

        @media (max-width: 500px) {
            .webplayer-controls { padding: 0.8rem 1rem 1.2rem; gap: 0.3rem; }
            .webplayer-controls button { font-size: 0.35rem; padding: 0.2rem 0.4rem; }
            .webplayer-controls .play-btn { font-size: 0.5rem; padding: 0.2rem 0.8rem; }
            .player-container { width: 95%; border-radius: 12px; }
            .character-hint { display: none; }
            .character-svg { opacity: 0.15; max-width: 400px; }
            .controls-panel { bottom: 3.8rem; right: 0.5rem; min-width: 120px; padding: 0.6rem 0.8rem; }
            .controls-panel .panel-label { font-size: 0.35rem; }
            .controls-panel .control-row span { font-size: 0.35rem; }
            .controls-panel .toggle-btn { font-size: 0.3rem; padding: 0.1rem 0.4rem; }
            .panel-toggle { bottom: 0.8rem; right: 0.8rem; width: 28px; height: 28px; font-size: 0.6rem; }
            .velvet-curtains .curtain { width: 5%; }
        }
    </style>
</head>
<body>
<div class="app" id="app">
    <!-- Velvet Noir Background -->
    <div class="velvet-bg"></div>
    <div class="velvet-curtains">
        <div class="curtain curtain-left"></div>
        <div class="curtain curtain-right"></div>
    </div>

    <!-- Character -->
    <div class="player-bg">
        <svg class="character-svg" viewBox="0 0 1000 900" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g opacity="0.8">
                <ellipse cx="500" cy="500" rx="350" ry="400" fill="rgba(245,197,24,0.02)" filter="blur(40px)"/>
                <ellipse cx="500" cy="580" rx="130" ry="180" fill="rgba(245,197,24,0.02)" stroke="rgba(245,197,24,0.03)" stroke-width="1.5"/>
                <path d="M380 420 C380 390 420 370 500 370 C580 370 620 390 620 420" stroke="rgba(245,197,24,0.03)" stroke-width="1.5" fill="none"/>
                <circle cx="500" cy="310" r="85" fill="rgba(245,197,24,0.02)" stroke="rgba(245,197,24,0.03)" stroke-width="1.5"/>
                <path d="M415 300 C400 250 430 210 500 210 C570 210 600 250 585 300 C580 280 550 250 500 250 C450 250 420 280 415 300Z" fill="rgba(245,197,24,0.02)" stroke="rgba(245,197,24,0.03)" stroke-width="1"/>
                <path d="M410 310 C390 340 385 370 400 390" stroke="rgba(245,197,24,0.02)" stroke-width="1.5" fill="none"/>
                <path d="M590 310 C610 340 615 370 600 390" stroke="rgba(245,197,24,0.02)" stroke-width="1.5" fill="none"/>
                <path d="M400 430 C350 460 310 500 300 540 C290 580 310 610 350 610" stroke="rgba(245,197,24,0.04)" stroke-width="4" fill="none"/>
                <path d="M350 610 C360 620 380 625 400 620" stroke="rgba(245,197,24,0.04)" stroke-width="3" fill="none"/>
                <ellipse cx="390" cy="615" rx="20" ry="12" fill="rgba(245,197,24,0.02)" stroke="rgba(245,197,24,0.03)" stroke-width="1"/>
                <path d="M600 430 C650 460 690 500 700 540 C710 580 690 610 650 610" stroke="rgba(245,197,24,0.04)" stroke-width="4" fill="none"/>
                <path d="M650 610 C640 620 620 625 600 620" stroke="rgba(245,197,24,0.04)" stroke-width="3" fill="none"/>
                <ellipse cx="610" cy="615" rx="20" ry="12" fill="rgba(245,197,24,0.02)" stroke="rgba(245,197,24,0.03)" stroke-width="1"/>
                <rect x="280" y="480" width="440" height="240" rx="16" stroke="rgba(245,197,24,0.06)" stroke-width="2" fill="rgba(245,197,24,0.01)"/>
                <rect x="295" y="495" width="410" height="210" rx="10" fill="rgba(245,197,24,0.01)"/>
                <rect x="280" y="480" width="440" height="240" rx="16" stroke="rgba(245,197,24,0.02)" stroke-width="1" fill="none"/>
                <path d="M450 730 C440 780 430 820 420 840" stroke="rgba(245,197,24,0.02)" stroke-width="2" fill="none"/>
                <path d="M550 730 C560 780 570 820 580 840" stroke="rgba(245,197,24,0.02)" stroke-width="2" fill="none"/>
                <circle cx="200" cy="300" r="2" fill="rgba(245,197,24,0.015)"/>
                <circle cx="800" cy="280" r="3" fill="rgba(245,197,24,0.015)"/>
                <circle cx="180" cy="500" r="2" fill="rgba(245,197,24,0.015)"/>
                <circle cx="820" cy="520" r="2" fill="rgba(245,197,24,0.015)"/>
                <circle cx="350" cy="200" r="2" fill="rgba(245,197,24,0.015)"/>
                <circle cx="650" cy="190" r="3" fill="rgba(245,197,24,0.015)"/>
                <circle cx="250" cy="650" r="2" fill="rgba(245,197,24,0.015)"/>
                <circle cx="750" cy="640" r="2" fill="rgba(245,197,24,0.015)"/>
            </g>
        </svg>
    </div>

    <!-- Video Player -->
    <div class="player-container" id="playerContainer">
        <video id="videoPlayer" class="video-js vjs-default-skin" controls preload="auto" style="width:100%;height:100%;">
            <source src="{{ m3u8_url }}" type="application/x-mpegURL">
        </video>
        
        <!-- Vignette Overlay -->
        <div class="vignette-overlay" id="vignetteOverlay"></div>
        
        <!-- Progress Bar -->
        <div class="progress-bar" id="progressBar">
            <div class="progress-fill" id="progressFill"></div>
        </div>

        <!-- Webplayer Controls -->
        <div class="webplayer-controls" id="webControls">
            <button class="seek-btn" id="seekBack">−10</button>
            <button class="play-btn" id="playPauseBtn">▶</button>
            <button class="seek-btn" id="seekForward">+10</button>
            <span class="time" id="timeDisplay">0:00 / 0:00</span>
            <span class="spacer"></span>
            <button class="fs-btn" id="fullscreenBtn">full</button>
        </div>
    </div>

    <!-- Back Button -->
    <a href="/" class="back-player">← back</a>
    
    <!-- Status Dot -->
    <div class="status-dot">
        <span class="dot"></span>
        live
    </div>
    
    <div class="character-hint">velvet noir · premium cinema</div>

    <!-- Panel Toggle -->
    <button class="panel-toggle" id="panelToggle">⚙</button>

    <!-- Controls Panel -->
    <div class="controls-panel" id="controlsPanel">
        <div class="panel-label">cinema controls</div>
        
        <div class="control-group">
            <div class="control-row">
                <span>mood lighting</span>
                <div class="slider-group">
                    <input type="range" id="moodLighting" min="0" max="100" value="50">
                    <span class="slider-value" id="moodValue">50</span>
                </div>
            </div>
        </div>

        <div class="control-group">
            <div class="control-row">
                <span>vignette</span>
                <button class="toggle-btn active" id="vignetteToggle">on</button>
            </div>
            <div class="control-row">
                <span>after dark</span>
                <button class="toggle-btn" id="afterDarkToggle">off</button>
            </div>
            <div class="control-row">
                <span>discreet</span>
                <button class="toggle-btn" id="discreetToggle">off</button>
            </div>
        </div>
    </div>
</div>

<script src="https://vjs.zencdn.net/8.0.0/video.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize Video.js player
        var player = videojs('videoPlayer', {
            html5: {
                hls: {
                    enableLowInitialPlaylist: true,
                    smoothQualityChange: true,
                    overrideNative: true
                }
            },
            controls: false,
            autoplay: true,
            preload: 'auto'
        });

        // Get DOM elements
        const playPauseBtn = document.getElementById('playPauseBtn');
        const seekBack = document.getElementById('seekBack');
        const seekForward = document.getElementById('seekForward');
        const timeDisplay = document.getElementById('timeDisplay');
        const fullscreenBtn = document.getElementById('fullscreenBtn');
        const progressFill = document.getElementById('progressFill');
        const progressBar = document.getElementById('progressBar');
        const playerContainer = document.getElementById('playerContainer');

        // Controls Panel
        const panelToggle = document.getElementById('panelToggle');
        const controlsPanel = document.getElementById('controlsPanel');
        const moodLighting = document.getElementById('moodLighting');
        const moodValue = document.getElementById('moodValue');
        const vignetteToggle = document.getElementById('vignetteToggle');
        const afterDarkToggle = document.getElementById('afterDarkToggle');
        const discreetToggle = document.getElementById('discreetToggle');
        const vignetteOverlay = document.getElementById('vignetteOverlay');

        function formatTime(seconds) {
            if (isNaN(seconds) || !isFinite(seconds)) return '0:00';
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return `${m}:${s.toString().padStart(2, '0')}`;
        }

        function updateTimeDisplay() {
            const currentTime = player.currentTime();
            const duration = player.duration();
            if (duration) {
                timeDisplay.textContent = `${formatTime(currentTime)} / ${formatTime(duration)}`;
                const progress = (currentTime / duration) * 100;
                progressFill.style.width = progress + '%';
            } else {
                timeDisplay.textContent = '0:00 / 0:00';
                progressFill.style.width = '0%';
            }
        }

        // Play/Pause
        playPauseBtn.addEventListener('click', function() {
            if (player.paused()) {
                player.play();
                playPauseBtn.textContent = '⏸';
            } else {
                player.pause();
                playPauseBtn.textContent = '▶';
            }
        });

        // Seek
        seekBack.addEventListener('click', function() {
            player.currentTime(Math.max(0, player.currentTime() - 10));
        });
        seekForward.addEventListener('click', function() {
            player.currentTime(Math.min(player.duration() || 0, player.currentTime() + 10));
        });

        // Fullscreen
        fullscreenBtn.addEventListener('click', function() {
            const container = document.querySelector('.player-container');
            if (!document.fullscreenElement) {
                container.requestFullscreen?.();
            } else {
                document.exitFullscreen?.();
            }
        });

        // Progress bar click
        progressBar.addEventListener('click', function(e) {
            const rect = progressBar.getBoundingClientRect();
            const pos = (e.clientX - rect.left) / rect.width;
            player.currentTime(pos * player.duration());
        });

        // Video events
        player.on('timeupdate', updateTimeDisplay);
        player.on('loadedmetadata', updateTimeDisplay);
        player.on('play', function() { playPauseBtn.textContent = '⏸'; });
        player.on('pause', function() { playPauseBtn.textContent = '▶'; });
        player.on('ended', function() { playPauseBtn.textContent = '▶'; });

        // Show controls on hover/click
        playerContainer.addEventListener('mouseenter', function() {
            playerContainer.classList.add('show-controls');
        });
        playerContainer.addEventListener('mouseleave', function() {
            playerContainer.classList.remove('show-controls');
        });
        playerContainer.addEventListener('click', function() {
            playerContainer.classList.toggle('show-controls');
        });

        // ===== CONTROLS PANEL =====
        panelToggle.addEventListener('click', function() {
            controlsPanel.classList.toggle('visible');
            panelToggle.classList.toggle('active');
        });

        // Mood Lighting
        moodLighting.addEventListener('input', function() {
            const val = moodLighting.value;
            moodValue.textContent = val;
            const opacity = val / 100;
            const bg = document.querySelector('.velvet-bg');
            const warmColor = `radial-gradient(ellipse at 50% 50%, rgba(245,197,24,${0.02 * opacity}), transparent 70%),
                               radial-gradient(ellipse at 30% 80%, rgba(245,197,24,${0.015 * opacity}), transparent 50%),
                               radial-gradient(ellipse at 70% 20%, rgba(245,197,24,${0.015 * opacity}), transparent 50%)`;
            bg.style.background = warmColor;
        });

        // Vignette Toggle
        vignetteToggle.addEventListener('click', function() {
            vignetteToggle.classList.toggle('active');
            const isOn = vignetteToggle.classList.contains('active');
            vignetteToggle.textContent = isOn ? 'on' : 'off';
            vignetteOverlay.classList.toggle('disabled', !isOn);
        });

        // After Dark Toggle
        afterDarkToggle.addEventListener('click', function() {
            afterDarkToggle.classList.toggle('active');
            const isOn = afterDarkToggle.classList.contains('active');
            afterDarkToggle.textContent = isOn ? 'on' : 'off';
            document.getElementById('app').classList.toggle('after-dark', isOn);
        });

        // Discreet Toggle
        discreetToggle.addEventListener('click', function() {
            discreetToggle.classList.toggle('active');
            const isOn = discreetToggle.classList.contains('active');
            discreetToggle.textContent = isOn ? 'on' : 'off';
            document.getElementById('app').classList.toggle('discreet', isOn);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.key === ' ' || e.key === 'Space') { e.preventDefault(); playPauseBtn.click(); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); seekBack.click(); }
            if (e.key === 'ArrowRight') { e.preventDefault(); seekForward.click(); }
            if (e.key === 'f' || e.key === 'F') { e.preventDefault(); fullscreenBtn.click(); }
        });

        // Initial update
        updateTimeDisplay();
    });
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(MAIN_PAGE_HTML, video_url=None)

@app.route('/play')
def play_video():
    video_url = request.args.get('url')
    
    if not video_url:
        return render_template_string(MAIN_PAGE_HTML, video_url=None)
    
    if '#' in video_url:
        video_url = video_url.split('#')[0]
    
    try:
        logger.info(f"🎬 Play request for: {video_url}")
        m3u8_url = client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return render_template_string(PLAYER_PAGE_HTML, m3u8_url=m3u8_url)
        else:
            return render_template_string("""
                <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                    <div style="max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #ff4444;">Could not find M3U8 URL</h2>
                        <p style="color: #888; margin: 20px 0;">The video might be unavailable or blocked in your region.</p>
                        <a href="/" style="color: #f5c518; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">← Go Home</a>
                    </div>
                </div>
            """)
    except Exception as e:
        logger.error(f"❌ Play error: {str(e)}")
        return render_template_string("""
            <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                <div style="max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #ff4444;">Error</h2>
                    <p style="color: #888; margin: 20px 0;">{{ error }}</p>
                    <a href="/" style="color: #f5c518; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">← Go Home</a>
                </div>
            </div>
        """, error=str(e))

@app.route('/api/m3u8')
def get_m3u8():
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    try:
        if '#' in video_url:
            video_url = video_url.split('#')[0]
            
        m3u8_url = client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return jsonify({
                "success": True,
                "m3u8_url": m3u8_url,
                "video_url": video_url
            })
        else:
            return jsonify({
                "success": False,
                "error": "No M3U8 URL found"
            }), 404
    except Exception as e:
        logger.error(f"❌ API error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/status')
def status():
    return jsonify({
        "status": "online",
        "logged_in": client.logged_in,
        "session_created": client.session_created,
        "cache_info": client.get_m3u8_url.cache_info()._asdict()
    })

# ============ FOR VERCEL ============
def handler(request, context):
    return app(request.environ, context)

# ============ MAIN ============
if __name__ == "__main__":
    print(f"""
{'='*70}
🎬 Faphouse Player API (Vercel Ready - Working!)
{'='*70}

✅ Features:
  • Properly decodes compressed (brotli) responses
  • Finds M3U8 URLs reliably
  • LRU caching for fast responses
  • Works on Vercel serverless
  • Premium Velvet Noir UI with 18+ splash
  • Girl character holding the player
  • Mood lighting, vignette, after dark, discreet modes

📌 Endpoints:
  📺 /play?url=VIDEO_URL     - Watch video with premium UI
  📡 /api/m3u8?url=VIDEO_URL - Get M3U8 URL
  📊 /api/status             - Check status

🔐 Credentials:
  EMAIL: {EMAIL[:5]}... 
  PASSWORD: {'*' * 8}
{'='*70}
""")
    
    print("🚀 Starting server for local testing...")
    app.run(host='0.0.0.0', port=5000, debug=True)
