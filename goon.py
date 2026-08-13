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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>The House · Faphouse / Terabox</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --paper: #faf9f6;
            --paper-2: #f2f0eb;
            --ink: #1d1d1f;
            --ink-2: #6e6e73;
            --ink-3: #aeaeb2;
            --line: rgba(29, 29, 31, 0.09);
            --acc: #ff2e9a;
            --acc-deep: #d9167c;
            --acc-tint: rgba(255, 46, 154, 0.08);
            --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
            --shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
            --shadow-lg: 0 24px 70px rgba(0, 0, 0, 0.14);
            --ease: cubic-bezier(0.16, 1, 0.3, 1);
            --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        body[data-platform="terabox"] {
            --acc: #d87a50;
            --acc-deep: #b25e36;
            --acc-tint: rgba(216, 122, 80, 0.1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; }
        body {
            background: var(--paper);
            font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
            color: var(--ink);
            overflow: hidden;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }
        .app {
            position: relative;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .bg-glow {
            position: absolute;
            top: -30%;
            left: 50%;
            transform: translateX(-50%);
            width: 80vmax;
            height: 60vmax;
            background: radial-gradient(ellipse at center, var(--acc-tint), transparent 65%);
            pointer-events: none;
            transition: background 500ms var(--ease);
        }

        /* ===== TOP BAR ===== */
        .topbar {
            position: relative;
            z-index: 40;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.7rem 1.6rem;
            background: rgba(250, 249, 246, 0.72);
            backdrop-filter: saturate(180%) blur(20px);
            -webkit-backdrop-filter: saturate(180%) blur(20px);
            border-bottom: 1px solid var(--line);
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }
        .brand-word {
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--ink);
        }
        .brand-word .dot { color: var(--acc); transition: color 300ms var(--ease); }
        .brand-chip {
            font-size: 0.6rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            color: var(--ink-2);
            background: var(--paper-2);
            border-radius: 999px;
            padding: 0.22rem 0.6rem;
        }
        .top-right {
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }
        .net-chip {
            font-size: 0.62rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            color: var(--acc-deep);
            background: var(--acc-tint);
            border-radius: 999px;
            padding: 0.32rem 0.7rem;
            transition: color 300ms var(--ease), background 300ms var(--ease);
            white-space: nowrap;
        }
        .clock {
            font-size: 0.62rem;
            font-weight: 500;
            color: var(--ink-3);
            white-space: nowrap;
            font-variant-numeric: tabular-nums;
        }
        .lib-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            background: var(--ink);
            color: var(--paper);
            border: none;
            border-radius: 999px;
            padding: 0.42rem 0.9rem;
            font-family: inherit;
            font-size: 0.66rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            cursor: pointer;
            box-shadow: var(--shadow-sm);
            transition: transform 180ms var(--ease), box-shadow 300ms var(--ease), opacity 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .lib-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 18px rgba(0,0,0,0.18); }
        }
        .lib-btn:active { transform: scale(0.96); }
        .lib-btn.terabox-mode { background: #d87a50; }
        .lib-count {
            background: var(--acc);
            color: #fff;
            border-radius: 999px;
            min-width: 18px;
            height: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.6rem;
            font-weight: 700;
            padding: 0 0.3rem;
            transition: background 300ms var(--ease);
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
            gap: clamp(1.1rem, 3vh, 2rem);
            padding: 1.2rem 1.4rem;
            max-width: 1080px;
            width: 100%;
            margin: 0 auto;
            opacity: 0;
            transition: opacity 600ms var(--ease);
        }
        .stage.armed { opacity: 1; }

        .hero { text-align: center; }
        .hero-eyebrow {
            display: inline-block;
            font-size: 0.62rem;
            font-weight: 600;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            color: var(--acc);
            margin-bottom: 0.7rem;
            opacity: 0;
            animation: fadeUp 500ms var(--ease) forwards;
            animation-delay: 60ms;
        }
        .hero h1 {
            font-size: clamp(2.2rem, 6vw, 4rem);
            font-weight: 800;
            letter-spacing: -0.035em;
            line-height: 1.02;
            color: var(--ink);
            opacity: 0;
            transform: translateY(24px) scale(0.97);
            animation: springIn 700ms var(--spring) forwards;
            animation-delay: 90ms;
        }
        .hero h1 .dot { color: var(--acc); }
        .hero-sub {
            margin-top: 0.8rem;
            font-size: clamp(0.85rem, 1.6vw, 1rem);
            font-weight: 400;
            color: var(--ink-2);
            opacity: 0;
            animation: fadeUp 500ms var(--ease) forwards;
            animation-delay: 200ms;
        }
        @keyframes fadeUp { to { opacity: 1; transform: translateY(0); } }
        @keyframes springIn { to { opacity: 1; transform: translateY(0) scale(1); } }

        /* ===== GATES ===== */
        .gates {
            display: flex;
            gap: clamp(0.9rem, 2.5vw, 1.4rem);
            width: 100%;
            align-items: stretch;
        }
        .gate-wrap {
            flex: 1;
            min-width: 0;
            perspective: 1200px;
            opacity: 0;
            transform: translateY(28px);
            animation: fadeUp 600ms var(--ease) forwards;
        }
        .gate-wrap:nth-child(1) { animation-delay: 160ms; }
        .gate-wrap:nth-child(2) { animation-delay: 230ms; }

        .gate {
            position: relative;
            display: flex;
            flex-direction: column;
            width: 100%;
            height: clamp(190px, 36vh, 300px);
            padding: 1.4rem 1.5rem;
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 26px;
            box-shadow: var(--shadow);
            color: var(--ink);
            text-align: left;
            cursor: pointer;
            font-family: inherit;
            transform-style: preserve-3d;
            will-change: transform;
            transition: border-color 300ms var(--ease), box-shadow 400ms var(--ease), background 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .gate:hover { border-color: rgba(29,29,31,0.16); box-shadow: var(--shadow-lg); }
        }
        .gate:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--acc-tint), var(--shadow); }
        .gate.selected {
            border-color: transparent;
            box-shadow: 0 0 0 2px var(--acc), var(--shadow-lg);
        }
        .gate.selected {
            background: linear-gradient(180deg, #fff, var(--acc-tint));
        }
        .gate.ping { animation: pingRing 700ms var(--ease); }
        @keyframes pingRing {
            0% { box-shadow: 0 0 0 0 rgba(255,46,154,0.45); }
            100% { box-shadow: 0 0 0 16px transparent; }
        }
        .gate-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            transform: translateZ(30px);
        }
        .gate-icon {
            width: clamp(44px, 5vw, 54px);
            height: clamp(44px, 5vw, 54px);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: clamp(1.2rem, 2.4vw, 1.5rem);
            background: var(--paper-2);
            transform: translateZ(40px) rotate(-4deg);
            transition: transform 400ms var(--spring), background 300ms var(--ease);
        }
        .gate.selected .gate-icon { transform: translateZ(40px) rotate(0deg) scale(1.05); background: var(--acc-tint); }
        .gate-idx {
            font-size: 0.62rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            color: var(--ink-3);
        }
        .gate-mid { transform: translateZ(20px); }
        .gate-name {
            font-size: clamp(1.4rem, 3vw, 1.9rem);
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--ink);
        }
        .gate-tag {
            margin-top: 0.35rem;
            font-size: 0.78rem;
            font-weight: 400;
            color: var(--ink-2);
        }
        .gate-foot {
            margin-top: auto;
            padding-top: 1rem;
            border-top: 1px solid var(--line);
            display: flex;
            align-items: center;
            justify-content: space-between;
            transform: translateZ(24px);
        }
        .gate-status {
            font-size: 0.62rem;
            font-weight: 600;
            color: var(--ink-3);
            transition: color 300ms var(--ease);
        }
        .gate.selected .gate-status { color: var(--acc-deep); }
        .gate-cta {
            font-size: 0.68rem;
            font-weight: 600;
            color: var(--acc-deep);
            background: var(--acc-tint);
            border-radius: 999px;
            padding: 0.34rem 0.85rem;
            opacity: 0;
            transform: translateX(-8px);
            transition: opacity 300ms var(--ease), transform 300ms var(--ease);
        }
        .gate.selected .gate-cta { opacity: 1; transform: translateX(0); }
        .gate-key {
            position: absolute;
            right: 1.4rem;
            top: 1.4rem;
            font-size: 0.6rem;
            font-weight: 600;
            color: var(--ink-3);
            transform: translateZ(30px);
        }

        /* ===== DECK ===== */
        .deck {
            width: 100%;
            max-width: 680px;
            opacity: 0;
            transform: translateY(24px);
            animation: fadeUp 600ms var(--ease) forwards;
            animation-delay: 300ms;
        }
        .deck-shell {
            display: flex;
            align-items: center;
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 30px;
            box-shadow: var(--shadow);
            padding: 0.35rem 0.35rem 0.35rem 1.4rem;
            transition: border-color 300ms var(--ease), box-shadow 300ms var(--ease);
        }
        .deck-shell:focus-within {
            border-color: var(--acc);
            box-shadow: 0 0 0 3px var(--acc-tint), var(--shadow);
        }
        .deck-prefix {
            font-size: 0.95rem;
            font-weight: 700;
            letter-spacing: -0.01em;
            color: var(--acc);
            white-space: nowrap;
            transition: color 300ms var(--ease);
        }
        .deck-input {
            flex: 1;
            min-width: 0;
            background: transparent;
            border: none;
            outline: none;
            padding: 0.95rem 1rem;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 500;
            color: var(--ink);
            caret-color: var(--acc);
        }
        .deck-input::placeholder { color: var(--ink-3); font-weight: 400; }
        .launch-btn {
            background: var(--acc);
            color: #fff;
            border: none;
            border-radius: 999px;
            padding: 0.85rem 1.7rem;
            font-family: inherit;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            cursor: pointer;
            position: relative;
            white-space: nowrap;
            box-shadow: 0 4px 14px var(--acc-tint);
            transition: transform 180ms var(--ease), box-shadow 300ms var(--ease), background 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .launch-btn:hover { transform: translateY(-1px); box-shadow: 0 10px 24px var(--acc-tint); }
        }
        .launch-btn:active { transform: scale(0.97); }
        .launch-btn.loading {
            pointer-events: none;
            color: transparent;
        }
        .launch-btn.loading::after {
            content: '';
            position: absolute;
            inset: 0;
            margin: auto;
            width: 18px;
            height: 18px;
            border: 2.5px solid rgba(255,255,255,0.35);
            border-top-color: #fff;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .deck-hint {
            margin-top: 0.65rem;
            text-align: center;
            font-size: 0.68rem;
            font-weight: 400;
            color: var(--ink-3);
        }

        /* ===== TRY ROW ===== */
        .try-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.6rem;
            flex-wrap: wrap;
            opacity: 0;
            animation: fadeUp 600ms var(--ease) forwards;
            animation-delay: 360ms;
        }
        .try-label {
            font-size: 0.66rem;
            font-weight: 600;
            color: var(--ink-3);
            letter-spacing: 0.06em;
        }
        .tick-link {
            font-size: 0.68rem;
            font-weight: 500;
            color: var(--ink-2);
            text-decoration: none;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 0.36rem 0.85rem;
            background: #fff;
            cursor: pointer;
            transition: color 200ms var(--ease), border-color 200ms var(--ease), transform 180ms var(--ease), box-shadow 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .tick-link:hover { color: var(--ink); border-color: rgba(29,29,31,0.2); transform: translateY(-1px); box-shadow: var(--shadow-sm); }
        }
        .tick-link:active { transform: scale(0.97); }
        .foot-note {
            margin-top: 0.4rem;
            font-size: 0.62rem;
            font-weight: 500;
            color: var(--ink-3);
            letter-spacing: 0.04em;
        }

        /* ===== TOAST ===== */
        #saveToast {
            position: fixed;
            bottom: 36px;
            left: 50%;
            transform: translate(-50%, 16px);
            background: rgba(29, 29, 31, 0.92);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            color: #fff;
            border-radius: 999px;
            padding: 0.6rem 1.2rem;
            font-size: 0.78rem;
            font-weight: 500;
            box-shadow: 0 12px 40px rgba(0,0,0,0.25);
            opacity: 0;
            pointer-events: none;
            z-index: 200;
            transition: opacity 300ms var(--ease), transform 400ms var(--ease);
        }
        #saveToast.show { opacity: 1; transform: translate(-50%, 0); }

        /* ===== LIBRARY SIDEBAR ===== */
        .library-sidebar-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(29, 29, 31, 0.25);
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
            opacity: 0;
            visibility: hidden;
            transition: opacity 300ms var(--ease), visibility 300ms var(--ease);
            z-index: 90;
        }
        .library-sidebar-backdrop.open { opacity: 1; visibility: visible; }
        .library-sidebar {
            position: fixed;
            top: 0;
            right: 0;
            height: 100%;
            width: 380px;
            max-width: 92vw;
            background: rgba(250, 249, 246, 0.9);
            backdrop-filter: saturate(180%) blur(30px);
            -webkit-backdrop-filter: saturate(180%) blur(30px);
            z-index: 100;
            transform: translateX(105%);
            transition: transform 450ms var(--ease);
            display: flex;
            flex-direction: column;
            padding: 1.4rem;
            box-shadow: -20px 0 60px rgba(0,0,0,0.1);
        }
        .library-sidebar.open { transform: translateX(0); }
        .library-sidebar-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--line);
        }
        .library-sidebar-title {
            font-size: 1.05rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .library-sidebar-title .count { color: var(--acc); font-weight: 600; }
        .library-sidebar-close {
            background: var(--paper-2);
            border: none;
            border-radius: 999px;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--ink-2);
            font-size: 0.9rem;
            cursor: pointer;
            transition: transform 180ms var(--ease), background 200ms var(--ease);
        }
        .library-sidebar-close:hover { background: var(--line); }
        .library-sidebar-close:active { transform: scale(0.92); }
        .library-sidebar-actions {
            display: flex;
            gap: 0.5rem;
            margin: 1rem 0;
        }
        .library-sidebar-actions button {
            font-family: inherit;
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--ink-2);
            background: transparent;
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 0.4rem 0.9rem;
            cursor: pointer;
            transition: color 200ms var(--ease), border-color 200ms var(--ease), transform 180ms var(--ease);
        }
        .library-sidebar-actions button:hover { color: var(--ink); border-color: rgba(29,29,31,0.2); }
        .library-sidebar-actions button:active { transform: scale(0.96); }
        .library-sidebar-actions button.clear:hover { color: #d33; border-color: rgba(221,51,51,0.3); }
        .library-list { flex: 1; overflow-y: auto; padding-right: 0.4rem; }
        .library-list::-webkit-scrollbar { width: 4px; }
        .library-list::-webkit-scrollbar-track { background: transparent; }
        .library-list::-webkit-scrollbar-thumb { background: var(--line); border-radius: 4px; }
        .library-empty {
            text-align: center;
            padding: 2.6rem 0;
            color: var(--ink-3);
            font-size: 0.78rem;
            font-weight: 400;
            line-height: 1.8;
        }
        .library-empty .empty-icon { font-size: 2rem; display: block; margin-bottom: 0.6rem; }
        .library-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            background: #fff;
            border: 1px solid var(--line);
            border-radius: 16px;
            box-shadow: var(--shadow-sm);
            padding: 0.7rem 0.85rem;
            margin-bottom: 0.5rem;
            cursor: pointer;
            transition: transform 180ms var(--ease), box-shadow 300ms var(--ease), border-color 200ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .library-item:hover { transform: translateY(-1px); box-shadow: var(--shadow); border-color: rgba(29,29,31,0.16); }
        }
        .library-item:active { transform: scale(0.98); }
        .library-item .item-info { display: flex; align-items: center; gap: 0.6rem; flex: 1; min-width: 0; }
        .library-item .item-icon { font-size: 0.95rem; flex-shrink: 0; }
        .library-item .item-title {
            font-size: 0.78rem;
            font-weight: 500;
            color: var(--ink);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            flex: 1;
        }
        .library-item .item-platform {
            font-size: 0.55rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            border-radius: 999px;
            padding: 0.1rem 0.5rem;
            flex-shrink: 0;
        }
        .library-item .item-platform.faphouse { background: var(--acc-tint); color: var(--acc-deep); }
        .library-item .item-platform.terabox { background: rgba(216,122,80,0.12); color: #b25e36; }
        .library-item .item-remove {
            background: transparent;
            border: none;
            color: var(--ink-3);
            font-size: 0.75rem;
            cursor: pointer;
            padding: 0 0.2rem;
            transition: color 200ms var(--ease);
        }
        .library-item .item-remove:hover { color: #d33; }

        /* ===== SPLASH ===== */
        .splash-overlay {
            position: fixed;
            inset: 0;
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
            background: var(--paper);
            transition: opacity 500ms var(--ease), visibility 500ms var(--ease);
            padding: 1.5rem;
        }
        .splash-overlay.hidden { opacity: 0; visibility: hidden; pointer-events: none; }
        .splash-panel {
            text-align: center;
            max-width: 420px;
            opacity: 0;
            transform: translateY(20px) scale(0.98);
            animation: springIn 700ms var(--spring) forwards;
        }
        .splash-chip {
            display: inline-block;
            font-size: 0.6rem;
            font-weight: 700;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: var(--acc);
            background: var(--acc-tint);
            border-radius: 999px;
            padding: 0.3rem 0.7rem;
            margin-bottom: 1.2rem;
        }
        .splash-18 {
            font-size: clamp(4rem, 14vw, 6rem);
            font-weight: 800;
            letter-spacing: -0.04em;
            line-height: 1;
            color: var(--ink);
        }
        .splash-18 .plus { color: var(--acc); }
        .splash-warn {
            margin: 1.2rem 0 1.8rem;
            font-size: 0.85rem;
            font-weight: 400;
            line-height: 1.7;
            color: var(--ink-2);
        }
        .splash-warn strong { color: var(--ink); font-weight: 600; }
        .splash-btn {
            background: var(--ink);
            color: var(--paper);
            border: none;
            border-radius: 999px;
            padding: 0.9rem 2.2rem;
            font-family: inherit;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            box-shadow: var(--shadow);
            transition: transform 180ms var(--ease), box-shadow 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .splash-btn:hover { transform: translateY(-1px); box-shadow: var(--shadow-lg); }
        }
        .splash-btn:active { transform: scale(0.97); }
        .splash-sub {
            margin-top: 1rem;
            font-size: 0.66rem;
            font-weight: 500;
            color: var(--ink-3);
        }

        @media (max-width: 820px) {
            .gates { flex-direction: column; }
            .gate { height: 148px; }
            .gate-tag { display: none; }
            .clock { display: none; }
            .topbar { padding: 0.6rem 1rem; }
            .net-chip { font-size: 0.56rem; }
            .deck-shell { padding-left: 1rem; }
            .launch-btn { padding: 0.8rem 1.3rem; }
        }
        @media (max-width: 460px) {
            .brand-chip { display: none; }
            .gate { padding: 1.1rem 1.2rem; }
        }
        @media (prefers-reduced-motion: reduce) {
            .hero-eyebrow, .hero h1, .hero-sub, .gate-wrap, .deck, .try-row, .splash-panel { animation: none; opacity: 1; transform: none; }
            .gate.ping { animation: none; }
        }
    </style>
</head>
<body>
<div class="app" id="app">
    <div class="bg-glow"></div>

    <!-- ===== TOP BAR ===== -->
    <header class="topbar">
        <div class="brand">
            <span class="brand-word">The House<span class="dot">.</span></span>
            <span class="brand-chip">18+</span>
        </div>
        <div class="top-right">
            <span class="net-chip" id="hudPlatform">Faphouse</span>
            <span class="clock" id="hudClock"></span>
            <button class="lib-btn" id="libraryToggleBtn">Library <span class="lib-count" id="libraryBadge">0</span></button>
        </div>
    </header>

    <!-- ===== STAGE ===== -->
    <main class="stage" id="stage">
        <div class="hero">
            <div class="hero-eyebrow">Adult streaming hub</div>
            <h1>One player.<br>The<span class="dot"> House</span>.</h1>
            <div class="hero-sub">Paste a link, pick a platform, press launch. Faphouse &amp; Terabox, one place.</div>
        </div>

        <div class="gates">
            <div class="gate-wrap">
                <button class="gate selected" id="gateFaphouse" type="button" aria-label="Select Faphouse">
                    <span class="gate-top">
                        <span class="gate-icon">🍑</span>
                        <span class="gate-key">key 1</span>
                    </span>
                    <span class="gate-mid">
                        <span class="gate-name">Faphouse</span>
                        <span class="gate-tag">Premium streams · direct</span>
                    </span>
                    <span class="gate-foot">
                        <span class="gate-status">ARMED</span>
                        <span class="gate-cta">Selected</span>
                    </span>
                </button>
            </div>
            <div class="gate-wrap">
                <button class="gate" id="gateTerabox" type="button" aria-label="Select Terabox">
                    <span class="gate-top">
                        <span class="gate-icon">📦</span>
                        <span class="gate-key">key 2</span>
                    </span>
                    <span class="gate-mid">
                        <span class="gate-name">Terabox</span>
                        <span class="gate-tag">Links · decode · direct</span>
                    </span>
                    <span class="gate-foot">
                        <span class="gate-status">STANDBY</span>
                        <span class="gate-cta">Selected</span>
                    </span>
                </button>
            </div>
        </div>

        <form class="deck" id="urlForm" method="GET" action="/play">
            <div class="deck-shell">
                <span class="deck-prefix" id="deckPrefix">fap://</span>
                <input class="deck-input" id="videoUrlInput" name="url" type="text" spellcheck="false" autocomplete="off" placeholder="https://faphouse2.com/videos/..." value="{{ video_url or '' }}">
                <button type="submit" class="launch-btn" id="loadBtn">Launch</button>
            </div>
            <div class="deck-hint">Enter to launch · paste a link to auto-switch platforms</div>
        </form>

        <div class="try-row" id="ticker">
            <span class="try-label">Try</span>
            <a class="tick-link" data-platform="faphouse" data-url="https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u">faphouse2.com/.../C6Qi1u</a>
            <a class="tick-link" data-platform="terabox" data-url="https://terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug">terafileshare.com/s/1xJtL3j2LJ-ZsUA6zbG7Pug</a>
        </div>
        <div class="foot-note">Adult content · 18+ only</div>
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
            <button id="refreshLibraryBtn">↻ Refresh</button>
            <button class="clear" id="clearLibraryBtn">Clear all</button>
        </div>
        <div class="library-list" id="libraryList">
            <div class="library-empty">
                <span class="empty-icon">🗂️</span>
                No videos in your library yet<br>
                Watch something to save it here
            </div>
        </div>
    </div>

    <div id="saveToast"></div>
</div>

<!-- ===== SPLASH ===== -->
<div class="splash-overlay" id="splashOverlay">
    <div class="splash-panel">
        <div class="splash-chip">18+</div>
        <div class="splash-18">18<span class="plus">+</span></div>
        <div class="splash-warn">This site contains adult content.<br>You must be <strong>18 or older</strong> to enter.</div>
        <button class="splash-btn" id="enterBtn">Enter</button>
        <div class="splash-sub">By entering you confirm you are of legal age</div>
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
                bottom: 36px;
                left: 50%;
                transform: translate(-50%, 16px);
                background: rgba(29,29,31,0.92);
                color: #fff;
                border-radius: 999px;
                padding: 0.6rem 1.2rem;
                font-size: 0.78rem;
                font-weight: 500;
                box-shadow: 0 12px 40px rgba(0,0,0,0.25);
                opacity: 0;
                pointer-events: none;
                z-index: 200;
                transition: opacity 300ms ease, transform 400ms ease;
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
                newToast.style.transform = 'translate(-50%, 16px)';
                setTimeout(function() { newToast.remove(); }, 400);
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

        libraryBadge.textContent = library.length;
        sidebarCount.textContent = '(' + library.length + ')';

        if (platform === 'terabox') {
            libraryToggleBtn.classList.add('terabox-mode');
        } else {
            libraryToggleBtn.classList.remove('terabox-mode');
        }

        if (library.length === 0) {
            libraryList.innerHTML = `
                <div class="library-empty">
                    <span class="empty-icon">🗂️</span>
                    No ${platform} videos in your library yet<br>
                    Watch something to save it here
                </div>
            `;
            return;
        }

        let html = '';
        library.forEach(function(item) {
            const icon = platform === 'faphouse' ? '🍑' : '📦';
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
        loadBtn.textContent = isFap ? 'Launch' : 'Extract';
        urlForm.action = isFap ? '/play' : '/terabox';
        hudPlatform.textContent = isFap ? 'Faphouse' : 'Terabox';
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

    // ===== TRY ROW =====
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
        loadBtn.textContent = currentPlatform === 'faphouse' ? 'Loading' : 'Extracting';
    });

    // ===== CLOCK =====
    function tickClock() {
        const d = new Date();
        const p = function(n) { return String(n).padStart(2, '0'); };
        hudClock.textContent = p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds()) + ' UTC';
    }
    tickClock();
    setInterval(tickClock, 1000);

    // ===== GATE 3D TILT =====
    if (!reduceMotion && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
        document.querySelectorAll('.gate').forEach(function(gate) {
            const target = { rx: 0, ry: 0 };
            const current = { rx: 0, ry: 0 };
            let raf = null;
            function loop() {
                current.rx += (target.rx - current.rx) * 0.1;
                current.ry += (target.ry - current.ry) * 0.1;
                gate.style.transform = 'rotateX(' + current.rx + 'deg) rotateY(' + current.ry + 'deg)';
                raf = null;
                if (Math.abs(target.rx - current.rx) > 0.03 || Math.abs(target.ry - current.ry) > 0.03) {
                    raf = requestAnimationFrame(loop);
                }
            }
            gate.addEventListener('mousemove', function(e) {
                const r = gate.getBoundingClientRect();
                target.ry = ((e.clientX - r.left) / r.width - 0.5) * 8;
                target.rx = ((e.clientY - r.top) / r.height - 0.5) * -6;
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Faphouse · The House</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://vjs.zencdn.net/8.0.0/video-js.css" rel="stylesheet" />
    <style>
        :root {
            --paper: #faf9f6;
            --ink: #1d1d1f;
            --ink-2: #6e6e73;
            --ink-3: #aeaeb2;
            --line: rgba(29, 29, 31, 0.09);
            --acc: #ff2e9a;
            --acc-tint: rgba(255, 46, 154, 0.1);
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
            --shadow: 0 10px 40px rgba(0,0,0,0.08);
            --shadow-lg: 0 24px 70px rgba(0,0,0,0.16);
            --ease: cubic-bezier(0.16, 1, 0.3, 1);
            --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: var(--paper);
            font-family: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
            color: var(--ink);
            height: 100vh;
            width: 100vw;
            overflow: hidden;
            position: fixed;
            top: 0;
            left: 0;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }
        .bg-glow {
            position: absolute;
            top: -25%;
            left: 50%;
            transform: translateX(-50%);
            width: 80vmax;
            height: 55vmax;
            background: radial-gradient(ellipse at center, var(--acc-tint), transparent 65%);
            pointer-events: none;
        }
        .app {
            position: relative;
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            gap: 1.2rem;
            padding: 1.2rem 1.4rem;
        }

        /* ===== VIDEO FRAME ===== */
        .video-wrapper {
            position: relative;
            width: min(90vw, 920px);
            aspect-ratio: 16 / 9;
            background: #000;
            border-radius: 26px;
            overflow: hidden;
            box-shadow: var(--shadow-lg);
            opacity: 0;
            transform: translateY(24px) scale(0.98);
            animation: frameIn 700ms var(--ease) forwards;
        }
        @keyframes frameIn { to { opacity: 1; transform: translateY(0) scale(1); } }
        #player {
            width: 100%;
            height: 100%;
            display: block;
            background: #000;
        }

        /* ===== HEADER (overlay) ===== */
        .header {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            z-index: 15;
            padding: 0.9rem 1.1rem;
            background: linear-gradient(180deg, rgba(0,0,0,0.6) 0%, transparent 100%);
            display: flex;
            align-items: center;
            justify-content: space-between;
            opacity: 0;
            transition: opacity 300ms var(--ease);
            pointer-events: none;
        }
        .header.visible { opacity: 1; pointer-events: auto; }
        .header-brand {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(20,20,22,0.55);
            backdrop-filter: blur(16px) saturate(160%);
            -webkit-backdrop-filter: blur(16px) saturate(160%);
            border-radius: 999px;
            padding: 0.34rem 0.85rem;
        }
        .header-brand .word {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: -0.01em;
            color: #fff;
        }
        .header-brand .dot { color: var(--acc); }
        .header-badge {
            font-size: 0.55rem;
            font-weight: 700;
            color: #fff;
            background: var(--acc);
            border-radius: 999px;
            padding: 0.12rem 0.4rem;
        }
        .header-right {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .quality-badge {
            font-size: 0.55rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #fff;
            background: rgba(20,20,22,0.55);
            backdrop-filter: blur(16px) saturate(160%);
            -webkit-backdrop-filter: blur(16px) saturate(160%);
            border-radius: 999px;
            padding: 0.3rem 0.7rem;
        }
        .quality-badge.live { color: #fff; }
        .header-status {
            font-size: 0.55rem;
            font-weight: 600;
            color: rgba(255,255,255,0.75);
            background: rgba(20,20,22,0.55);
            backdrop-filter: blur(16px) saturate(160%);
            -webkit-backdrop-filter: blur(16px) saturate(160%);
            border-radius: 999px;
            padding: 0.3rem 0.7rem;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }
        .header-status .dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #ff2e9a;
            animation: pulse 1.5s ease-in-out infinite;
            display: inline-block;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
        .back-btn {
            background: rgba(20,20,22,0.55);
            backdrop-filter: blur(16px) saturate(160%);
            -webkit-backdrop-filter: blur(16px) saturate(160%);
            border: none;
            color: #fff;
            border-radius: 999px;
            padding: 0.34rem 0.9rem;
            font-family: inherit;
            font-size: 0.62rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            letter-spacing: 0.01em;
            touch-action: manipulation;
            min-height: 26px;
            display: flex;
            align-items: center;
            transition: transform 180ms var(--ease), background 250ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .back-btn:hover { background: rgba(20,20,22,0.75); }
        }
        .back-btn:active { transform: scale(0.95); }

        /* ===== CENTER PLAY ===== */
        .center-play {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 12;
            width: clamp(60px, 9vw, 76px);
            height: clamp(60px, 9vw, 76px);
            border-radius: 50%;
            background: rgba(255,255,255,0.95);
            border: none;
            color: #000;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.45);
            opacity: 0;
            pointer-events: none;
            transition: opacity 250ms var(--ease), transform 250ms var(--ease);
        }
        .center-play.visible { opacity: 1; pointer-events: auto; }
        @media (hover: hover) and (pointer: fine) {
            .center-play:hover { transform: translate(-50%, -50%) scale(1.06); }
        }
        .center-play:active { transform: translate(-50%, -50%) scale(0.94); }
        .center-play svg { width: 32px; height: 32px; fill: currentColor; margin-left: 5px; }

        /* ===== CONTROLS (overlay) ===== */
        .controls-wrapper {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 20;
            padding: 1rem 1rem 0.9rem 1rem;
            background: linear-gradient(0deg, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0.15) 70%, transparent 100%);
            opacity: 0;
            transition: opacity 300ms var(--ease);
        }
        .controls-wrapper.visible { opacity: 1; }
        .progress-section { width: 100%; padding: 0 0 0.55rem 0; }
        .progress-track {
            position: relative;
            width: 100%;
            height: 5px;
            background: rgba(255,255,255,0.28);
            border-radius: 4px;
            cursor: pointer;
            transition: height 200ms var(--ease);
        }
        .progress-track:hover { height: 7px; }
        .progress-fill {
            height: 100%;
            width: 0%;
            background: var(--acc);
            border-radius: 4px;
            position: relative;
            transition: width 0.1s linear;
        }
        .progress-buffer {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            width: 0%;
            background: rgba(255,255,255,0.4);
            border-radius: 4px;
            transition: width 0.3s var(--ease);
        }
        .progress-fill::after {
            content: '';
            position: absolute;
            right: -6px;
            top: 50%;
            transform: translateY(-50%);
            width: 14px;
            height: 14px;
            border-radius: 50%;
            background: #fff;
            box-shadow: 0 2px 8px rgba(0,0,0,0.35);
            opacity: 0;
            transition: opacity 200ms var(--ease);
        }
        .progress-track:hover .progress-fill::after,
        .progress-track.touching .progress-fill::after { opacity: 1; }
        .controls-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.3rem;
        }
        .controls-row button {
            background: transparent;
            border: none;
            color: rgba(255,255,255,0.85);
            padding: 0.3rem 0.5rem;
            font-family: inherit;
            font-size: 0.66rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 160ms var(--ease), color 200ms var(--ease), background 200ms var(--ease);
            border-radius: 999px;
            min-height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            touch-action: manipulation;
        }
        .controls-row button:active { transform: scale(0.92); color: #fff; }
        .controls-row .seek-btn {
            font-size: 0.6rem;
            color: rgba(255,255,255,0.7);
            padding: 0.25rem 0.5rem;
            min-height: 30px;
        }
        @media (hover: hover) and (pointer: fine) {
            .controls-row .seek-btn:hover { color: #fff; background: rgba(255,255,255,0.14); }
        }
        .controls-row .time-display {
            font-size: 0.62rem;
            font-weight: 500;
            color: rgba(255,255,255,0.85);
            padding: 0.1rem 0.4rem;
            letter-spacing: 0.02em;
            min-width: 84px;
            text-align: center;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
        }
        .controls-row .fs-btn { font-size: 0.58rem; color: rgba(255,255,255,0.7); min-height: 30px; }
        .controls-row .fs-btn svg { width: 17px; height: 17px; }
        .controls-row .icon-btn {
            width: 38px;
            height: 38px;
            padding: 0;
        }
        .controls-row .icon-btn svg { fill: currentColor; }
        .controls-row .play-btn {
            width: clamp(42px, 6vw, 52px);
            height: clamp(42px, 6vw, 52px);
            min-width: 42px;
            min-height: 42px;
            padding: 0;
            border-radius: 50%;
            background: rgba(255,255,255,0.16);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        @media (hover: hover) and (pointer: fine) {
            .controls-row .play-btn:hover { background: rgba(255,255,255,0.28); }
        }
        .controls-row .play-btn svg { width: 20px; height: 20px; display: none; }
        .controls-row .play-btn svg.icon-play { margin-left: 2px; }
        .controls-row .play-btn.playing svg.icon-pause { display: block; }
        .controls-row .play-btn.playing svg.icon-play { display: none; }
        .controls-row .play-btn:not(.playing) svg.icon-play { display: block; }
        .volume-group {
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }
        .controls-row .vol-btn {
            width: 36px;
            height: 36px;
            min-height: 36px;
            padding: 0;
            border-radius: 50%;
            color: rgba(255,255,255,0.85);
        }
        .controls-row .vol-btn svg { width: 18px; height: 18px; fill: currentColor; }
        .controls-row .vol-btn.muted { color: rgba(255,255,255,0.4); }
        @media (hover: hover) and (pointer: fine) {
            .controls-row .vol-btn:hover { background: rgba(255,255,255,0.14); }
        }
        .vol-slider {
            width: 80px;
            height: 5px;
            border-radius: 4px;
            background: rgba(255,255,255,0.28);
            cursor: pointer;
            position: relative;
            transition: width 250ms var(--ease);
        }
        .vol-slider .vol-fill {
            height: 100%;
            width: 100%;
            background: var(--acc);
            border-radius: 4px;
            position: relative;
        }
        .vol-slider .vol-fill::after {
            content: '';
            position: absolute;
            right: -4px;
            top: 50%;
            transform: translateY(-50%);
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #fff;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            opacity: 0;
            transition: opacity 200ms var(--ease);
        }
        .vol-slider:hover .vol-fill::after { opacity: 1; }

        /* ===== BUFFERING ===== */
        .buffering-overlay {
            position: absolute;
            inset: 0;
            z-index: 11;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(0,0,0,0.3);
            opacity: 0;
            pointer-events: none;
            transition: opacity 300ms var(--ease);
        }
        .buffering-overlay.visible { opacity: 1; pointer-events: auto; }
        .buffering-spinner {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: 3px solid rgba(255,255,255,0.25);
            border-top-color: #fff;
            animation: buffSpin 0.8s linear infinite;
        }
        @keyframes buffSpin { to { transform: rotate(360deg); } }

        /* ===== CLICK OVERLAY ===== */
        .click-overlay {
            position: absolute;
            inset: 0;
            z-index: 10;
            cursor: pointer;
        }

        /* ===== META BELOW ===== */
        .meta {
            width: min(90vw, 920px);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            opacity: 0;
            transform: translateY(16px);
            animation: metaIn 600ms var(--ease) forwards;
            animation-delay: 300ms;
        }
        @keyframes metaIn { to { opacity: 1; transform: translateY(0); } }
        .meta-title {
            font-size: clamp(0.85rem, 2vw, 1.05rem);
            font-weight: 700;
            letter-spacing: -0.01em;
            color: var(--ink);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 60%;
        }
        .meta-caption {
            font-size: 0.68rem;
            font-weight: 400;
            color: var(--ink-3);
            margin-top: 0.2rem;
        }
        .meta-actions {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            flex-shrink: 0;
        }
        .meta-btn {
            background: var(--ink);
            color: var(--paper);
            border: none;
            border-radius: 999px;
            padding: 0.55rem 1.1rem;
            font-family: inherit;
            font-size: 0.72rem;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            box-shadow: var(--shadow-sm);
            transition: transform 180ms var(--ease), box-shadow 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .meta-btn:hover { transform: translateY(-1px); box-shadow: var(--shadow); }
        }
        .meta-btn:active { transform: scale(0.97); }

        /* ===== TOAST ===== */
        .save-toast {
            position: fixed;
            bottom: 36px;
            left: 50%;
            transform: translate(-50%, 16px);
            background: rgba(29,29,31,0.92);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            color: #fff;
            border-radius: 999px;
            padding: 0.6rem 1.2rem;
            font-family: inherit;
            font-size: 0.78rem;
            font-weight: 500;
            box-shadow: 0 12px 40px rgba(0,0,0,0.25);
            opacity: 0;
            pointer-events: none;
            z-index: 100;
            transition: opacity 300ms var(--ease), transform 400ms var(--ease);
        }
        .save-toast.show { opacity: 1; transform: translate(-50%, 0); }

        @media (max-width: 700px) {
            .app { padding: 0.7rem; gap: 0.9rem; }
            .video-wrapper { width: 100%; border-radius: 20px; }
            .header { padding: 0.7rem 0.8rem; }
            .header-brand .word { font-size: 0.66rem; }
            .header-status { display: none; }
            .controls-wrapper { padding: 0.8rem 0.8rem 0.7rem 0.8rem; }
            .controls-row button { font-size: 0.6rem; min-height: 30px; }
            .controls-row .play-btn { width: 42px; height: 42px; min-width: 42px; min-height: 42px; }
            .controls-row .play-btn svg { width: 18px; height: 18px; }
            .controls-row .vol-btn { width: 32px; height: 32px; min-height: 32px; }
            .controls-row .icon-btn { width: 32px; height: 32px; }
            .vol-slider { width: 56px; }
            .controls-row .time-display { font-size: 0.56rem; min-width: 66px; }
            .center-play { width: 56px; height: 56px; }
            .center-play svg { width: 24px; height: 24px; }
            .meta { width: 100%; flex-direction: column; align-items: flex-start; gap: 0.6rem; }
            .meta-title { max-width: 100%; }
            .meta-actions { width: 100%; }
            .meta-btn { flex: 1; text-align: center; }
            .save-toast { bottom: 20px; }
        }
        @media (max-width: 450px) {
            .controls-row .time-display { font-size: 0.52rem; min-width: 60px; }
            .vol-slider { width: 40px; }
            .quality-badge { display: none; }
        }
        @media (orientation: landscape) and (max-height: 520px) {
            .app { gap: 0.6rem; padding: 0.6rem; }
            .video-wrapper { width: min(86vw, 92vh * 16/9); }
            .meta { width: min(86vw, 92vh * 16/9); }
            .controls-wrapper { padding: 0.6rem 0.9rem 0.5rem 0.9rem; }
            .controls-row button { min-height: 26px; }
            .controls-row .play-btn { width: 38px; height: 38px; min-width: 38px; min-height: 38px; }
            .controls-row .play-btn svg { width: 16px; height: 16px; }
            .controls-row .icon-btn { width: 28px; height: 28px; }
            .controls-row .vol-btn { width: 28px; height: 28px; min-height: 28px; }
            .vol-slider { width: 44px; }
            .meta { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
            .video-wrapper, .meta { animation: none; opacity: 1; transform: none; }
            .header-status .dot { animation: none; }
        }
    </style>
</head>
<body>
<div class="bg-glow"></div>
<div class="app">
    <div class="video-wrapper" id="videoWrapper">
        <video id="player" class="video-js vjs-default-skin" controls autoplay preload="auto" style="width:100%;height:100%;">
            <source src="{{ m3u8_url }}" type="application/x-mpegURL">
        </video>
        <div class="header" id="header">
            <div class="header-brand">
                <span class="word">The House<span class="dot">.</span></span>
                <span class="header-badge">18+</span>
            </div>
            <div class="header-right">
                <span class="quality-badge live" id="qualityBadge">HD · LIVE</span>
                <span class="header-status"><span class="dot"></span> Streaming</span>
                <a href="/" class="back-btn">Back</a>
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
                <button class="seek-btn" id="seekBack">−10</button>
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
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4"/></svg>
                </button>
            </div>
        </div>
    </div>

    <div class="meta">
        <div style="min-width:0;">
            <div class="meta-title" id="videoTitle">Faphouse Video</div>
            <div class="meta-caption">Saved to your library automatically on playback</div>
        </div>
        <div class="meta-actions">
            <a href="/" class="meta-btn">← Back to hub</a>
        </div>
    </div>
</div>

<div class="save-toast" id="saveToast">Added to library</div>

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
                showToast('Added to ' + platform + ' library');
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
        const videoTitleEl = document.getElementById('videoTitle');
        if (videoTitleEl) videoTitleEl.textContent = videoTitle;
        
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
