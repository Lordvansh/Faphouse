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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://faphouse2.com"
EMAIL = os.environ.get('EMAIL', 'rockstarga69@gmail.com')
PASSWORD = os.environ.get('PASSWORD', 'Jaiisbeast@1')
CACHE_DURATION = 300

class FaphouseClient:
    def __init__(self):
        self.session = None
        self.logged_in = False
        self.session_created = False
        
    def ensure_session(self):
        if not self.session or not self.logged_in:
            logger.info("Creating new session...")
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
        logger.info(f"Attempting login with email: {EMAIL[:5]}...")
        
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
            logger.info("Getting initial page...")
            init_res = self.session.get(BASE_URL, timeout=10)
            logger.info(f"Initial page status: {init_res.status_code}")
            
            payload = {
                "login": EMAIL,
                "password": PASSWORD,
                "rememberMe": "1",
                "recaptcha": "",
                "trackingParamsBag": "eyJwcm9tb19pZCI6IiIsInZpZGVvX2lkIjpudWxsLCJzdHVkaW9faWQiOm51bGwsInByb2R1Y2VyX2lkIjpudWxsLCJvcmllbnRhdGlvbiI6InN0cmFpZ2h0IiwibWxfcGFnZSI6Im1haW5fcGFnZSIsIm1sX3BhZ2VfdmFsdWVfaWQiOm51bGwsIm1sX3BhZ2VfdmFsdWUiOm51bGwsIm1sX3BhZ2VfbnVtYmVyIjpudWxsLCJtbF9yZWZfcGFnZV92YWx1ZV9pZCI6bnVsbCwibWxfcmVmX3BhZ2VfdmFsdWUiOiIiLCJtbF9yZWZfcGFnZV9udW1iZXIiOm51bGwsIm1sX3JlZl9wYWdlIjoiZGlyZWN0In0="
            }
            
            logger.info("Sending login request...")
            login_res = self.session.post(
                f"{BASE_URL}/api/auth/signin",
                json=payload,
                timeout=15
            )
            
            logger.info(f"Login response status: {login_res.status_code}")
            
            if login_res.status_code == 200:
                try:
                    data = login_res.json()
                    if data.get('success') or data.get('data'):
                        self.logged_in = True
                        logger.info("Login successful!")
                        return True
                except:
                    pass
                
                if len(self.session.cookies) > 0:
                    self.logged_in = True
                    logger.info("Login successful (session established)!")
                    return True
            
            self.logged_in = False
            return False
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            self.logged_in = False
            return False
    
    def _decode_response(self, response):
        try:
            content_encoding = response.headers.get('Content-Encoding', '')
            
            if content_encoding:
                logger.info(f"Decoding {content_encoding} response...")
            
            if 'gzip' in content_encoding:
                try:
                    return gzip.decompress(response.content).decode('utf-8', errors='ignore')
                except:
                    pass
            
            if 'deflate' in content_encoding:
                try:
                    return zlib.decompress(response.content).decode('utf-8', errors='ignore')
                except:
                    try:
                        return zlib.decompress(response.content, -zlib.MAX_WBITS).decode('utf-8', errors='ignore')
                    except:
                        pass
            
            if 'br' in content_encoding:
                try:
                    import brotli
                    return brotli.decompress(response.content).decode('utf-8', errors='ignore')
                except ImportError:
                    logger.warning("Brotli not installed, skipping...")
                except:
                    pass
            
            try:
                return response.text
            except:
                pass
            
            return response.text if response.text else str(response.content)
            
        except Exception as e:
            logger.error(f"Decoding error: {str(e)}")
            return response.text if response.text else str(response.content)
    
    @lru_cache(maxsize=100)
    def get_m3u8_url(self, video_url):
        logger.info(f"Processing video URL: {video_url[:80]}...")
        
        if '#' in video_url:
            video_url = video_url.split('#')[0]
        
        session = self.ensure_session()
        if session:
            try:
                logger.info("Attempt 1: Using authenticated session...")
                
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
                logger.info(f"Session GET Status: {response.status_code}")
                
                if response.status_code == 200:
                    html = self._decode_response(response)
                    if html:
                        m3u8 = self._extract_m3u8(html)
                        if m3u8:
                            logger.info("Found M3U8 URL with session!")
                            return m3u8
            except Exception as e:
                logger.warning(f"Session attempt failed: {str(e)}")
        
        logger.info("Attempt 2: Trying guest fetch...")
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
            logger.info(f"Guest Status: {response.status_code}")
            
            if response.status_code == 200:
                html = self._decode_response(response)
                if html:
                    m3u8 = self._extract_m3u8(html)
                    if m3u8:
                        logger.info("Found M3U8 URL with guest!")
                        return m3u8
        except Exception as e:
            logger.warning(f"Guest attempt failed: {str(e)}")
        
        logger.error("Failed to find M3U8 URL with all attempts.")
        return None
    
    def _extract_m3u8(self, html_content):
        if not html_content:
            return None
        
        html_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', html_content)
        
        patterns = [
            r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
            r'//[^\s"\'<>]+\.m3u8[^\s"\'<>]*',
            r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'href\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
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
                    m3u8_url = match.strip()
                    if '"' in m3u8_url:
                        m3u8_url = m3u8_url.split('"')[0]
                    if "'" in m3u8_url:
                        m3u8_url = m3u8_url.split("'")[0]
                    if '&amp;' in m3u8_url:
                        m3u8_url = m3u8_url.replace('&amp;', '&')
                    
                    if m3u8_url.startswith('//'):
                        m3u8_url = 'https:' + m3u8_url
                    
                    if m3u8_url.startswith('http') and '.m3u8' in m3u8_url:
                        found_urls.append(m3u8_url)
        
        seen = set()
        unique_urls = []
        for url in found_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        if unique_urls:
            logger.info(f"Found {len(unique_urls)} M3U8 URLs")
            return unique_urls[0]
        
        return None

client = FaphouseClient()

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
        * { margin: 0; padding: 0; box-sizing: border-box; }
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
        .splash-overlay.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
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
        .page-paste.visible { opacity: 1; }
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
            0%, 100% { filter: blur(0px); text-shadow: 0 0 40px rgba(245,197,24,0.03); transform: scale(1); }
            30% { filter: blur(5px); text-shadow: 0 0 60px rgba(245,197,24,0.08); transform: scale(1.015); }
            50% { filter: blur(0px); text-shadow: 0 0 40px rgba(245,197,24,0.03); transform: scale(1); }
            80% { filter: blur(5px); text-shadow: 0 0 60px rgba(245,197,24,0.08); transform: scale(1.015); }
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
        .input-wrapper:focus-within { border-color: rgba(255,215,0,0.06); }
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
        .input-wrapper input::placeholder { color: #3a362e; font-weight: 200; }
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
        .input-wrapper .btn-load:hover { background: #ffd93d; transform: scale(0.96); }
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
        .input-example .example-link:hover { color: #c4bbaa; }
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
    <div class="splash-overlay" id="splashOverlay">
        <div class="splash-content">
            <div class="splash-18">18+<span>adult content</span></div>
            <button class="splash-btn" id="enterBtn">enter</button>
            <div class="splash-sub">you must be 18 or older to continue</div>
        </div>
    </div>
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
            <form method="GET" action="/play" style="width:100%;" id="urlForm">
                <div class="input-wrapper">
                    <input type="text" name="url" id="videoUrlInput" placeholder="https://faphouse2.com/videos/..." spellcheck="false" value="{{ video_url or '' }}">
                    <button type="submit" class="btn-load">load</button>
                </div>
            </form>
            <div class="input-example">
                <span>try </span>
                <span class="example-link" id="exampleLink">https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u</span>
            </div>
        </div>
        <div class="paste-footer">premium · yellow black · faphouse</div>
    </div>
</div>
<script>
    document.getElementById('enterBtn').addEventListener('click', function() {
        document.getElementById('splashOverlay').classList.add('hidden');
        document.getElementById('pagePaste').classList.add('visible');
    });
    document.getElementById('videoUrlInput').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.getElementById('urlForm').submit();
        }
    });
    document.getElementById('exampleLink').addEventListener('click', function() {
        document.getElementById('videoUrlInput').value = this.textContent;
        document.getElementById('urlForm').submit();
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Faphouse Player</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@300;400;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
    <link href="https://vjs.zencdn.net/8.0.0/video-js.css" rel="stylesheet" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: #0a0a0a;
            font-family: "Unbounded", sans-serif;
            color: #f5f0e6;
            height: 100vh;
            width: 100vw;
            overflow: hidden;
            position: fixed;
            top: 0;
            left: 0;
            margin: 0;
            padding: 0;
        }
        .app {
            width: 100vw;
            height: 100vh;
            position: relative;
            background: #0a0a0a;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .video-wrapper {
            position: relative;
            width: 90%;
            max-width: 900px;
            aspect-ratio: 16/9;
            background: #000000;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 0 0 1px rgba(255,215,0,0.02), 0 20px 60px rgba(0,0,0,0.9);
        }
        #player {
            width: 100%;
            height: 100%;
            display: block;
            background: #000000;
        }
        .header {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            z-index: 15;
            padding: 1rem 1.5rem;
            background: linear-gradient(180deg, rgba(0,0,0,0.7) 0%, transparent 100%);
            display: flex;
            align-items: center;
            justify-content: space-between;
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        }
        .header.visible { opacity: 1; pointer-events: auto; }
        .header-brand { display: flex; align-items: baseline; gap: 0.2rem; }
        .header-brand .fap {
            font-family: "Unbounded", sans-serif;
            font-size: 0.9rem;
            font-weight: 900;
            background: linear-gradient(135deg, #f5c518, #d4a800);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-brand .house {
            font-family: "Unbounded", sans-serif;
            font-size: 0.9rem;
            font-weight: 900;
            color: #f5f0e6;
        }
        .header-badge {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.4rem;
            font-weight: 700;
            color: #f5c518;
            background: rgba(245,197,24,0.04);
            border: 1px solid rgba(245,197,24,0.06);
            padding: 0.02rem 0.4rem;
            border-radius: 20px;
            letter-spacing: 0.05em;
            margin-left: 0.2rem;
        }
        .header-status {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.35rem;
            color: rgba(255,255,255,0.2);
            letter-spacing: 0.05em;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }
        .header-status .dot {
            width: 4px;
            height: 4px;
            border-radius: 50%;
            background: #f5c518;
            animation: pulse 1.5s infinite;
            display: inline-block;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
        .back-btn {
            background: rgba(255,255,255,0.02);
            border: 1px solid rgba(255,255,255,0.03);
            color: rgba(255,255,255,0.3);
            padding: 0.15rem 0.8rem;
            border-radius: 30px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.4rem;
            cursor: pointer;
            transition: all 0.2s ease;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            text-decoration: none;
            touch-action: manipulation;
            min-height: 24px;
            display: flex;
            align-items: center;
        }
        .back-btn:hover { background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.6); }
        .center-play {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 12;
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: rgba(0,0,0,0.5);
            border: 2px solid rgba(255,255,255,0.08);
            color: rgba(255,255,255,0.6);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            opacity: 0;
            pointer-events: none;
        }
        .center-play.visible { opacity: 1; pointer-events: auto; }
        .center-play:hover {
            background: rgba(255,255,255,0.05);
            border-color: rgba(255,215,0,0.1);
            transform: translate(-50%, -50%) scale(1.05);
        }
        .center-play:active { transform: translate(-50%, -50%) scale(0.92); }
        .center-play svg { width: 28px; height: 28px; fill: currentColor; margin-left: 4px; }
        .controls-wrapper {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 20;
            padding: 0 1.2rem 1.2rem 1.2rem;
            background: linear-gradient(0deg, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.1) 70%, transparent 100%);
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .controls-wrapper.visible { opacity: 1; }
        .progress-section { width: 100%; padding: 0.3rem 0 0.2rem 0; }
        .progress-track {
            position: relative;
            width: 100%;
            height: 3px;
            background: rgba(255,255,255,0.1);
            border-radius: 2px;
            cursor: pointer;
            transition: height 0.2s ease;
        }
        .progress-track:hover { height: 5px; }
        .progress-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #f5c518, #d4a800);
            border-radius: 2px;
            position: relative;
            transition: width 0.1s ease;
        }
        .progress-fill::after {
            content: '';
            position: absolute;
            right: -4px;
            top: -3px;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #f5c518;
            opacity: 0;
            transition: opacity 0.2s ease;
            box-shadow: 0 0 15px rgba(245,197,24,0.2);
        }
        .progress-track:hover .progress-fill::after,
        .progress-track.touching .progress-fill::after { opacity: 1; }
        .controls-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.2rem 0;
            gap: 0.3rem;
        }
        .controls-row button {
            background: transparent;
            border: none;
            color: rgba(255,255,255,0.5);
            padding: 0.2rem 0.4rem;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.55rem;
            cursor: pointer;
            transition: all 0.15s ease;
            letter-spacing: 0.02em;
            border-radius: 30px;
            min-height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            touch-action: manipulation;
        }
        .controls-row button:active { transform: scale(0.92); color: #ffffff; }
        .controls-row .play-btn {
            font-family: "Unbounded", sans-serif;
            font-size: 0.6rem;
            color: #ffffff;
            padding: 0.2rem 1.2rem;
            border: 1px solid rgba(255,255,255,0.04);
            border-radius: 30px;
            min-width: 54px;
            background: rgba(255,255,255,0.01);
        }
        .controls-row .play-btn:hover {
            background: rgba(255,255,255,0.03);
            border-color: rgba(255,255,255,0.06);
        }
        .controls-row .play-btn:active {
            background: rgba(255,215,0,0.04);
            border-color: rgba(255,215,0,0.06);
            transform: scale(0.95);
        }
        .controls-row .seek-btn {
            font-size: 0.45rem;
            color: rgba(255,255,255,0.3);
            padding: 0.15rem 0.3rem;
            min-height: 24px;
        }
        .controls-row .seek-btn:hover { color: rgba(255,255,255,0.7); }
        .controls-row .time-display {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.45rem;
            color: rgba(255,255,255,0.25);
            padding: 0.1rem 0.3rem;
            letter-spacing: 0.02em;
            min-width: 60px;
            text-align: center;
            font-variant-numeric: tabular-nums;
        }
        .controls-row .fs-btn {
            font-size: 0.45rem;
            color: rgba(255,255,255,0.25);
            padding: 0.15rem 0.4rem;
            letter-spacing: 0.05em;
            min-height: 24px;
        }
        .controls-row .fs-btn:hover { color: rgba(255,255,255,0.6); }
        .click-overlay {
            position: absolute;
            inset: 0;
            z-index: 10;
            cursor: pointer;
        }
        @media (max-width: 700px) {
            .video-wrapper { width: 96%; border-radius: 8px; }
            .header { padding: 0.6rem 1rem; }
            .header-brand .fap, .header-brand .house { font-size: 0.75rem; }
            .header-badge { font-size: 0.35rem; padding: 0.02rem 0.3rem; }
            .controls-wrapper { padding: 0 0.8rem 0.8rem 0.8rem; }
            .controls-row button { font-size: 0.45rem; min-height: 24px; padding: 0.15rem 0.3rem; }
            .controls-row .play-btn { font-size: 0.5rem; padding: 0.15rem 0.8rem; min-width: 44px; }
            .controls-row .time-display { font-size: 0.38rem; min-width: 50px; }
            .controls-row .seek-btn { font-size: 0.38rem; }
            .controls-row .fs-btn { font-size: 0.38rem; }
            .center-play { width: 50px; height: 50px; }
            .center-play svg { width: 22px; height: 22px; }
            .back-btn { font-size: 0.35rem; padding: 0.1rem 0.6rem; min-height: 20px; }
            .progress-section { padding: 0.2rem 0 0.1rem 0; }
        }
        @media (max-width: 450px) {
            .center-play { width: 44px; height: 44px; }
            .center-play svg { width: 18px; height: 18px; }
            .controls-row .play-btn { font-size: 0.45rem; padding: 0.12rem 0.6rem; min-width: 38px; }
            .controls-row .time-display { font-size: 0.35rem; min-width: 44px; }
        }
        @media (orientation: landscape) and (max-height: 500px) {
            .video-wrapper { width: 85%; max-height: 85vh; }
            .header { padding: 0.4rem 1rem; }
            .header-brand .fap, .header-brand .house { font-size: 0.7rem; }
            .controls-wrapper { padding: 0 1rem 0.6rem 1rem; }
            .controls-row button { font-size: 0.4rem; min-height: 20px; padding: 0.1rem 0.25rem; }
            .controls-row .play-btn { font-size: 0.45rem; padding: 0.1rem 0.6rem; min-width: 36px; }
            .controls-row .time-display { font-size: 0.35rem; min-width: 40px; }
            .center-play { width: 40px; height: 40px; }
            .center-play svg { width: 16px; height: 16px; }
            .back-btn { font-size: 0.3rem; padding: 0.1rem 0.4rem; min-height: 16px; }
            .progress-section { padding: 0.15rem 0 0.05rem 0; }
            .progress-track { height: 2px; }
        }
    </style>
</head>
<body>
<div class="app">
    <div class="video-wrapper" id="videoWrapper">
        <video id="player" class="video-js vjs-default-skin" controls autoplay preload="auto" style="width:100%;height:100%;">
            <source src="{{ m3u8_url }}" type="application/x-mpegURL">
        </video>
        <div class="header" id="header">
            <div class="header-brand">
                <span class="fap">FAP</span>
                <span class="house">HOUSE</span>
                <span class="header-badge">18+</span>
            </div>
            <div style="display:flex; align-items:center; gap:0.6rem;">
                <span class="header-status"><span class="dot"></span> live</span>
                <a href="/" class="back-btn">back</a>
            </div>
        </div>
        <button class="center-play" id="centerPlayBtn">
            <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
        </button>
        <div class="click-overlay" id="clickOverlay"></div>
        <div class="controls-wrapper" id="controlsWrapper">
            <div class="progress-section">
                <div class="progress-track" id="progressTrack">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
            </div>
            <div class="controls-row">
                <button class="seek-btn" id="seekBack">-10</button>
                <button class="play-btn" id="playPauseBtn">play</button>
                <span class="time-display" id="timeDisplay">0:00 / 0:00</span>
                <button class="seek-btn" id="seekForward">+10</button>
                <button class="fs-btn" id="fullscreenBtn">full</button>
            </div>
        </div>
    </div>
</div>
<script src="https://vjs.zencdn.net/8.0.0/video.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {
        var player = videojs('player', {
            html5: { hls: { enableLowInitialPlaylist: true, smoothQualityChange: true, overrideNative: true } },
            controls: false,
            autoplay: true,
            preload: 'auto'
        });
        const centerPlayBtn = document.getElementById('centerPlayBtn');
        const playPauseBtn = document.getElementById('playPauseBtn');
        const seekBack = document.getElementById('seekBack');
        const seekForward = document.getElementById('seekForward');
        const timeDisplay = document.getElementById('timeDisplay');
        const fullscreenBtn = document.getElementById('fullscreenBtn');
        const progressFill = document.getElementById('progressFill');
        const progressTrack = document.getElementById('progressTrack');
        const controlsWrapper = document.getElementById('controlsWrapper');
        const header = document.getElementById('header');
        const clickOverlay = document.getElementById('clickOverlay');
        const videoWrapper = document.getElementById('videoWrapper');
        function formatTime(seconds) {
            if (isNaN(seconds) || !isFinite(seconds)) return '0:00';
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            return m + ':' + s.toString().padStart(2, '0');
        }
        function updateTimeDisplay() {
            const currentTime = player.currentTime();
            const duration = player.duration();
            if (duration) {
                timeDisplay.textContent = formatTime(currentTime) + ' / ' + formatTime(duration);
                progressFill.style.width = ((currentTime / duration) * 100) + '%';
            } else {
                timeDisplay.textContent = '0:00 / 0:00';
                progressFill.style.width = '0%';
            }
        }
        function toggleControls(show) {
            controlsWrapper.classList.toggle('visible', show);
            header.classList.toggle('visible', show);
        }
        function toggleCenterPlay(show) {
            centerPlayBtn.classList.toggle('visible', show);
        }
        let controlsVisible = true;
        let controlsTimeout;
        function showControls() {
            toggleControls(true);
            controlsVisible = true;
            clearTimeout(controlsTimeout);
        }
        function hideControlsDelayed() {
            clearTimeout(controlsTimeout);
            controlsTimeout = setTimeout(function() {
                if (!player.paused()) {
                    toggleControls(false);
                    controlsVisible = false;
                }
            }, 3000);
        }
        function togglePlayPause() {
            if (player.paused()) {
                player.play();
                playPauseBtn.textContent = 'pause';
                centerPlayBtn.classList.remove('visible');
                if (controlsVisible) hideControlsDelayed();
            } else {
                player.pause();
                playPauseBtn.textContent = 'play';
                centerPlayBtn.classList.add('visible');
                showControls();
                clearTimeout(controlsTimeout);
            }
        }
        clickOverlay.addEventListener('click', function() {
            togglePlayPause();
        });
        centerPlayBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            togglePlayPause();
        });
        playPauseBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            togglePlayPause();
        });
        seekBack.addEventListener('click', function(e) {
            e.stopPropagation();
            player.currentTime(Math.max(0, player.currentTime() - 10));
            showControls();
            if (!player.paused()) hideControlsDelayed();
        });
        seekForward.addEventListener('click', function(e) {
            e.stopPropagation();
            player.currentTime(Math.min(player.duration() || 0, player.currentTime() + 10));
            showControls();
            if (!player.paused()) hideControlsDelayed();
        });
        fullscreenBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (!document.fullscreenElement) {
                videoWrapper.requestFullscreen?.();
            } else {
                document.exitFullscreen?.();
            }
        });
        let isDragging = false;
        progressTrack.addEventListener('mousedown', function(e) {
            isDragging = true;
            const rect = progressTrack.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            player.currentTime(pos * player.duration());
            progressFill.style.width = (pos * 100) + '%';
            progressTrack.classList.add('touching');
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (isDragging) {
                const rect = progressTrack.getBoundingClientRect();
                const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                player.currentTime(pos * player.duration());
                progressFill.style.width = (pos * 100) + '%';
            }
        });
        document.addEventListener('mouseup', function() {
            if (isDragging) {
                isDragging = false;
                progressTrack.classList.remove('touching');
                showControls();
                if (!player.paused()) hideControlsDelayed();
            }
        });
        progressTrack.addEventListener('touchstart', function(e) {
            const touch = e.touches[0];
            const rect = progressTrack.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
            player.currentTime(pos * player.duration());
            progressFill.style.width = (pos * 100) + '%';
            progressTrack.classList.add('touching');
            e.preventDefault();
        }, { passive: false });
        progressTrack.addEventListener('touchmove', function(e) {
            const touch = e.touches[0];
            const rect = progressTrack.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
            player.currentTime(pos * player.duration());
            progressFill.style.width = (pos * 100) + '%';
            e.preventDefault();
        }, { passive: false });
        progressTrack.addEventListener('touchend', function() {
            progressTrack.classList.remove('touching');
            showControls();
            if (!player.paused()) hideControlsDelayed();
        });
        player.on('timeupdate', updateTimeDisplay);
        player.on('loadedmetadata', updateTimeDisplay);
        player.on('play', function() {
            playPauseBtn.textContent = 'pause';
            centerPlayBtn.classList.remove('visible');
            showControls();
            hideControlsDelayed();
        });
        player.on('pause', function() {
            playPauseBtn.textContent = 'play';
            centerPlayBtn.classList.add('visible');
            showControls();
            clearTimeout(controlsTimeout);
        });
        player.on('ended', function() {
            playPauseBtn.textContent = 'play';
            centerPlayBtn.classList.add('visible');
            showControls();
            clearTimeout(controlsTimeout);
        });
        document.addEventListener('keydown', function(e) {
            if (e.key === ' ' || e.key === 'Space') { e.preventDefault(); togglePlayPause(); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); seekBack.click(); }
            if (e.key === 'ArrowRight') { e.preventDefault(); seekForward.click(); }
            if (e.key === 'f' || e.key === 'F') { e.preventDefault(); fullscreenBtn.click(); }
        });
        clickOverlay.addEventListener('dblclick', function() {
            fullscreenBtn.click();
        });
        setTimeout(function() {
            showControls();
            if (player.paused()) {
                centerPlayBtn.classList.add('visible');
            } else {
                hideControlsDelayed();
            }
        }, 500);
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
        logger.info(f"Play request for: {video_url}")
        m3u8_url = client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return render_template_string(PLAYER_PAGE_HTML, m3u8_url=m3u8_url)
        else:
            return render_template_string("""
                <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                    <div style="max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #ff4444;">Could not find M3U8 URL</h2>
                        <p style="color: #888; margin: 20px 0;">The video might be unavailable or blocked in your region.</p>
                        <a href="/" style="color: #f5c518; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">Go Home</a>
                    </div>
                </div>
            """)
    except Exception as e:
        logger.error(f"Play error: {str(e)}")
        return render_template_string("""
            <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                <div style="max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #ff4444;">Error</h2>
                    <p style="color: #888; margin: 20px 0;">{{ error }}</p>
                    <a href="/" style="color: #f5c518; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">Go Home</a>
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
        logger.error(f"API error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/status')
def status():
    return jsonify({
        "status": "online",
        "logged_in": client.logged_in,
        "session_created": client.session_created,
        "cache_info": client.get_m3u8_url.cache_info()._asdict()
    })

def handler(request, context):
    return app(request.environ, context)

if __name__ == "__main__":
    print(f"""
{'='*70}
Faphouse Player API (Vercel Ready)
{'='*70}

Features:
  • Properly decodes compressed (brotli) responses
  • Finds M3U8 URLs reliably
  • LRU caching for fast responses
  • Works on Vercel serverless
  • Premium 18+ webplayer UI

Endpoints:
  /play?url=VIDEO_URL     - Watch video with premium UI
  /api/m3u8?url=VIDEO_URL - Get M3U8 URL
  /api/status             - Check status

Credentials:
  EMAIL: {EMAIL[:5]}... 
  PASSWORD: {'*' * 8}
{'='*70}
""")
    
    print("Starting server for local testing...")
    app.run(host='0.0.0.0', port=5000, debug=True)
