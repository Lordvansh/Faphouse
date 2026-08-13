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
import urllib.parse

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

class TeraboxDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
        }
        self.base_url = "https://terabox.beer"
        self.cache = {}

    def extract_video_id(self, url):
        patterns = [
            r'/s/([a-zA-Z0-9_-]+)',
            r'share\.com/s/([a-zA-Z0-9_-]+)',
            r'file\.com/s/([a-zA-Z0-9_-]+)',
            r'terafileshare\.com/s/([a-zA-Z0-9_-]+)',
            r'terabox\.com/s/([a-zA-Z0-9_-]+)',
            r'1024terabox\.com/s/([a-zA-Z0-9_-]+)',
            r'teraboxapp\.com/s/([a-zA-Z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def get_proxy_url(self, terabox_url):
        video_id = self.extract_video_id(terabox_url)
        if not video_id:
            return {"error": "Invalid or unsupported Terabox link. Please make sure you're using a valid Terabox share link."}

        cache_key = f"proxy_{terabox_url}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < CACHE_DURATION:
                logger.info("Returning cached proxy URL")
                return cached['data']

        try:
            encoded_url = urllib.parse.quote(terabox_url, safe='')
            api_url = f"{self.base_url}/api/terabox-new?link={encoded_url}"
            
            response = self.session.get(api_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                api_result = response.json()
                
                if isinstance(api_result, dict):
                    if api_result.get('error') and api_result.get('error') != False:
                        error_msg = api_result.get('error')
                        if isinstance(error_msg, str):
                            if "105" in error_msg:
                                return {"error": "The Terabox link is invalid or the video no longer exists. Please check the link and try again."}
                            elif "404" in error_msg:
                                return {"error": "Video not found. The link might be expired or removed."}
                            else:
                                return {"error": f"Terabox service error: {error_msg}. Please try again later."}
                        else:
                            return {"error": "Terabox service returned an error. Please try again later."}
                    
                    proxy_url = None
                    for field in ['proxy_url', 'download_link', 'fallback_url', 'stream_download_url']:
                        if field in api_result and api_result[field]:
                            proxy_url = api_result[field]
                            break
                    
                    if not proxy_url:
                        for key, value in api_result.items():
                            if isinstance(value, str) and value.startswith('http'):
                                if '.workers.dev' in value or 'proxy' in key.lower():
                                    proxy_url = value
                                    break
                    
                    if proxy_url:
                        result = {
                            "success": True,
                            "proxy_url": proxy_url,
                            "file_name": api_result.get('file_name', 'Unknown'),
                            "file_size": api_result.get('file_size', 'Unknown')
                        }
                        self.cache[cache_key] = {
                            'timestamp': datetime.now(),
                            'data': result
                        }
                        return result
                    else:
                        return {"error": "No video URL could be extracted from this Terabox link. The link might be private or unsupported."}
                else:
                    return {"error": "Invalid response from Terabox service. Please try again later."}
            elif response.status_code == 404:
                return {"error": "Terabox link not found. Please check if the link is correct."}
            elif response.status_code == 403:
                return {"error": "Access denied. The Terabox link might be private or restricted."}
            else:
                return {"error": f"Terabox service is currently unavailable (Status: {response.status_code}). Please try again later."}
                
        except requests.exceptions.Timeout:
            return {"error": "Connection to Terabox service timed out. Please try again."}
        except requests.exceptions.ConnectionError:
            return {"error": "Could not connect to Terabox service. Please check your internet connection."}
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {"error": "An unexpected error occurred while processing the Terabox link. Please try again."}

    def process_terabox_link(self, terabox_url):
        result = self.get_proxy_url(terabox_url)
        if result.get('error'):
            return result
        
        proxy_url = result['proxy_url']
        logger.info(f"Proxy URL: {proxy_url[:100]}...")
        
        return {
            "success": True,
            "video_url": proxy_url,
            "file_name": result.get('file_name', 'Unknown'),
            "file_size": result.get('file_size', 'Unknown'),
            "platform": "terabox"
        }

faphouse_client = FaphouseClient()
terabox_client = TeraboxDownloader()

# ============= HTML TEMPLATES =============

MAIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>HUB · Faphouse / Terabox</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@300;400;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #050507;
            --panel: #0b0b0f;
            --line: rgba(255,255,255,0.07);
            --txt: #e9e5d9;
            --dim: #5f5b66;
            --acc: #f5c518;
            --acc-strong: #ffd94a;
            --acc-soft: rgba(245,197,24,0.12);
            --acc-glow: rgba(245,197,24,0.16);
            --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
            --ease-inout: cubic-bezier(0.77, 0, 0.175, 1);
        }
        body[data-platform="terabox"] {
            --acc: #00b4d8;
            --acc-strong: #48cae4;
            --acc-soft: rgba(0,180,216,0.12);
            --acc-glow: rgba(0,180,216,0.16);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; }
        body {
            background: var(--bg);
            font-family: "JetBrains Mono", monospace;
            color: var(--txt);
            overflow: hidden;
            -webkit-font-smoothing: antialiased;
        }
        .app {
            position: relative;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            background:
                radial-gradient(ellipse at 50% 30%, rgba(255,255,255,0.015), transparent 60%),
                var(--bg);
        }
        .orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(100px);
            pointer-events: none;
        }
        .orb-a {
            top: -18%;
            left: -12%;
            width: 46vmax;
            height: 46vmax;
            background: radial-gradient(circle, rgba(245,197,24,0.05), transparent 65%);
            animation: driftA 26s ease-in-out infinite alternate;
        }
        .orb-b {
            bottom: -22%;
            right: -14%;
            width: 42vmax;
            height: 42vmax;
            background: radial-gradient(circle, rgba(0,180,216,0.05), transparent 65%);
            animation: driftB 30s ease-in-out infinite alternate;
        }
        @keyframes driftA { 0% { transform: translate(0,0); } 100% { transform: translate(6vmax, 5vmax); } }
        @keyframes driftB { 0% { transform: translate(0,0); } 100% { transform: translate(-6vmax, -4vmax); } }
        .bg-grid {
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.018) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.018) 1px, transparent 1px);
            background-size: 56px 56px;
            -webkit-mask-image: radial-gradient(ellipse at 50% 45%, #000 30%, transparent 78%);
            mask-image: radial-gradient(ellipse at 50% 45%, #000 30%, transparent 78%);
            pointer-events: none;
        }
        .scanlines {
            position: absolute;
            inset: 0;
            background-image: repeating-linear-gradient(0deg, rgba(255,255,255,0.008) 0 1px, transparent 1px 3px);
            pointer-events: none;
        }
        .bg-vignette {
            position: absolute;
            inset: 0;
            pointer-events: none;
            background: radial-gradient(ellipse at center, transparent 52%, rgba(0,0,0,0.5) 100%);
        }

        /* ===== HUD ===== */
        .hud {
            position: relative;
            z-index: 30;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.9rem 1.4rem;
            border-bottom: 1px solid var(--line);
            font-size: 0.58rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--dim);
            background: rgba(5,5,7,0.7);
            backdrop-filter: blur(10px);
        }
        .hud-left, .hud-right {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            min-width: 0;
        }
        .hud-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #3ddc84;
            box-shadow: 0 0 10px rgba(61,220,132,0.7);
            animation: blink 2.2s ease-in-out infinite;
            flex-shrink: 0;
        }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
        .hud-status { color: #9ef0c2; }
        .hud-tag { color: #3a3740; }
        .hud-sep { color: #26232b; }
        .hud-platform {
            color: var(--acc);
            transition: color 200ms var(--ease-out);
            white-space: nowrap;
        }
        .hud-clock { white-space: nowrap; }
        .hud-lib {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            background: transparent;
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: 0.35rem 0.8rem;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.55rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--dim);
            cursor: pointer;
            transition: border-color 200ms var(--ease-out), color 200ms var(--ease-out), transform 160ms var(--ease-out);
        }
        @media (hover: hover) and (pointer: fine) {
            .hud-lib:hover { border-color: rgba(255,255,255,0.22); color: var(--txt); }
        }
        .hud-lib:active { transform: scale(0.97); }
        .hud-lib.terabox-mode { border-color: rgba(0,180,216,0.35); color: #7fd8ee; }
        .hud-lib-count {
            color: var(--acc);
            font-weight: 700;
        }

        /* ===== STAGE ===== */
        .stage {
            position: relative;
            z-index: 20;
            flex: 1;
            min-height: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: clamp(1rem, 3vh, 2rem);
            padding: 1rem 1.4rem;
            opacity: 0;
            transition: opacity 600ms var(--ease-out);
        }
        .stage.armed { opacity: 1; }

        .stage-head {
            text-align: center;
            opacity: 0;
            animation: riseIn 500ms var(--ease-out) forwards;
            animation-delay: 40ms;
        }
        .stage-head .eyebrow {
            font-size: 0.5rem;
            letter-spacing: 0.32em;
            text-transform: uppercase;
            color: var(--dim);
        }
        .stage-head .eyebrow em {
            font-style: normal;
            color: var(--acc);
        }
        .stage-head h1 {
            font-family: "Unbounded", sans-serif;
            font-weight: 900;
            font-size: clamp(1.5rem, 4.5vw, 2.6rem);
            letter-spacing: -0.02em;
            margin-top: 0.5rem;
            background: linear-gradient(120deg, #f5f1e6, #8f8a99);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* ===== GATES ===== */
        .gates {
            display: flex;
            gap: clamp(0.8rem, 2.5vw, 1.6rem);
            width: 100%;
            max-width: 1060px;
            align-items: stretch;
        }
        .gate-wrap {
            flex: 1;
            min-width: 0;
            opacity: 0;
            transform: translateY(16px) scale(0.985);
            animation: gateIn 520ms var(--ease-out) forwards;
        }
        .gate-wrap:nth-child(1) { animation-delay: 120ms; }
        .gate-wrap:nth-child(2) { animation-delay: 200ms; }
        @keyframes gateIn { to { opacity: 1; transform: translateY(0) scale(1); } }

        .gate {
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            width: 100%;
            height: clamp(210px, 40vh, 360px);
            padding: 1.1rem 1.2rem;
            background:
                radial-gradient(600px circle at var(--sx, 50%) var(--sy, 0%), var(--acc-soft), transparent 45%),
                linear-gradient(180deg, rgba(255,255,255,0.02), transparent 55%),
                var(--panel);
            border: 1px solid var(--line);
            border-radius: 6px;
            color: var(--txt);
            text-align: left;
            cursor: pointer;
            font-family: inherit;
            overflow: hidden;
            will-change: transform;
            transition: border-color 250ms var(--ease-out), box-shadow 250ms var(--ease-out);
        }
        @media (hover: hover) and (pointer: fine) {
            .gate:hover { border-color: var(--acc-dim, var(--line)); }
        }
        .gate:focus-visible {
            outline: none;
            border-color: var(--acc);
        }
        .gate.selected {
            border-color: var(--acc-dim, var(--acc));
            box-shadow: 0 0 0 1px rgba(255,255,255,0.03), 0 0 42px var(--acc-glow), inset 0 0 60px rgba(255,255,255,0.01);
        }
        .gate.ping { animation: pingPulse 720ms var(--ease-out); }
        @keyframes pingPulse {
            0% { box-shadow: 0 0 0 0 var(--acc-glow), inset 0 0 60px rgba(255,255,255,0.01); }
            100% { box-shadow: 0 0 0 16px transparent, inset 0 0 60px rgba(255,255,255,0.01); }
        }
        .gate-corner {
            position: absolute;
            width: 14px;
            height: 14px;
            border-color: var(--acc);
            opacity: 0.9;
            transition: opacity 200ms var(--ease-out);
        }
        .gate-corner.tl { top: 6px; left: 6px; border-top: 2px solid; border-left: 2px solid; }
        .gate-corner.tr { top: 6px; right: 6px; border-top: 2px solid; border-right: 2px solid; }
        .gate-corner.bl { bottom: 6px; left: 6px; border-bottom: 2px solid; border-left: 2px solid; }
        .gate-corner.br { bottom: 6px; right: 6px; border-bottom: 2px solid; border-right: 2px solid; }

        .gate-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.55rem;
            letter-spacing: 0.2em;
            color: var(--dim);
        }
        .gate-index { color: var(--acc); font-weight: 700; }
        .gate-led {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #2a2730;
            transition: background 200ms var(--ease-out), box-shadow 200ms var(--ease-out);
        }
        .gate.selected .gate-led {
            background: var(--acc);
            box-shadow: 0 0 10px var(--acc);
            animation: blink 1.6s ease-in-out infinite;
        }
        .gate-word {
            font-family: "Unbounded", sans-serif;
            font-weight: 900;
            font-size: clamp(1.6rem, 4.2vw, 2.6rem);
            letter-spacing: 0.01em;
            line-height: 1;
            background: linear-gradient(120deg, var(--acc-strong), var(--acc));
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 0 18px var(--acc-glow));
        }
        .gate-tag {
            font-size: 0.5rem;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            color: var(--dim);
            margin-top: 0.45rem;
        }
        .gate-foot {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: 0.6rem;
            border-top: 1px solid var(--line);
            font-size: 0.5rem;
            letter-spacing: 0.2em;
            text-transform: uppercase;
        }
        .gate-status {
            color: var(--dim);
            transition: color 200ms var(--ease-out);
        }
        .gate.selected .gate-status { color: var(--acc); }
        .gate-arrow {
            color: var(--acc);
            font-size: 0.75rem;
            opacity: 0;
            transform: translateX(-6px);
            transition: opacity 200ms var(--ease-out), transform 200ms var(--ease-out);
        }
        .gate.selected .gate-arrow { opacity: 1; transform: translateX(0); }
        .gate-key {
            position: absolute;
            right: 1rem;
            bottom: 1rem;
            font-size: 0.45rem;
            color: #37343d;
            letter-spacing: 0.1em;
        }

        /* ===== DECK ===== */
        .deck {
            width: 100%;
            max-width: 760px;
            opacity: 0;
            transform: translateY(12px);
            animation: riseIn 500ms var(--ease-out) forwards;
            animation-delay: 260ms;
        }
        @keyframes riseIn { to { opacity: 1; transform: translateY(0); } }
        .deck-shell {
            display: flex;
            align-items: stretch;
            background: rgba(10,10,13,0.9);
            border: 1px solid var(--line);
            border-radius: 6px;
            padding: 0.35rem 0.35rem 0.35rem 1.1rem;
            transition: border-color 250ms var(--ease-out), box-shadow 250ms var(--ease-out);
        }
        .deck-shell:focus-within {
            border-color: var(--acc-dim, var(--acc));
            box-shadow: 0 0 30px var(--acc-glow);
        }
        .deck-prefix {
            display: flex;
            align-items: center;
            font-size: 0.8rem;
            color: var(--acc);
            font-weight: 700;
            letter-spacing: 0.05em;
            white-space: nowrap;
            transition: color 200ms var(--ease-out);
        }
        .deck-caret {
            display: flex;
            align-items: center;
            margin-left: 0.15rem;
            font-size: 0.8rem;
            color: var(--acc);
            animation: caret 1.05s steps(1) infinite;
        }
        @keyframes caret { 0%,100% { opacity: 1; } 50% { opacity: 0; } }
        .deck-input {
            flex: 1;
            min-width: 0;
            background: transparent;
            border: none;
            outline: none;
            padding: 0.9rem 0.8rem;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.78rem;
            color: var(--txt);
            caret-color: var(--acc);
        }
        .deck-input::placeholder { color: #3b3842; font-weight: 300; }
        .launch-btn {
            background: var(--acc);
            border: none;
            border-radius: 4px;
            padding: 0 2rem;
            font-family: "Unbounded", sans-serif;
            font-weight: 700;
            font-size: 0.62rem;
            letter-spacing: 0.12em;
            color: #000;
            cursor: pointer;
            position: relative;
            white-space: nowrap;
            transition: transform 160ms var(--ease-out), box-shadow 250ms var(--ease-out), background 250ms var(--ease-out);
        }
        @media (hover: hover) and (pointer: fine) {
            .launch-btn:hover { box-shadow: 0 0 30px var(--acc-glow); }
        }
        .launch-btn:active { transform: scale(0.97); }
        .launch-btn.loading {
            pointer-events: none;
            color: transparent;
            background: var(--acc);
        }
        .launch-btn.loading::after {
            content: '';
            position: absolute;
            inset: 0;
            margin: auto;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(0,0,0,0.25);
            border-top-color: #000;
            border-radius: 50%;
            animation: btnSpin 0.7s linear infinite;
        }
        @keyframes btnSpin { to { transform: rotate(360deg); } }
        .deck-hint {
            margin-top: 0.7rem;
            text-align: center;
            font-size: 0.48rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: #3b3842;
        }

        /* ===== TICKER ===== */
        .ticker {
            width: 100%;
            max-width: 1060px;
            overflow: hidden;
            border-top: 1px solid var(--line);
            padding-top: 0.8rem;
            opacity: 0;
            animation: riseIn 500ms var(--ease-out) forwards;
            animation-delay: 320ms;
        }
        .ticker-track {
            display: flex;
            width: max-content;
            animation: tickerScroll 46s linear infinite;
        }
        .ticker:hover .ticker-track { animation-play-state: paused; }
        @keyframes tickerScroll { to { transform: translateX(-50%); } }
        .ticker-group {
            display: flex;
            align-items: center;
            gap: 2.2rem;
            padding-right: 2.2rem;
            flex-shrink: 0;
        }
        .tick-label {
            font-size: 0.48rem;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: #3b3842;
        }
        .tick-link {
            font-size: 0.55rem;
            letter-spacing: 0.06em;
            text-decoration: none;
            color: #6f6a76;
            white-space: nowrap;
            transition: color 200ms var(--ease-out);
            cursor: pointer;
        }
        .tick-link.fap-link { color: rgba(245,197,24,0.55); }
        .tick-link.tera-link { color: rgba(0,180,216,0.55); }
        @media (hover: hover) and (pointer: fine) {
            .tick-link:hover { color: var(--txt); }
        }
        .tick-sep { color: #26232b; font-size: 0.6rem; }

        /* ===== TOAST ===== */
        #saveToast {
            position: fixed;
            bottom: 96px;
            left: 50%;
            transform: translate(-50%, 12px);
            background: rgba(10,10,13,0.92);
            border: 1px solid var(--acc-soft);
            padding: 0.5rem 1.3rem;
            border-radius: 4px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.55rem;
            letter-spacing: 0.1em;
            color: var(--acc);
            opacity: 0;
            pointer-events: none;
            z-index: 120;
            backdrop-filter: blur(10px);
            transition: opacity 220ms var(--ease-out), transform 220ms var(--ease-out);
        }
        #saveToast.show { opacity: 1; transform: translate(-50%, 0); }

        /* ===== LIBRARY SIDEBAR ===== */
        .library-sidebar-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.55);
            backdrop-filter: blur(3px);
            opacity: 0;
            visibility: hidden;
            transition: opacity 250ms var(--ease-out), visibility 250ms var(--ease-out);
            z-index: 90;
        }
        .library-sidebar-backdrop.open { opacity: 1; visibility: visible; }
        .library-sidebar {
            position: fixed;
            top: 0;
            right: 0;
            height: 100%;
            width: 360px;
            max-width: 92vw;
            background: #0a0a0e;
            border-left: 1px solid var(--line);
            z-index: 100;
            transform: translateX(105%);
            transition: transform 380ms var(--ease-inout);
            display: flex;
            flex-direction: column;
            padding: 1.2rem;
        }
        .library-sidebar.open { transform: translateX(0); }
        .library-sidebar-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--line);
            padding-bottom: 0.8rem;
        }
        .library-sidebar-title {
            font-size: 0.62rem;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: var(--txt);
        }
        .library-sidebar-title .count { color: var(--acc); }
        .library-sidebar-close {
            background: transparent;
            border: none;
            color: var(--dim);
            font-size: 1rem;
            cursor: pointer;
            padding: 0.2rem 0.4rem;
            transition: color 200ms var(--ease-out), transform 160ms var(--ease-out);
        }
        .library-sidebar-close:hover { color: var(--txt); }
        .library-sidebar-close:active { transform: scale(0.92); }
        .library-sidebar-actions {
            display: flex;
            gap: 0.5rem;
            margin: 0.9rem 0;
        }
        .library-sidebar-actions button {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.45rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--dim);
            background: transparent;
            border: 1px solid var(--line);
            padding: 0.35rem 0.8rem;
            border-radius: 4px;
            cursor: pointer;
            transition: border-color 200ms var(--ease-out), color 200ms var(--ease-out), transform 160ms var(--ease-out);
        }
        @media (hover: hover) and (pointer: fine) {
            .library-sidebar-actions button:hover { color: var(--txt); border-color: rgba(255,255,255,0.2); }
        }
        .library-sidebar-actions button:active { transform: scale(0.97); }
        .library-sidebar-actions button.clear:hover { color: #ff5c5c; border-color: rgba(255,92,92,0.3); }
        .library-list { flex: 1; overflow-y: auto; padding-right: 0.4rem; }
        .library-list::-webkit-scrollbar { width: 3px; }
        .library-list::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
        .library-list::-webkit-scrollbar-thumb { background: var(--acc-soft); border-radius: 3px; }
        .library-empty {
            text-align: center;
            padding: 2.4rem 0;
            color: #3b3842;
            font-size: 0.55rem;
            letter-spacing: 0.12em;
            line-height: 1.9;
        }
        .library-empty .empty-icon { font-size: 1.6rem; display: block; margin-bottom: 0.6rem; }
        .library-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            background: rgba(255,255,255,0.015);
            border: 1px solid var(--line);
            border-radius: 4px;
            padding: 0.55rem 0.7rem;
            margin-bottom: 0.3rem;
            cursor: pointer;
            transition: border-color 200ms var(--ease-out), background 200ms var(--ease-out);
        }
        @media (hover: hover) and (pointer: fine) {
            .library-item:hover { background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.14); }
        }
        .library-item .item-info { display: flex; align-items: center; gap: 0.5rem; flex: 1; min-width: 0; }
        .library-item .item-icon { font-size: 0.8rem; flex-shrink: 0; }
        .library-item .item-title {
            font-size: 0.55rem;
            color: var(--dim);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            flex: 1;
        }
        .library-item .item-platform {
            padding: 0.08rem 0.4rem;
            border-radius: 3px;
            font-size: 0.38rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            flex-shrink: 0;
        }
        .library-item .item-platform.faphouse { background: rgba(245,197,24,0.08); color: #f5c518; }
        .library-item .item-platform.terabox { background: rgba(0,180,216,0.08); color: #00b4d8; }
        .library-item .item-remove {
            background: transparent;
            border: none;
            color: #3b3842;
            font-size: 0.6rem;
            cursor: pointer;
            padding: 0 0.2rem;
            transition: color 200ms var(--ease-out);
        }
        .library-item .item-remove:hover { color: #ff5c5c; }

        /* ===== SPLASH ===== */
        .splash-overlay {
            position: fixed;
            inset: 0;
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            background:
                radial-gradient(ellipse at 50% 40%, rgba(245,197,24,0.05), transparent 60%),
                var(--bg);
            transition: opacity 500ms var(--ease-out), visibility 500ms var(--ease-out);
            padding: 1.5rem;
        }
        .splash-overlay.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
        .splash-panel {
            position: relative;
            width: 100%;
            max-width: 480px;
            text-align: center;
            padding: 2.4rem 2rem;
            background: rgba(11,11,15,0.85);
            border: 1px solid rgba(245,197,24,0.14);
            border-radius: 6px;
            transform: translateY(10px);
            opacity: 0;
            animation: riseIn 500ms var(--ease-out) forwards;
        }
        .splash-panel .corner { border-color: rgba(245,197,24,0.5); }
        .splash-18 {
            font-family: "Unbounded", sans-serif;
            font-weight: 900;
            font-size: clamp(4rem, 12vw, 6rem);
            line-height: 1;
            background: linear-gradient(120deg, #ffd94a, #b89100);
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .splash-warn {
            margin: 1.2rem 0 1.8rem;
            font-size: 0.52rem;
            line-height: 2;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--dim);
        }
        .splash-warn strong { color: var(--txt); font-weight: 400; }
        .splash-btn {
            background: var(--acc);
            border: none;
            border-radius: 4px;
            padding: 0.9rem 2.4rem;
            font-family: "Unbounded", sans-serif;
            font-weight: 700;
            font-size: 0.62rem;
            letter-spacing: 0.14em;
            color: #000;
            cursor: pointer;
            transition: transform 160ms var(--ease-out), box-shadow 250ms var(--ease-out);
        }
        @media (hover: hover) and (pointer: fine) {
            .splash-btn:hover { box-shadow: 0 0 40px var(--acc-glow); }
        }
        .splash-btn:active { transform: scale(0.97); }
        .splash-sub {
            margin-top: 1.3rem;
            font-size: 0.42rem;
            letter-spacing: 0.28em;
            text-transform: uppercase;
            color: #3b3842;
        }

        @media (max-width: 820px) {
            .gates { flex-direction: column; }
            .gate { height: 148px; }
            .gate-tag { display: none; }
            .hud-tag, .hud-sep { display: none; }
            .hud { padding: 0.7rem 0.9rem; }
            .deck-shell { padding-left: 0.9rem; }
            .launch-btn { padding: 0 1.4rem; }
            .ticker-group { gap: 1.4rem; padding-right: 1.4rem; }
            .tick-label { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
            .gate-wrap, .deck, .ticker, .stage-head, .splash-panel { animation: none; opacity: 1; transform: none; }
            .ticker-track { animation-play-state: paused; }
            .orb, .hud-dot, .gate-led, .deck-caret { animation: none; }
            .gate.ping { animation: none; }
        }
    </style>
</head>
<body>
<div class="app" id="app">
    <div class="orb orb-a"></div>
    <div class="orb orb-b"></div>
    <div class="bg-grid"></div>
    <div class="scanlines"></div>
    <div class="bg-vignette"></div>

    <!-- ===== HUD ===== -->
    <header class="hud">
        <div class="hud-left">
            <span class="hud-dot"></span>
            <span class="hud-status">SYS ONLINE</span>
            <span class="hud-sep">/</span>
            <span class="hud-tag">HUB v2.6</span>
        </div>
        <div class="hud-right">
            <span class="hud-platform" id="hudPlatform">NETWORK: FAPHOUSE</span>
            <span class="hud-sep">/</span>
            <span class="hud-clock" id="hudClock">--:--:-- UTC</span>
            <button class="hud-lib" id="libraryToggleBtn">LIBRARY <span class="hud-lib-count" id="libraryBadge">0</span></button>
        </div>
    </header>

    <!-- ===== STAGE ===== -->
    <main class="stage" id="stage">
        <div class="stage-head">
            <div class="eyebrow">dual network <em>·</em> pick a gate</div>
            <h1>ENTER THE HOUSE</h1>
        </div>

        <div class="gates">
            <div class="gate-wrap">
                <button class="gate selected" id="gateFaphouse" type="button" aria-label="Select Faphouse">
                    <span class="gate-corner tl"></span><span class="gate-corner tr"></span><span class="gate-corner bl"></span><span class="gate-corner br"></span>
                    <span class="gate-top">
                        <span class="gate-index">01</span>
                        <span class="gate-led"></span>
                    </span>
                    <span class="gate-mid">
                        <span class="gate-word">FAPHOUSE</span>
                        <span class="gate-tag">stream · premium · direct</span>
                    </span>
                    <span class="gate-foot">
                        <span class="gate-status">ARMED</span>
                        <span class="gate-arrow">▸</span>
                    </span>
                    <span class="gate-key">key [1]</span>
                </button>
            </div>
            <div class="gate-wrap">
                <button class="gate" id="gateTerabox" type="button" aria-label="Select Terabox">
                    <span class="gate-corner tl"></span><span class="gate-corner tr"></span><span class="gate-corner bl"></span><span class="gate-corner br"></span>
                    <span class="gate-top">
                        <span class="gate-index">02</span>
                        <span class="gate-led"></span>
                    </span>
                    <span class="gate-mid">
                        <span class="gate-word">TERABOX</span>
                        <span class="gate-tag">link · decode · direct</span>
                    </span>
                    <span class="gate-foot">
                        <span class="gate-status">STANDBY</span>
                        <span class="gate-arrow">▸</span>
                    </span>
                    <span class="gate-key">key [2]</span>
                </button>
            </div>
        </div>

        <form class="deck" id="urlForm" method="GET" action="/play">
            <div class="deck-shell">
                <span class="deck-prefix" id="deckPrefix">fap://</span>
                <span class="deck-caret">▋</span>
                <input class="deck-input" id="videoUrlInput" name="url" type="text" spellcheck="false" autocomplete="off" placeholder="https://faphouse2.com/videos/..." value="{{ video_url or '' }}">
                <button type="submit" class="launch-btn" id="loadBtn">LAUNCH</button>
            </div>
            <div class="deck-hint">enter to launch · or paste a link to auto-lock the network</div>
        </form>

        <div class="ticker" id="ticker">
            <div class="ticker-track" id="tickerTrack">
                <div class="ticker-group">
                    <span class="tick-label">try one</span>
                    <a class="tick-link fap-link" data-platform="faphouse" data-url="https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u">https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u</a>
                    <span class="tick-sep">▸</span>
                    <a class="tick-link tera-link" data-platform="terabox" data-url="https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug">https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug</a>
                    <span class="tick-sep">▸</span>
                </div>
                <div class="ticker-group" aria-hidden="true">
                    <span class="tick-label">try one</span>
                    <a class="tick-link fap-link" data-platform="faphouse" data-url="https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u">https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u</a>
                    <span class="tick-sep">▸</span>
                    <a class="tick-link tera-link" data-platform="terabox" data-url="https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug">https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug</a>
                    <span class="tick-sep">▸</span>
                </div>
            </div>
        </div>
    </main>

    <!-- Library Backdrop -->
    <div class="library-sidebar-backdrop" id="libraryBackdrop"></div>

    <!-- Library Sidebar -->
    <div class="library-sidebar" id="librarySidebar">
        <div class="library-sidebar-header">
            <div class="library-sidebar-title">Library <span class="count" id="sidebarCount">(0)</span></div>
            <button class="library-sidebar-close" id="libraryCloseBtn" aria-label="Close library">✕</button>
        </div>
        <div class="library-sidebar-actions">
            <button id="refreshLibraryBtn">↻ refresh</button>
            <button class="clear" id="clearLibraryBtn">clear all</button>
        </div>
        <div class="library-list" id="libraryList">
            <div class="library-empty">
                <span class="empty-icon">▢</span>
                No videos in library yet<br>
                Watch something to save it here
            </div>
        </div>
    </div>

    <div id="saveToast"></div>
</div>

<!-- ===== SPLASH ===== -->
<div class="splash-overlay" id="splashOverlay">
    <div class="splash-panel">
        <span class="gate-corner tl"></span><span class="gate-corner tr"></span><span class="gate-corner bl"></span><span class="gate-corner br"></span>
        <div class="splash-18">18+</div>
        <div class="splash-warn">restricted content<br>you must be <strong>18 or older</strong> to enter this hub</div>
        <button class="splash-btn" id="enterBtn">I AM 18+ · ENTER</button>
        <div class="splash-sub">adult content · verify to continue</div>
    </div>
</div>

<script>
    // ===== DOM REFS =====
    const enterBtn = document.getElementById('enterBtn');
    const splashOverlay = document.getElementById('splashOverlay');
    const stage = document.getElementById('stage');
    const gateFaphouse = document.getElementById('gateFaphouse');
    const gateTerabox = document.getElementById('gateTerabox');
    const deckPrefix = document.getElementById('deckPrefix');
    const urlForm = document.getElementById('urlForm');
    const videoUrlInput = document.getElementById('videoUrlInput');
    const loadBtn = document.getElementById('loadBtn');
    const hudPlatform = document.getElementById('hudPlatform');
    const hudClock = document.getElementById('hudClock');
    const ticker = document.getElementById('ticker');
    const libraryToggleBtn = document.getElementById('libraryToggleBtn');
    const librarySidebar = document.getElementById('librarySidebar');
    const libraryBackdrop = document.getElementById('libraryBackdrop');
    const libraryCloseBtn = document.getElementById('libraryCloseBtn');
    const refreshLibraryBtn = document.getElementById('refreshLibraryBtn');
    const clearLibraryBtn = document.getElementById('clearLibraryBtn');
    const libraryList = document.getElementById('libraryList');
    const libraryBadge = document.getElementById('libraryBadge');
    const sidebarCount = document.getElementById('sidebarCount');

    let currentPlatform = 'faphouse';
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ===== LIBRARY FUNCTIONS =====
    function getLibrary(platform) {
        try {
            const key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
            return JSON.parse(localStorage.getItem(key) || '[]');
        } catch {
            return [];
        }
    }

    function saveLibrary(platform, library) {
        const key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
        localStorage.setItem(key, JSON.stringify(library));
        renderLibrary();
    }

    function addToLibrary(platform, video) {
        const library = getLibrary(platform);
        const exists = library.some(item => item.url === video.url);
        if (!exists) {
            video.watchedAt = new Date().toISOString();
            library.unshift(video);
            saveLibrary(platform, library);
            showToast('Added to ' + platform + ' library');
            return true;
        }
        return false;
    }

    function removeFromLibrary(platform, url) {
        const library = getLibrary(platform).filter(item => item.url !== url);
        saveLibrary(platform, library);
    }

    function clearLibrary(platform) {
        if (confirm('Clear all ' + platform + ' videos from library?')) {
            saveLibrary(platform, []);
        }
    }

    function showToast(message) {
        const toast = document.getElementById('saveToast');
        if (!toast) {
            const newToast = document.createElement('div');
            newToast.id = 'saveToast';
            newToast.style.cssText = `
                position: fixed;
                bottom: 96px;
                left: 50%;
                transform: translate(-50%, 12px);
                background: rgba(10,10,13,0.92);
                border: 1px solid rgba(245,197,24,0.12);
                padding: 0.5rem 1.3rem;
                border-radius: 4px;
                font-family: "JetBrains Mono", monospace;
                font-size: 0.55rem;
                color: #f5c518;
                opacity: 0;
                transition: opacity 220ms ease, transform 220ms ease;
                pointer-events: none;
                z-index: 120;
                backdrop-filter: blur(10px);
            `;
            document.body.appendChild(newToast);
            newToast.textContent = message;
            setTimeout(function() {
                newToast.classList.add('show');
                newToast.style.opacity = '1';
                newToast.style.transform = 'translate(-50%, 0)';
            }, 100);
            setTimeout(function() {
                newToast.style.opacity = '0';
                newToast.style.transform = 'translate(-50%, 12px)';
                setTimeout(function() { newToast.remove(); }, 300);
            }, 3000);
            return;
        }
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(function() {
            toast.classList.remove('show');
        }, 3000);
    }

    function renderLibrary() {
        const platform = currentPlatform || 'faphouse';
        const library = getLibrary(platform);
        const badge = libraryBadge;
        const sidebarCountEl = sidebarCount;
        const btn = libraryToggleBtn;

        badge.textContent = library.length;
        sidebarCountEl.textContent = '(' + library.length + ')';

        if (platform === 'terabox') {
            btn.classList.add('terabox-mode');
        } else {
            btn.classList.remove('terabox-mode');
        }

        if (library.length === 0) {
            libraryList.innerHTML = `
                <div class="library-empty">
                    <span class="empty-icon">▢</span>
                    No ${platform} videos in library yet<br>
                    Watch something to save it here
                </div>
            `;
            return;
        }

        let html = '';
        library.forEach(function(item) {
            const icon = platform === 'faphouse' ? '▣' : '▦';
            const title = item.title || (item.file_name || 'Untitled');
            html += `
                <div class="library-item" data-url="${item.url}">
                    <div class="item-info">
                        <span class="item-icon">${icon}</span>
                        <span class="item-title">${title}</span>
                        <span class="item-platform ${platform}">${platform}</span>
                    </div>
                    <button class="item-remove" data-url="${item.url}">✕</button>
                </div>
            `;
        });

        libraryList.innerHTML = html;

        libraryList.querySelectorAll('.library-item').forEach(function(el) {
            const url = el.dataset.url;

            el.addEventListener('click', function(e) {
                if (e.target.closest('.item-remove')) return;
                const form = urlForm;
                const input = videoUrlInput;
                input.value = url;
                form.action = platform === 'faphouse' ? '/play' : '/terabox';
                form.submit();
                closeLibrary();
            });

            el.querySelector('.item-remove').addEventListener('click', function(e) {
                e.stopPropagation();
                removeFromLibrary(platform, this.dataset.url);
            });
        });
    }

    // ===== LIBRARY SIDEBAR CONTROLS =====
    function toggleLibrary() {
        librarySidebar.classList.toggle('open');
        libraryBackdrop.classList.toggle('open');
        if (librarySidebar.classList.contains('open')) {
            renderLibrary();
        }
    }

    function closeLibrary() {
        librarySidebar.classList.remove('open');
        libraryBackdrop.classList.remove('open');
    }

    libraryToggleBtn.addEventListener('click', toggleLibrary);
    libraryCloseBtn.addEventListener('click', closeLibrary);
    libraryBackdrop.addEventListener('click', closeLibrary);
    refreshLibraryBtn.addEventListener('click', renderLibrary);
    clearLibraryBtn.addEventListener('click', function() {
        clearLibrary(currentPlatform);
    });

    // ===== PLATFORM SELECTION =====
    function setPlatform(platform, ping) {
        currentPlatform = platform;
        const isFap = platform === 'faphouse';
        document.body.dataset.platform = platform;
        gateFaphouse.classList.toggle('selected', isFap);
        gateTerabox.classList.toggle('selected', !isFap);
        gateFaphouse.querySelector('.gate-status').textContent = isFap ? 'ARMED' : 'STANDBY';
        gateTerabox.querySelector('.gate-status').textContent = !isFap ? 'ARMED' : 'STANDBY';
        deckPrefix.textContent = isFap ? 'fap://' : 'tera://';
        videoUrlInput.placeholder = isFap ? 'https://faphouse2.com/videos/...' : 'https://terafileshare.com/s/...';
        loadBtn.textContent = isFap ? 'LAUNCH' : 'EXTRACT';
        urlForm.action = isFap ? '/play' : '/terabox';
        hudPlatform.textContent = 'NETWORK: ' + (isFap ? 'FAPHOUSE' : 'TERABOX');
        renderLibrary();
        if (ping) {
            const gate = isFap ? gateFaphouse : gateTerabox;
            gate.classList.remove('ping');
            void gate.offsetWidth;
            gate.classList.add('ping');
        }
    }

    function detectPlatformFromUrl(val) {
        const v = val.toLowerCase();
        const isTera = ['terabox', 'terafileshare', 'share.com', 'file.com', 'teraboxlink', '1024terabox', 'teraboxapp'].some(function(s) {
            return v.includes(s);
        });
        const isFap = v.includes('faphouse') || v.includes('faphouse2');
        if (isTera) {
            setPlatform('terabox', true);
        } else if (isFap) {
            setPlatform('faphouse', true);
        }
    }

    gateFaphouse.addEventListener('click', function() { setPlatform('faphouse', false); });
    gateTerabox.addEventListener('click', function() { setPlatform('terabox', false); });

    document.addEventListener('keydown', function(e) {
        if (!splashOverlay.classList.contains('hidden')) return;
        if (e.target.tagName === 'INPUT') return;
        if (e.key === '1' || e.key === 'f' || e.key === 'F') setPlatform('faphouse', false);
        if (e.key === '2' || e.key === 't' || e.key === 'T') setPlatform('terabox', false);
    });

    // ===== URL INPUT =====
    videoUrlInput.addEventListener('paste', function() {
        setTimeout(function() {
            detectPlatformFromUrl(videoUrlInput.value);
        }, 50);
    });

    videoUrlInput.addEventListener('input', function() {
        detectPlatformFromUrl(videoUrlInput.value);
    });

    videoUrlInput.addEventListener('change', function() {
        detectPlatformFromUrl(videoUrlInput.value);
    });

    videoUrlInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            detectPlatformFromUrl(videoUrlInput.value);
            urlForm.submit();
        }
    });

    // ===== TICKER =====
    ticker.addEventListener('click', function(e) {
        const link = e.target.closest('.tick-link');
        if (!link) return;
        const platform = link.dataset.platform;
        setPlatform(platform, true);
        videoUrlInput.value = link.dataset.url;
        setTimeout(function() {
            urlForm.submit();
        }, 80);
    });

    // ===== LOADING STATE =====
    urlForm.addEventListener('submit', function() {
        loadBtn.classList.add('loading');
        loadBtn.textContent = currentPlatform === 'faphouse' ? 'LOADING' : 'EXTRACTING';
    });

    // ===== CLOCK =====
    function tickClock() {
        const d = new Date();
        const p = function(n) { return String(n).padStart(2, '0'); };
        hudClock.textContent = p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds()) + ' UTC';
    }
    tickClock();
    setInterval(tickClock, 1000);

    // ===== GATE TILT + SPOTLIGHT =====
    if (!reduceMotion && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
        document.querySelectorAll('.gate').forEach(function(gate) {
            const target = { rx: 0, ry: 0 };
            const current = { rx: 0, ry: 0 };
            let raf = null;
            function loop() {
                current.rx += (target.rx - current.rx) * 0.12;
                current.ry += (target.ry - current.ry) * 0.12;
                gate.style.transform = 'perspective(1000px) rotateX(' + current.rx + 'deg) rotateY(' + current.ry + 'deg) translateY(-4px)';
                raf = null;
                if (Math.abs(target.rx - current.rx) > 0.03 || Math.abs(target.ry - current.ry) > 0.03) {
                    raf = requestAnimationFrame(loop);
                }
            }
            gate.addEventListener('mousemove', function(e) {
                const r = gate.getBoundingClientRect();
                target.ry = ((e.clientX - r.left) / r.width - 0.5) * 14;
                target.rx = ((e.clientY - r.top) / r.height - 0.5) * -10;
                gate.style.setProperty('--sx', ((e.clientX - r.left) / r.width) * 100 + '%');
                gate.style.setProperty('--sy', ((e.clientY - r.top) / r.height) * 100 + '%');
                if (!raf) raf = requestAnimationFrame(loop);
            });
            gate.addEventListener('mouseleave', function() {
                target.rx = 0;
                target.ry = 0;
                if (!raf) raf = requestAnimationFrame(loop);
            });
        });
    }

    // ===== ENTER =====
    enterBtn.addEventListener('click', function() {
        splashOverlay.classList.add('hidden');
        stage.classList.add('armed');
        renderLibrary();
        videoUrlInput.focus();
    });

    // ===== INIT =====
    setPlatform('faphouse', false);
</script>
</body>
</html>

"""
PLAYER_PAGE_HTML = r"""
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
        .progress-buffer {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            width: 0%;
            background: rgba(255,255,255,0.18);
            border-radius: 2px;
            transition: width 0.3s ease;
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
        .controls-row .icon-btn {
            width: 34px;
            height: 34px;
            padding: 0;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .controls-row .icon-btn svg {
            width: 16px;
            height: 16px;
            fill: currentColor;
        }
        .controls-row .play-btn {
            width: 44px;
            height: 44px;
            min-width: 44px;
            min-height: 44px;
            padding: 0;
            border-radius: 50%;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
        }
        .controls-row .play-btn svg {
            width: 18px;
            height: 18px;
            fill: currentColor;
            display: none;
        }
        .controls-row .play-btn svg.icon-play { margin-left: 2px; }
        .controls-row .play-btn.playing svg.icon-pause { display: block; }
        .controls-row .play-btn.playing svg.icon-play { display: none; }
        .controls-row .play-btn:not(.playing) svg.icon-play { display: block; }
        .controls-row .play-btn:hover {
            background: rgba(245,215,0,0.08);
            border-color: rgba(245,215,0,0.2);
        }
        .volume-group {
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }
        .controls-row .vol-btn {
            width: 30px;
            height: 30px;
            min-height: 30px;
            padding: 0;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(255,255,255,0.45);
        }
        .controls-row .vol-btn svg {
            width: 15px;
            height: 15px;
            fill: currentColor;
        }
        .controls-row .vol-btn.muted { color: rgba(255,255,255,0.15); }
        .controls-row .vol-btn:hover { color: rgba(255,255,255,0.85); }
        .vol-slider {
            width: 64px;
            height: 3px;
            border-radius: 3px;
            background: rgba(255,255,255,0.12);
            cursor: pointer;
            position: relative;
            transition: width 0.25s ease;
        }
        .vol-slider .vol-fill {
            height: 100%;
            width: 100%;
            background: linear-gradient(90deg, #f5c518, #d4a800);
            border-radius: 3px;
            position: relative;
        }
        .vol-slider .vol-fill::after {
            content: '';
            position: absolute;
            right: -3px;
            top: -3px;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #f5c518;
            opacity: 0;
            transition: opacity 0.2s ease;
        }
        .vol-slider:hover .vol-fill::after { opacity: 1; }
        .buffering-overlay {
            position: absolute;
            inset: 0;
            z-index: 11;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(0,0,0,0.25);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
            backdrop-filter: blur(2px);
            -webkit-backdrop-filter: blur(2px);
        }
        .buffering-overlay.visible { opacity: 1; pointer-events: auto; }
        .buffering-spinner {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.08);
            border-top-color: #f5c518;
            animation: buffSpin 0.8s linear infinite;
        }
        @keyframes buffSpin { to { transform: rotate(360deg); } }
        .quality-badge {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.35rem;
            letter-spacing: 0.08em;
            color: rgba(255,255,255,0.35);
            border: 1px solid rgba(255,255,255,0.06);
            background: rgba(255,255,255,0.02);
            padding: 0.1rem 0.45rem;
            border-radius: 4px;
            text-transform: uppercase;
        }
        .quality-badge.live {
            color: rgba(245,197,24,0.8);
            border-color: rgba(245,197,24,0.15);
            background: rgba(245,197,24,0.04);
        }
        .click-overlay {
            position: absolute;
            inset: 0;
            z-index: 10;
            cursor: pointer;
        }
        .save-toast {
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(245,197,24,0.1);
            border: 1px solid rgba(245,197,24,0.05);
            padding: 0.4rem 1.2rem;
            border-radius: 30px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.5rem;
            color: #f5c518;
            opacity: 0;
            transition: all 0.5s ease;
            pointer-events: none;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        .save-toast.show {
            opacity: 1;
            bottom: 100px;
        }
        @media (max-width: 700px) {
            .video-wrapper { width: 96%; border-radius: 8px; }
            .header { padding: 0.6rem 1rem; }
            .header-brand .fap, .header-brand .house { font-size: 0.75rem; }
            .header-badge { font-size: 0.35rem; padding: 0.02rem 0.3rem; }
            .controls-wrapper { padding: 0 0.8rem 0.8rem 0.8rem; }
            .controls-row button { font-size: 0.45rem; min-height: 24px; padding: 0.15rem 0.3rem; }
            .controls-row .play-btn { width: 40px; height: 40px; min-width: 40px; min-height: 40px; }
            .controls-row .play-btn svg { width: 16px; height: 16px; }
            .controls-row .vol-btn { width: 26px; height: 26px; min-height: 26px; }
            .controls-row .icon-btn { width: 28px; height: 28px; }
            .controls-row .icon-btn svg { width: 13px; height: 13px; }
            .vol-slider { width: 48px; }
            .controls-row .time-display { font-size: 0.38rem; min-width: 50px; }
            .controls-row .seek-btn { font-size: 0.38rem; }
            .controls-row .fs-btn { font-size: 0.38rem; }
            .center-play { width: 50px; height: 50px; }
            .center-play svg { width: 22px; height: 22px; }
            .back-btn { font-size: 0.35rem; padding: 0.1rem 0.6rem; min-height: 20px; }
            .progress-section { padding: 0.2rem 0 0.1rem 0; }
            .save-toast { font-size: 0.45rem; padding: 0.3rem 0.8rem; bottom: 60px; }
            .save-toast.show { bottom: 80px; }
            .buffering-spinner { width: 36px; height: 36px; }
        }
        @media (max-width: 450px) {
            .center-play { width: 44px; height: 44px; }
            .center-play svg { width: 18px; height: 18px; }
            .controls-row .play-btn { width: 36px; height: 36px; min-width: 36px; min-height: 36px; }
            .controls-row .play-btn svg { width: 14px; height: 14px; }
            .controls-row .time-display { font-size: 0.35rem; min-width: 44px; }
            .vol-slider { width: 34px; }
            .quality-badge { display: none; }
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
                <span class="quality-badge live" id="qualityBadge">HD · LIVE</span>
                <span class="header-status"><span class="dot"></span> streaming</span>
                <a href="/" class="back-btn">back</a>
            </div>
        </div>
        <div class="buffering-overlay" id="bufferingOverlay">
            <div class="buffering-spinner"></div>
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
                <button class="play-btn" id="playPauseBtn">
                    <svg class="icon-play" viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
                    <svg class="icon-pause" viewBox="0 0 24 24"><rect x="5" y="3" width="5" height="18" rx="1"/><rect x="14" y="3" width="5" height="18" rx="1"/></svg>
                </button>
                <div class="volume-group">
                    <button class="vol-btn" id="volBtn">
                        <svg class="icon-vol" viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3z"/></svg>
                        <svg class="icon-mute" viewBox="0 0 24 24" style="display:none"><path d="M3 9v6h4l5 5V4L7 9H3z"/><line x1="16" y1="9" x2="22" y2="15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="22" y1="9" x2="16" y2="15" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                    </button>
                    <div class="vol-slider" id="volSlider">
                        <div class="vol-fill" id="volFill"></div>
                    </div>
                </div>
                <span class="time-display" id="timeDisplay">0:00 / 0:00</span>
                <button class="seek-btn" id="seekForward">+10</button>
                <button class="fs-btn icon-btn" id="fullscreenBtn">
                    <svg viewBox="0 0 24 24"><path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>
                </button>
            </div>
        </div>
    </div>
</div>

<div class="save-toast" id="saveToast">📚 Added to library</div>

<script src="https://vjs.zencdn.net/8.0.0/video.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {
        // ===== LIBRARY FUNCTIONS =====
        function getLibrary(platform) {
            try {
                const key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
                return JSON.parse(localStorage.getItem(key) || '[]');
            } catch {
                return [];
            }
        }
        
        function saveLibrary(platform, library) {
            const key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
            localStorage.setItem(key, JSON.stringify(library));
        }
        
        function addToLibrary(platform, video) {
            const library = getLibrary(platform);
            const exists = library.some(item => item.url === video.url);
            if (!exists) {
                video.watchedAt = new Date().toISOString();
                library.unshift(video);
                saveLibrary(platform, library);
                showToast('📚 Added to ' + platform + ' library');
                return true;
            }
            return false;
        }
        
        function showToast(message) {
            const toast = document.getElementById('saveToast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
            }, 3000);
        }
        
        // ===== SAVE VIDEO TO LIBRARY =====
        const videoUrl = "{{ m3u8_url }}";
        const originalUrl = new URLSearchParams(window.location.search).get('url') || '';
        
        let videoTitle = '';
        if (originalUrl) {
            const match = originalUrl.match(/videos\/([^\/?]+)/);
            if (match) {
                videoTitle = match[1].replace(/-/g, ' ').replace(/_/g, ' ');
            }
        }
        if (!videoTitle || videoTitle.length < 3) {
            videoTitle = 'Faphouse Video';
        }
        
        let saved = false;
        
        var player = videojs('player', {
            html5: { hls: { enableLowInitialPlaylist: true, smoothQualityChange: true, overrideNative: true } },
            controls: false,
            autoplay: true,
            preload: 'auto'
        });
        
        player.on('play', function() {
            if (!saved && videoUrl) {
                saved = true;
                addToLibrary('faphouse', {
                    url: originalUrl || videoUrl,
                    title: videoTitle,
                    platform: 'faphouse',
                    videoUrl: videoUrl
                });
            }
        });
        
        setTimeout(function() {
            if (!saved && videoUrl) {
                saved = true;
                addToLibrary('faphouse', {
                    url: originalUrl || videoUrl,
                    title: videoTitle,
                    platform: 'faphouse',
                    videoUrl: videoUrl
                });
            }
        }, 5000);
        
        // ===== PLAYER CONTROLS =====
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
        const bufferingOverlay = document.getElementById('bufferingOverlay');
        const volBtn = document.getElementById('volBtn');
        const volSlider = document.getElementById('volSlider');
        const volFill = document.getElementById('volFill');
        const qualityBadge = document.getElementById('qualityBadge');
        const bufferedBar = document.createElement('div');
        bufferedBar.className = 'progress-buffer';
        progressTrack.appendChild(bufferedBar);
        progressTrack.appendChild(progressFill);
        
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
                const buffered = player.buffered();
                if (buffered && buffered.length > 0) {
                    const bufferedEnd = buffered.end(buffered.length - 1);
                    bufferedBar.style.width = Math.min(100, (bufferedEnd / duration) * 100) + '%';
                }
            } else {
                timeDisplay.textContent = '0:00 / 0:00';
                progressFill.style.width = '0%';
                bufferedBar.style.width = '0%';
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
                playPauseBtn.classList.add('playing');
                centerPlayBtn.classList.remove('visible');
                if (controlsVisible) hideControlsDelayed();
            } else {
                player.pause();
                playPauseBtn.classList.remove('playing');
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
        player.on('loadedmetadata', function() {
            updateTimeDisplay();
            const videoEl = player.el().querySelector('video');
            if (videoEl && videoEl.videoHeight) {
                if (videoEl.videoHeight >= 1080) qualityBadge.textContent = 'FHD · 1080P';
                else if (videoEl.videoHeight >= 720) qualityBadge.textContent = 'HD · 720P';
                else if (videoEl.videoHeight >= 480) qualityBadge.textContent = 'SD · 480P';
            }
        });
        player.on('progress', updateTimeDisplay);
        player.on('waiting', function() {
            bufferingOverlay.classList.add('visible');
        });
        player.on('playing', function() {
            bufferingOverlay.classList.remove('visible');
        });
        player.on('canplay', function() {
            bufferingOverlay.classList.remove('visible');
        });
        player.on('play', function() {
            playPauseBtn.classList.add('playing');
            centerPlayBtn.classList.remove('visible');
            showControls();
            hideControlsDelayed();
        });
        player.on('pause', function() {
            playPauseBtn.classList.remove('playing');
            centerPlayBtn.classList.add('visible');
            showControls();
            clearTimeout(controlsTimeout);
        });
        player.on('ended', function() {
            playPauseBtn.classList.remove('playing');
            centerPlayBtn.classList.add('visible');
            showControls();
            clearTimeout(controlsTimeout);
        });
        
        // ===== VOLUME CONTROL =====
        function updateVolumeUI() {
            const vol = player.volume();
            const muted = player.muted();
            volFill.style.width = (muted ? 0 : vol * 100) + '%';
            const iconVol = volBtn.querySelector('.icon-vol');
            const iconMute = volBtn.querySelector('.icon-mute');
            if (muted || vol === 0) {
                volBtn.classList.add('muted');
                iconVol.style.display = 'none';
                iconMute.style.display = 'block';
            } else {
                volBtn.classList.remove('muted');
                iconVol.style.display = 'block';
                iconMute.style.display = 'none';
            }
        }
        
        volBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            player.muted(!player.muted());
            updateVolumeUI();
            showControls();
            if (!player.paused()) hideControlsDelayed();
        });
        
        function setVolumeFromEvent(e) {
            const rect = volSlider.getBoundingClientRect();
            const x = e.clientX !== undefined ? e.clientX : e.touches[0].clientX;
            let pos = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
            player.muted(false);
            if (pos === 0) player.muted(true);
            player.volume(pos);
            updateVolumeUI();
        }
        
        volSlider.addEventListener('click', function(e) {
            e.stopPropagation();
            setVolumeFromEvent(e);
        });
        
        volSlider.addEventListener('touchstart', function(e) {
            e.preventDefault();
            e.stopPropagation();
            setVolumeFromEvent(e);
        }, { passive: false });
        
        volSlider.addEventListener('touchmove', function(e) {
            e.preventDefault();
            setVolumeFromEvent(e);
        }, { passive: false });
        
        player.on('volumechange', updateVolumeUI);
        updateVolumeUI();
        
        document.addEventListener('keydown', function(e) {
            if (e.key === ' ' || e.key === 'Space') { e.preventDefault(); togglePlayPause(); }
            if (e.key === 'ArrowLeft') { e.preventDefault(); seekBack.click(); }
            if (e.key === 'ArrowRight') { e.preventDefault(); seekForward.click(); }
            if (e.key === 'm' || e.key === 'M') { e.preventDefault(); volBtn.click(); }
            if (e.key === 'ArrowUp') { e.preventDefault(); player.muted(false); player.volume(Math.min(1, player.volume() + 0.1)); updateVolumeUI(); }
            if (e.key === 'ArrowDown') { e.preventDefault(); player.volume(Math.max(0, player.volume() - 0.1)); updateVolumeUI(); }
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

TERABOX_PLAYER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Terabox Player</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #000; 
            font-family: Arial, sans-serif;
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            overflow: hidden;
        }
        .container { 
            width: 100%;
            height: 100vh;
            background: #000;
            display: flex;
            flex-direction: column;
        }
        .video-wrapper {
            flex: 1;
            width: 100%;
            background: #000;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            position: relative;
        }
        .video-wrapper iframe {
            width: 100%;
            height: 100%;
            border: none;
            background: #000;
        }
        .info {
            padding: 10px 16px;
            background: #111;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            border-top: 1px solid #1a1a1a;
            flex-shrink: 0;
        }
        .info .file-info {
            color: #555;
            font-size: 12px;
            font-family: Arial, sans-serif;
        }
        .info .file-info span { color: #888; }
        .back-btn {
            color: #00b4d8;
            text-decoration: none;
            padding: 4px 14px;
            border: 1px solid #00b4d8;
            border-radius: 20px;
            font-size: 12px;
            font-family: Arial, sans-serif;
            transition: all 0.3s;
        }
        .back-btn:hover { background: #00b4d8; color: #000; }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #555;
            font-size: 14px;
            z-index: 5;
            text-align: center;
            font-family: Arial, sans-serif;
        }
        .loading .spinner {
            display: inline-block;
            width: 30px;
            height: 30px;
            border: 3px solid #222;
            border-top: 3px solid #00b4d8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-bottom: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .save-toast {
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,180,216,0.1);
            border: 1px solid rgba(0,180,216,0.05);
            padding: 0.4rem 1.2rem;
            border-radius: 30px;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.5rem;
            color: #00b4d8;
            opacity: 0;
            transition: all 0.5s ease;
            pointer-events: none;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        .save-toast.show {
            opacity: 1;
            bottom: 100px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="video-wrapper" id="videoWrapper">
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <div>Loading player...</div>
            </div>
            <iframe 
                id="playerFrame"
                src="{{ video_url }}" 
                allowfullscreen 
                allow="autoplay; encrypted-media; fullscreen"
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-presentation"
                loading="eager"
            ></iframe>
        </div>
        <div class="info">
            <div class="file-info">
                📁 <span>{{ file_name }}</span>
                {% if file_size %}
                | 📦 <span>{{ file_size }}</span>
                {% endif %}
            </div>
            <a href="/" class="back-btn">← Back</a>
        </div>
    </div>

    <div class="save-toast" id="saveToast">📚 Added to library</div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // ===== LIBRARY FUNCTIONS =====
            function getLibrary(platform) {
                try {
                    const key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
                    return JSON.parse(localStorage.getItem(key) || '[]');
                } catch {
                    return [];
                }
            }
            
            function saveLibrary(platform, library) {
                const key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
                localStorage.setItem(key, JSON.stringify(library));
            }
            
            function addToLibrary(platform, video) {
                const library = getLibrary(platform);
                const exists = library.some(item => item.url === video.url);
                if (!exists) {
                    video.watchedAt = new Date().toISOString();
                    library.unshift(video);
                    saveLibrary(platform, library);
                    showToast('📚 Added to ' + platform + ' library');
                    return true;
                }
                return false;
            }
            
            function showToast(message) {
                const toast = document.getElementById('saveToast');
                toast.textContent = message;
                toast.classList.add('show');
                setTimeout(() => {
                    toast.classList.remove('show');
                }, 3000);
            }
            
            // ===== SAVE VIDEO TO LIBRARY =====
            const videoUrl = "{{ video_url }}";
            const originalUrl = new URLSearchParams(window.location.search).get('url') || '';
            const fileName = "{{ file_name }}" || 'Terabox Video';
            
            let saved = false;
            
            const iframe = document.getElementById('playerFrame');
            const loading = document.getElementById('loading');
            
            iframe.addEventListener('load', function() {
                loading.style.display = 'none';
                
                if (!saved && (videoUrl || originalUrl)) {
                    saved = true;
                    addToLibrary('terabox', {
                        url: originalUrl || videoUrl,
                        title: fileName,
                        platform: 'terabox',
                        videoUrl: videoUrl,
                        file_name: fileName,
                        file_size: "{{ file_size }}"
                    });
                }
            });
            
            setTimeout(function() {
                loading.style.display = 'none';
                if (!saved && (videoUrl || originalUrl)) {
                    saved = true;
                    addToLibrary('terabox', {
                        url: originalUrl || videoUrl,
                        title: fileName,
                        platform: 'terabox',
                        videoUrl: videoUrl,
                        file_name: fileName,
                        file_size: "{{ file_size }}"
                    });
                }
            }, 8000);
        });
    </script>
</body>
</html>
"""

ERROR_PAGE_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Error · Faphouse Player</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Unbounded:wght@300;400;700;900&family=JetBrains+Mono:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: #000000;
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
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .bg-glow {
            position: absolute;
            inset: 0;
            background: radial-gradient(ellipse at 50% 40%, rgba(245,197,24,0.02), transparent 70%);
            pointer-events: none;
        }
        .bg-orb {
            position: absolute;
            width: 40vmax;
            height: 40vmax;
            border-radius: 50%;
            filter: blur(90px);
            pointer-events: none;
        }
        .bg-orb.orb-a {
            top: -20%;
            left: -15%;
            background: radial-gradient(circle, rgba(245,197,24,0.04) 0%, transparent 65%);
            animation: driftA 26s ease-in-out infinite alternate;
        }
        .bg-orb.orb-b {
            bottom: -25%;
            right: -18%;
            background: radial-gradient(circle, rgba(255,68,68,0.035) 0%, transparent 65%);
            animation: driftB 30s ease-in-out infinite alternate;
        }
        @keyframes driftA {
            0%   { transform: translate(0, 0) scale(1); }
            100% { transform: translate(7vmax, 6vmax) scale(1.12); }
        }
        @keyframes driftB {
            0%   { transform: translate(0, 0) scale(1); }
            100% { transform: translate(-6vmax, -5vmax) scale(0.92); }
        }
        .error-card {
            position: relative;
            width: 92%;
            max-width: 460px;
            padding: 3rem 2.5rem;
            background: rgba(8,8,8,0.8);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.03);
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 40px 80px rgba(0,0,0,0.6);
            animation: cardIn 0.7s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        @keyframes cardIn {
            0% { opacity: 0; transform: translateY(24px) scale(0.96); }
            100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        .error-code {
            font-size: 4.5rem;
            font-weight: 900;
            line-height: 1;
            background: linear-gradient(135deg, #ff4444, #b02a2a);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.03em;
            margin-bottom: 0.3rem;
            filter: drop-shadow(0 0 30px rgba(255,68,68,0.15));
        }
        .error-label {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.5rem;
            letter-spacing: 0.4em;
            text-transform: uppercase;
            color: #3d3930;
            margin-bottom: 1.8rem;
        }
        .error-title {
            font-size: 0.85rem;
            font-weight: 700;
            color: #f5f0e6;
            margin-bottom: 0.8rem;
            letter-spacing: 0.02em;
        }
        .error-message {
            font-family: "JetBrains Mono", monospace;
            font-size: 0.6rem;
            line-height: 1.9;
            color: #6b6558;
            margin-bottom: 2rem;
        }
        .error-message .highlight {
            color: #f5c518;
        }
        .btn-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
        }
        .back-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
            background: #f5c518;
            border: none;
            color: #000000;
            text-decoration: none;
            padding: 0.7rem 2.2rem;
            border-radius: 60px;
            font-family: "Unbounded", sans-serif;
            font-weight: 700;
            font-size: 0.6rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            box-shadow: 0 0 0 0 rgba(245,197,24,0.2);
        }
        .back-btn:hover {
            transform: scale(0.97);
            box-shadow: 0 0 30px rgba(245,197,24,0.2);
        }
        .back-btn:active { transform: scale(0.92); }
        .retry-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: transparent;
            border: 1px solid rgba(255,255,255,0.05);
            color: #3d3930;
            text-decoration: none;
            padding: 0.7rem 1.4rem;
            border-radius: 60px;
            font-family: "Unbounded", sans-serif;
            font-size: 0.55rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .retry-btn:hover {
            color: #8a8477;
            border-color: rgba(255,255,255,0.1);
        }
        .error-details {
            margin-top: 1.6rem;
            padding: 0.8rem 1rem;
            background: rgba(255,255,255,0.01);
            border: 1px solid rgba(255,255,255,0.02);
            border-radius: 10px;
            font-size: 0.5rem;
            color: #3a362e;
            word-break: break-all;
            font-family: "JetBrains Mono", monospace;
            text-align: left;
        }
        .error-details .label {
            color: #6b6558;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.42rem;
            display: block;
            margin-bottom: 0.4rem;
        }
        .error-details .value {
            color: #8a8477;
            line-height: 1.6;
        }
        .footer-hint {
            position: fixed;
            bottom: 1.5rem;
            left: 0;
            right: 0;
            text-align: center;
            z-index: 10;
            font-family: "JetBrains Mono", monospace;
            font-size: 0.4rem;
            color: #1a1814;
            letter-spacing: 0.3em;
            text-transform: uppercase;
        }
        @media (max-width: 500px) {
            .error-card { padding: 2.2rem 1.5rem; }
            .error-code { font-size: 3.5rem; }
            .btn-row { flex-direction: column; }
            .back-btn, .retry-btn { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="bg-glow"></div>
    <div class="bg-orb orb-a"></div>
    <div class="bg-orb orb-b"></div>
    
    <div class="error-card">
        <div class="error-code">!</div>
        <div class="error-label">stream error</div>
        <div class="error-title">{{ error_title }}</div>
        <div class="error-message">{{ error_message }}</div>
        <div class="btn-row">
            <a href="/" class="back-btn">← go home</a>
            <button class="retry-btn" onclick="history.back()">retry</button>
        </div>
        {% if error_detail %}
        <div class="error-details">
            <span class="label">details</span>
            <span class="value">{{ error_detail }}</span>
        </div>
        {% endif %}
    </div>
    
    <div class="footer-hint">faphouse + terabox · premium webplayer</div>
</body>
</html>
"""

# ============= ROUTES =============

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
        logger.info(f"Faphouse play request for: {video_url}")
        m3u8_url = faphouse_client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return render_template_string(
                PLAYER_PAGE_HTML,
                m3u8_url=m3u8_url,
                platform="faphouse",
                file_name="",
                file_size=""
            )
        else:
            return render_template_string(
                ERROR_PAGE_HTML,
                error_title="Video Not Found",
                error_message="Could not find a playable video URL. The video might be unavailable, private, or removed.",
                error_detail="No M3U8 URL found in the page source"
            )
    except Exception as e:
        logger.error(f"Play error: {str(e)}")
        return render_template_string(
            ERROR_PAGE_HTML,
            error_title="Something Went Wrong",
            error_message="An unexpected error occurred while trying to play this video.",
            error_detail=str(e)
        )

@app.route('/terabox')
def terabox_player():
    video_url = request.args.get('url')
    
    if not video_url:
        return render_template_string(MAIN_PAGE_HTML, video_url=None)
    
    try:
        logger.info(f"Terabox request for: {video_url}")
        result = terabox_client.process_terabox_link(video_url)
        
        if result.get('error'):
            return render_template_string(
                ERROR_PAGE_HTML,
                error_title="Terabox Error",
                error_message=result['error'],
                error_detail=""
            )
        
        return render_template_string(
            TERABOX_PLAYER_HTML,
            video_url=result['video_url'],
            file_name=result.get('file_name', ''),
            file_size=result.get('file_size', '')
        )
        
    except Exception as e:
        logger.error(f"Terabox error: {str(e)}")
        return render_template_string(
            ERROR_PAGE_HTML,
            error_title="Something Went Wrong",
            error_message="An unexpected error occurred while processing your request.",
            error_detail=str(e)
        )

@app.route('/api/m3u8')
def get_m3u8():
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    try:
        if '#' in video_url:
            video_url = video_url.split('#')[0]
            
        m3u8_url = faphouse_client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return jsonify({
                "success": True,
                "m3u8_url": m3u8_url,
                "video_url": video_url,
                "platform": "faphouse"
            })
        else:
            return jsonify({
                "success": False,
                "error": "No M3U8 URL found"
            }), 404
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/terabox')
def api_terabox():
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    try:
        result = terabox_client.process_terabox_link(video_url)
        
        if result.get('error'):
            return jsonify({"success": False, "error": result['error']}), 404
        
        return jsonify({
            "success": True,
            "video_url": result['video_url'],
            "file_name": result.get('file_name', ''),
            "file_size": result.get('file_size', ''),
            "platform": "terabox"
        })
        
    except Exception as e:
        logger.error(f"API Terabox error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/status')
def status():
    return jsonify({
        "status": "online",
        "faphouse": {
            "logged_in": faphouse_client.logged_in,
            "session_created": faphouse_client.session_created,
            "cache_info": faphouse_client.get_m3u8_url.cache_info()._asdict()
        },
        "terabox": {
            "cache_size": len(terabox_client.cache)
        }
    })

def handler(request, context):
    return app(request.environ, context)

if __name__ == "__main__":
    print(f"""
{'='*70}
Faphouse + Terabox Player · Premium UI
{'='*70}

Features:
  • Faphouse: Logs in and extracts M3U8 URLs (Video.js player)
  • Terabox: Extracts proxy URL and embeds in iframe
  • ✨ Ambient animated backgrounds (orbs, grid, vignette)
  • 📚 Collapsible library sidebar (hamburger menu button)
  • 📝 Separate libraries for each platform
  • 🔄 Click library items to replay videos
  • 🔈 Volume control, mute + keyboard shortcuts (M, ↑, ↓)
  • ⏳ Buffering indicator + buffered progress bar
  • 🎞 Auto quality badge (SD/HD/FHD based on stream)
  • 🌀 Premium loading states (button spinner, secure-stream)
  • 🎨 Consistent glassmorphism design across all pages

Endpoints:
  /play?url=URL         - Faphouse video player (Video.js)
  /terabox?url=URL      - Terabox video player (iframe)
  /api/m3u8?url=URL     - Get Faphouse M3U8 URL
  /api/terabox?url=URL  - Get Terabox video URL
  /api/status           - Check status

Faphouse Credentials:
  EMAIL: {EMAIL[:5]}... 
  PASSWORD: {'*' * 8}
{'='*70}
""")
    
    print("Starting server for local testing...")
    print("Try this Terabox link: https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug")
    app.run(host='0.0.0.0', port=5000, debug=True)
