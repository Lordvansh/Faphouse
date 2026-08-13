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
    <title>Faphouse · The House</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;800;900&family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #07070a;
            --panel: #0e0e13;
            --panel-2: #16161d;
            --line: rgba(255, 255, 255, 0.08);
            --line-strong: rgba(255, 255, 255, 0.16);
            --ink: #f5f5f7;
            --ink-2: #9a9aa3;
            --ink-3: #55555f;
            --fap: #ffd60a;
            --ter: #00a8ff;
            --acc: var(--fap);
            --acc-rgb: 255, 214, 10;
            --ease: cubic-bezier(0.16, 1, 0.3, 1);
            --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
            --mono: "JetBrains Mono", monospace;
            --disp: "Orbitron", sans-serif;
            --body: "Space Grotesk", sans-serif;
        }
        body[data-platform="terabox"] {
            --acc: var(--ter);
            --acc-rgb: 0, 168, 255;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: var(--bg);
            color: var(--ink);
            font-family: var(--body);
            min-height: 100vh;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }
        ::selection { background: var(--acc); color: #07070a; }

        /* ===== BACKGROUND LAYERS ===== */
        .glow {
            position: fixed;
            width: 65vmax;
            height: 65vmax;
            border-radius: 50%;
            filter: blur(90px);
            opacity: 0.12;
            pointer-events: none;
            z-index: 0;
            transition: opacity 0.8s var(--ease);
        }
        .glow-fap { background: radial-gradient(circle, rgba(255, 214, 10, 0.85), transparent 62%); top: -30%; left: 50%; transform: translateX(-50%); }
        .glow-ter { background: radial-gradient(circle, rgba(0, 168, 255, 0.85), transparent 62%); bottom: -32%; right: -14%; }
        body[data-platform="faphouse"] .glow-ter { opacity: 0; }
        body[data-platform="terabox"] .glow-fap { opacity: 0; }
        .grid-bg {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            background-image: radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 34px 34px;
            -webkit-mask-image: radial-gradient(ellipse at center, #000 30%, transparent 80%);
            mask-image: radial-gradient(ellipse at center, #000 30%, transparent 80%);
        }
        #particles { position: fixed; inset: 0; pointer-events: none; z-index: 1; }
        .vignette {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 1;
            background: radial-gradient(ellipse at center, transparent 52%, rgba(0, 0, 0, 0.6) 100%);
        }

        /* ===== HUD CORNERS ===== */
        .hud {
            position: fixed;
            width: 26px;
            height: 26px;
            z-index: 30;
            pointer-events: none;
            opacity: 0.4;
            transition: border-color 0.6s var(--ease);
            animation: hudPulse 5s ease-in-out infinite;
        }
        .hud.tl { top: 14px; left: 14px; border-top: 2px solid var(--acc); border-left: 2px solid var(--acc); border-top-left-radius: 8px; }
        .hud.tr { top: 14px; right: 14px; border-top: 2px solid var(--acc); border-right: 2px solid var(--acc); border-top-right-radius: 8px; }
        .hud.bl { bottom: 14px; left: 14px; border-bottom: 2px solid var(--acc); border-left: 2px solid var(--acc); border-bottom-left-radius: 8px; }
        .hud.br { bottom: 14px; right: 14px; border-bottom: 2px solid var(--acc); border-right: 2px solid var(--acc); border-bottom-right-radius: 8px; }
        @keyframes hudPulse { 0%, 100% { opacity: 0.25; } 50% { opacity: 0.55; } }

        /* ===== SPLASH / BOOT ===== */
        .splash {
            position: fixed;
            inset: 0;
            z-index: 100;
            background: var(--bg);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 1.6rem;
            text-align: center;
            padding: 2rem;
            transition: opacity 0.6s var(--ease), transform 0.8s var(--ease), filter 0.6s var(--ease);
        }
        .splash.leave { opacity: 0; transform: scale(1.06); filter: blur(10px); pointer-events: none; }
        .splash .term {
            font-family: var(--mono);
            font-size: 0.82rem;
            line-height: 1.9;
            color: var(--ink-2);
            min-height: 3.8rem;
            letter-spacing: 0.02em;
        }
        .splash .term .ok { color: var(--acc); }
        .splash .a18-wrap { position: relative; display: flex; }
        .splash .a18-halo {
            position: absolute;
            inset: -40% -15%;
            background: radial-gradient(ellipse at center, rgba(var(--acc-rgb), 0.16), transparent 70%);
            filter: blur(36px);
            animation: breath 3.4s ease-in-out infinite;
            transition: background 0.6s var(--ease);
        }
        @keyframes breath { 0%, 100% { opacity: 0.7; transform: scale(0.98); } 50% { opacity: 1; transform: scale(1.04); } }
        .splash .a18 {
            position: relative;
            font-family: var(--disp);
            font-weight: 900;
            font-size: clamp(5.5rem, 22vw, 12rem);
            line-height: 1;
            letter-spacing: 0.04em;
            display: flex;
        }
        .splash .a18 .l {
            opacity: 0;
            transform: translateY(24px);
            filter: blur(10px);
            color: #fff;
            text-shadow: 0 0 24px rgba(var(--acc-rgb), 0.45);
            transition: opacity 0.5s var(--ease), transform 0.6s var(--spring), filter 0.5s var(--ease);
        }
        .splash .a18.in .l { opacity: 1; transform: none; filter: none; }
        .splash .s-tag {
            font-family: var(--disp);
            font-size: 0.66rem;
            font-weight: 700;
            letter-spacing: 0.5em;
            text-transform: uppercase;
            color: var(--ink-2);
            opacity: 0;
            animation: fadeUp 0.7s var(--ease) forwards;
            animation-delay: 0.9s;
        }
        .splash .s-warn {
            font-size: 0.8rem;
            line-height: 1.7;
            color: var(--ink-3);
            max-width: 380px;
            opacity: 0;
            animation: fadeUp 0.7s var(--ease) forwards;
            animation-delay: 1.05s;
        }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
        .enter-btn {
            margin-top: 0.6rem;
            font-family: var(--disp);
            font-weight: 700;
            font-size: 0.72rem;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            color: #07070a;
            background: var(--acc);
            border: none;
            border-radius: 10px;
            padding: 1rem 2.8rem;
            cursor: pointer;
            box-shadow: 0 8px 34px rgba(var(--acc-rgb), 0.4);
            transition: transform 0.3s var(--spring), box-shadow 0.4s var(--ease), background 0.5s var(--ease);
            opacity: 0;
            animation: fadeUp 0.7s var(--ease) forwards;
            animation-delay: 1.2s;
        }
        @media (hover: hover) and (pointer: fine) {
            .enter-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 50px rgba(var(--acc-rgb), 0.6); }
        }
        .enter-btn:active { transform: scale(0.95); }
        .splash .s-foot {
            position: absolute;
            bottom: 1.6rem;
            font-family: var(--mono);
            font-size: 0.6rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--ink-3);
        }

        /* ===== TOP BAR ===== */
        .topbar {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            z-index: 20;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.2rem 2rem;
            pointer-events: none;
        }
        .brand {
            font-family: var(--disp);
            font-weight: 800;
            font-size: 0.92rem;
            letter-spacing: 0.05em;
            display: flex;
            align-items: baseline;
        }
        .brand .w { color: #fff; }
        .brand .a {
            color: var(--acc);
            text-shadow: 0 0 14px rgba(var(--acc-rgb), 0.5);
            transition: color 0.6s var(--ease), text-shadow 0.6s var(--ease);
        }
        .brand .end { font-family: var(--mono); color: var(--ink-3); font-weight: 400; font-size: 0.62rem; margin-left: 0.6rem; letter-spacing: 0.12em; }
        .top-right { display: flex; align-items: center; gap: 0.7rem; pointer-events: auto; }
        .pill {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--line-strong);
            border-radius: 8px;
            padding: 0.48rem 0.9rem;
            font-family: var(--mono);
            font-size: 0.64rem;
            font-weight: 500;
            color: var(--ink-2);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            transition: border-color 0.4s var(--ease), color 0.4s var(--ease);
        }
        .pill .pdot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--acc);
            box-shadow: 0 0 10px var(--acc);
            animation: pulse 1.6s ease-in-out infinite;
            transition: background 0.5s var(--ease);
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .lib-btn { cursor: pointer; }
        .lib-btn .count {
            background: var(--acc);
            color: #07070a;
            border-radius: 6px;
            font-size: 0.6rem;
            font-weight: 700;
            padding: 0.1rem 0.42rem;
            transition: background 0.5s var(--ease);
        }

        /* ===== STAGE ===== */
        .stage {
            position: relative;
            z-index: 5;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 6.5rem 1.5rem 3rem;
            gap: 1.7rem;
        }

        /* ===== HOLOGRAM SIGN ===== */
        .holo-area {
            position: relative;
            width: 100%;
            height: clamp(120px, 20vw, 185px);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .sign {
            position: absolute;
            inset: 0;
            margin: auto;
            width: max-content;
            height: max-content;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            user-select: none;
            opacity: 0;
            transition: transform 0.9s var(--spring), opacity 0.5s var(--ease);
            will-change: transform;
        }
        .sign.active { opacity: 1; }
        .sign.down { transform: translateY(135%) scale(0.94); opacity: 0; pointer-events: none; }
        .sign .halo {
            position: absolute;
            inset: -45% -10%;
            background: radial-gradient(ellipse at center, rgba(var(--acc-rgb), 0.12), transparent 70%);
            filter: blur(34px);
            animation: breath 4s ease-in-out infinite;
            transition: background 0.6s var(--ease);
            pointer-events: none;
        }
        .parallax { transform-style: preserve-3d; will-change: transform; }
        .float { animation: floatBob 6s ease-in-out infinite; will-change: transform; }
        @keyframes floatBob {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-9px); }
        }
        .wordmark {
            position: relative;
            font-family: var(--disp);
            font-weight: 900;
            font-size: clamp(2.3rem, 8.8vw, 6rem);
            line-height: 1;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .wordmark.glitch { animation: holoGlitch 0.4s steps(2, end); }
        @keyframes holoGlitch {
            0% { clip-path: inset(0 0 0 0); transform: translate(0); }
            20% { clip-path: inset(8% 0 62% 0); transform: translate(-8px, 2px); }
            40% { clip-path: inset(55% 0 12% 0); transform: translate(6px, -2px); }
            60% { clip-path: inset(28% 0 46% 0); transform: translate(-5px, 1px); }
            80% { clip-path: inset(70% 0 4% 0); transform: translate(7px, -1px); }
            100% { clip-path: inset(0 0 0 0); transform: translate(0); }
        }
        .wordmark .word { display: inline-flex; }
        .wordmark .word .l {
            display: inline-block;
            opacity: 0;
            transform: translateY(26px);
            filter: blur(8px);
            transition: opacity 0.45s var(--ease), transform 0.6s var(--spring), filter 0.45s var(--ease);
        }
        .wordmark.in .word .l { opacity: 1; transform: none; filter: none; }
        .word.white .l { color: #f5f5f7; text-shadow: 0 0 18px rgba(255, 255, 255, 0.25); }
        .word.accent .l { color: var(--acc); text-shadow: 0 0 20px rgba(var(--acc-rgb), 0.45); }
        .wordmark .scan {
            position: absolute;
            left: -6%;
            right: -6%;
            height: 34%;
            top: -12%;
            background: linear-gradient(180deg, transparent, rgba(var(--acc-rgb), 0.12), transparent);
            animation: scanSweep 5s ease-in-out infinite;
            pointer-events: none;
            mix-blend-mode: screen;
        }
        @keyframes scanSweep {
            0% { top: -20%; opacity: 0; }
            8% { opacity: 1; }
            48% { opacity: 1; }
            58% { opacity: 0; }
            100% { top: 110%; opacity: 0; }
        }
        .sign-reflection {
            position: absolute;
            top: 103%;
            left: 0;
            right: 0;
            transform: scaleY(-1);
            opacity: 0.12;
            filter: blur(2px);
            -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,0.5), transparent 70%);
            mask-image: linear-gradient(to bottom, rgba(0,0,0,0.5), transparent 70%);
            pointer-events: none;
        }
        .sign-reflection .l { opacity: 0.5 !important; transition: none !important; filter: none !important; }
        .sign-reflection .word.white .l { color: #888; text-shadow: none; }
        .sign-reflection .word.accent .l { color: var(--acc); text-shadow: none; }

        /* ===== BOOT BAR ===== */
        .boot {
            width: min(460px, 86vw);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.5rem;
            min-height: 2.6rem;
            opacity: 0;
            transition: opacity 0.3s var(--ease);
        }
        .boot.run { opacity: 1; }
        .boot-label {
            font-family: var(--mono);
            font-size: 0.64rem;
            color: var(--ink-2);
            letter-spacing: 0.06em;
        }
        .boot-track {
            width: 100%;
            height: 3px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 3px;
            overflow: hidden;
        }
        .boot-fill {
            display: block;
            width: 0%;
            height: 100%;
            background: var(--acc);
            box-shadow: 0 0 12px rgba(var(--acc-rgb), 0.8);
            border-radius: 3px;
            transition: background 0.5s var(--ease);
        }
        .boot.run .boot-fill { animation: bootFill 1.05s var(--ease) forwards; }
        @keyframes bootFill { from { width: 0%; } to { width: 100%; } }

        /* ===== TAGLINE ===== */
        .tagline {
            position: relative;
            height: 1.4rem;
            font-family: var(--disp);
            font-size: 0.62rem;
            font-weight: 700;
            letter-spacing: 0.5em;
            text-transform: uppercase;
            color: var(--ink-2);
            text-align: center;
        }
        .tagline > span { position: absolute; inset: 0; transition: opacity 0.45s var(--ease); opacity: 0; }
        body[data-platform="faphouse"] .tagline .tag-fap { opacity: 1; }
        body[data-platform="terabox"] .tagline .tag-ter { opacity: 1; }

        /* ===== SWITCH BUTTON ===== */
        .switch-btn {
            display: flex;
            align-items: center;
            gap: 0.55rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--line-strong);
            color: var(--ink-2);
            border-radius: 8px;
            padding: 0.5rem 1.15rem;
            font-family: var(--mono);
            font-size: 0.7rem;
            font-weight: 500;
            cursor: pointer;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            transition: border-color 0.4s var(--ease), color 0.4s var(--ease), transform 0.3s var(--spring), box-shadow 0.5s var(--ease);
            touch-action: manipulation;
        }
        .switch-btn .sdot {
            width: 8px;
            height: 8px;
            border-radius: 2px;
            background: var(--acc);
            box-shadow: 0 0 12px var(--acc);
            transform: rotate(45deg);
            transition: background 0.5s var(--ease);
        }
        .switch-btn .arrow { transition: transform 0.4s var(--ease); font-size: 0.85rem; }
        @media (hover: hover) and (pointer: fine) {
            .switch-btn:hover { border-color: var(--acc); color: #fff; box-shadow: 0 0 24px rgba(var(--acc-rgb), 0.2); }
            .switch-btn:hover .arrow { transform: translateY(3px); }
        }
        .switch-btn:active { transform: scale(0.95); }

        /* ===== DECK / URL PASTER ===== */
        .deck {
            width: min(680px, 94vw);
            display: flex;
            align-items: center;
            background: var(--panel);
            border: 1px solid var(--line-strong);
            border-radius: 12px;
            padding: 0.45rem 0.45rem 0.45rem 1.2rem;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            transition: border-color 0.5s var(--ease), box-shadow 0.5s var(--ease);
        }
        .deck:focus-within {
            border-color: var(--acc);
            box-shadow: 0 0 0 3px rgba(var(--acc-rgb), 0.12), 0 0 26px rgba(var(--acc-rgb), 0.14), 0 24px 70px rgba(0, 0, 0, 0.55);
        }
        .deck-prefix {
            font-family: var(--mono);
            font-weight: 700;
            font-size: 0.74rem;
            color: var(--acc);
            text-shadow: 0 0 10px rgba(var(--acc-rgb), 0.6);
            white-space: nowrap;
            transition: color 0.5s var(--ease);
        }
        .deck-input {
            flex: 1;
            min-width: 0;
            background: transparent;
            border: none;
            outline: none;
            color: #fff;
            font-family: var(--mono);
            font-size: 0.88rem;
            padding: 0.85rem 0.8rem;
        }
        .deck-input::placeholder { color: var(--ink-3); }
        .launch-btn {
            background: var(--acc);
            color: #07070a;
            border: none;
            border-radius: 9px;
            padding: 0.95rem 1.7rem;
            font-family: var(--disp);
            font-weight: 800;
            font-size: 0.7rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            cursor: pointer;
            white-space: nowrap;
            box-shadow: 0 0 20px rgba(var(--acc-rgb), 0.4);
            transition: transform 0.3s var(--spring), background 0.5s var(--ease), box-shadow 0.5s var(--ease), opacity 0.4s var(--ease);
            touch-action: manipulation;
        }
        @media (hover: hover) and (pointer: fine) {
            .launch-btn:hover { transform: translateY(-1px); box-shadow: 0 0 38px rgba(var(--acc-rgb), 0.6); }
        }
        .launch-btn:active { transform: scale(0.95); }
        .launch-btn.loading { opacity: 0.55; pointer-events: none; animation: loadPulse 0.9s ease-in-out infinite; }
        @keyframes loadPulse { 0%, 100% { opacity: 0.55; } 50% { opacity: 0.9; } }

        .hint {
            display: flex;
            align-items: center;
            gap: 1.1rem;
            font-family: var(--mono);
            font-size: 0.64rem;
            color: var(--ink-3);
            flex-wrap: wrap;
            justify-content: center;
        }
        .hint kbd {
            background: var(--panel-2);
            border: 1px solid var(--line-strong);
            border-radius: 4px;
            padding: 0.1rem 0.4rem;
            font-size: 0.6rem;
            color: var(--ink-2);
            font-family: inherit;
        }

        .log {
            font-family: var(--mono);
            font-size: 0.66rem;
            color: var(--ink-3);
            letter-spacing: 0.04em;
        }
        .log .cur { color: var(--acc); animation: blink 1s steps(1) infinite; }
        @keyframes blink { 50% { opacity: 0; } }

        /* ===== LIBRARY DRAWER ===== */
        .scrim {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.55);
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
            z-index: 55;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.45s var(--ease);
        }
        .scrim.open { opacity: 1; pointer-events: auto; }
        .drawer {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            width: min(400px, 92vw);
            background: rgba(10, 10, 15, 0.92);
            backdrop-filter: blur(26px);
            -webkit-backdrop-filter: blur(26px);
            border-left: 1px solid var(--line-strong);
            transform: translateX(103%);
            transition: transform 0.55s var(--spring);
            z-index: 60;
            display: flex;
            flex-direction: column;
            padding: 1.5rem;
        }
        .drawer.open { transform: none; }
        .drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem; }
        .drawer-title { font-family: var(--disp); font-weight: 800; font-size: 0.8rem; letter-spacing: 0.08em; }
        .drawer-title .a { color: var(--acc); text-shadow: 0 0 12px rgba(var(--acc-rgb), 0.6); transition: color 0.5s var(--ease); }
        .icon-btn {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--line-strong);
            border-radius: 8px;
            color: var(--ink-2);
            width: 34px;
            height: 34px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            transition: border-color 0.3s var(--ease), color 0.3s var(--ease), transform 0.3s var(--spring);
        }
        @media (hover: hover) and (pointer: fine) {
            .icon-btn:hover { border-color: var(--acc); color: #fff; }
        }
        .icon-btn:active { transform: scale(0.9) rotate(-90deg); }
        .drawer-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 0.55rem; scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.15) transparent; }
        .drawer-item {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 0.7rem 0.9rem;
            text-decoration: none;
            color: var(--ink);
            transition: border-color 0.3s var(--ease), transform 0.3s var(--spring);
        }
        @media (hover: hover) and (pointer: fine) {
            .drawer-item:hover { border-color: var(--acc); transform: translateX(-3px); }
        }
        .drawer-item .itag {
            flex-shrink: 0;
            font-family: var(--mono);
            font-size: 0.52rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }
        .itag.fap { background: rgba(255, 214, 10, 0.14); color: #ffd60a; }
        .itag.ter { background: rgba(0, 168, 255, 0.14); color: #00a8ff; }
        .drawer-item .ititle { font-size: 0.78rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .drawer-item .itime { font-family: var(--mono); font-size: 0.6rem; color: var(--ink-3); flex-shrink: 0; }
        .drawer-empty { font-size: 0.8rem; color: var(--ink-3); text-align: center; padding: 2rem 0; }

        .foot {
            position: relative;
            z-index: 5;
            text-align: center;
            padding: 0 1rem 1.4rem;
            font-family: var(--mono);
            font-size: 0.58rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--ink-3);
        }

        @media (max-width: 640px) {
            .topbar { padding: 1rem 1.1rem; }
            .topbar .brand { font-size: 0.82rem; }
            .pill .pdot { display: none; }
            .stage { gap: 1.5rem; padding: 5.5rem 1rem 2rem; }
            .holo-area { height: clamp(80px, 24vw, 140px); }
            .deck { padding: 0.4rem 0.4rem 0.4rem 1rem; }
            .deck-input { font-size: 0.8rem; }
            .launch-btn { padding: 0.9rem 1.2rem; font-size: 0.66rem; }
            .hint { gap: 0.7rem; }
            .sign-reflection { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
            .splash .a18 .l, .splash .s-tag, .splash .s-warn, .enter-btn { animation: none; opacity: 1; transform: none; filter: none; }
            .wordmark .word .l { transition: none; opacity: 1; transform: none; filter: none; }
            .float, .scan, .pill .pdot, .sign .halo, .splash .a18-halo, .hud, .glow { animation: none; }
            .sign { transition: opacity 0.4s var(--ease); }
        }
    </style>
</head>
<body data-platform="faphouse">
<div class="glow glow-fap"></div>
<div class="glow glow-ter"></div>
<div class="grid-bg"></div>
<canvas id="particles"></canvas>
<div class="vignette"></div>
<div class="hud tl"></div><div class="hud tr"></div><div class="hud bl"></div><div class="hud br"></div>

<div class="splash" id="splash">
    <div class="term" id="termLines"><span class="ok">&gt;</span> INITIALIZING THE HOUSE…</div>
    <div class="a18-wrap">
        <div class="a18-halo"></div>
        <div class="a18" id="a18">18+</div>
    </div>
    <div class="s-tag">Adult Content</div>
    <div class="s-warn">This site contains adult material. You must be 18 or older to continue. By entering, you agree to our Terms of Service and Privacy Policy.</div>
    <button class="enter-btn" id="enterBtn">Enter</button>
    <div class="s-foot">18 U.S.C. §2257 Record Keeping</div>
</div>

<header class="topbar">
    <div class="brand">
        <span class="w">FAP</span><span class="a">HOUSE</span>
        <span class="end">THE HOUSE</span>
    </div>
    <div class="top-right">
        <div class="pill"><span class="pdot"></span><span id="statusText">STREAM ONLINE</span></div>
        <div class="pill" id="clockPill"><span id="clockText">--:--:--</span></div>
        <button class="pill lib-btn" id="libraryBtn">LIB <span class="count" id="libraryBadge">0</span></button>
    </div>
</header>

<main class="stage">
    <div class="holo-area">
        <div class="sign active in" id="gateFaphouse">
            <div class="halo"></div>
            <div class="parallax">
                <div class="float">
                    <div class="wordmark" id="wmFaphouse">
                        <span class="word white">FAP</span>
                        <span class="word accent">HOUSE</span>
                        <span class="scan"></span>
                    </div>
                </div>
            </div>
            <div class="sign-reflection">
                <span class="word white">FAP</span>
                <span class="word accent">HOUSE</span>
            </div>
        </div>
        <div class="sign down" id="gateTerabox">
            <div class="halo"></div>
            <div class="parallax">
                <div class="float">
                    <div class="wordmark" id="wmTerabox">
                        <span class="word white">TERA</span>
                        <span class="word accent">BOX</span>
                        <span class="scan"></span>
                    </div>
                </div>
            </div>
            <div class="sign-reflection">
                <span class="word white">TERA</span>
                <span class="word accent">BOX</span>
            </div>
        </div>
    </div>

    <div class="boot" id="bootBar">
        <span class="boot-label" id="bootLabel">&gt; MOUNTING MODULE…</span>
        <span class="boot-track"><span class="boot-fill" id="bootFill"></span></span>
    </div>

    <div class="tagline">
        <span class="tag-fap">Premium · Live · HD</span>
        <span class="tag-ter">Files · Mirrors · Cloud</span>
    </div>

    <button class="switch-btn" id="platformSwitch">
        <span class="sdot"></span>
        <span class="label" id="switchLabel">Terabox</span>
        <span class="arrow">↓</span>
    </button>

    <form class="deck" id="urlForm" method="GET" action="/play">
        <span class="deck-prefix" id="deckPrefix">fap://</span>
        <input class="deck-input" id="videoUrlInput" name="url" type="text" spellcheck="false" autocomplete="off" placeholder="Paste a Faphouse or Terabox link here…" value="{{ video_url or '' }}">
        <button type="submit" class="launch-btn" id="loadBtn">Launch</button>
    </form>

    <div class="hint">
        <span><kbd>F</kbd> Faphouse</span>
        <span><kbd>T</kbd> Terabox</span>
        <span><kbd>Enter</kbd> Launch</span>
        <span>Paste a link to auto-switch</span>
    </div>

    <div class="log"><span id="logLine">&gt; MODULE FAPHOUSE — ONLINE</span><span class="cur">▌</span></div>
</main>

<footer class="foot">Faphouse · The House of Adult Streaming</footer>

<div class="scrim" id="scrim"></div>
<aside class="drawer" id="libraryDrawer">
    <div class="drawer-head">
        <div class="drawer-title">My <span class="a">Library</span></div>
        <button class="icon-btn" id="refreshLibraryBtn" title="Refresh">↻</button>
    </div>
    <div class="drawer-list" id="libraryList"></div>
</aside>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // ===== CORE REFS =====
    var splash = document.getElementById('splash');
    var enterBtn = document.getElementById('enterBtn');
    var gateFaphouse = document.getElementById('gateFaphouse');
    var gateTerabox = document.getElementById('gateTerabox');
    var wmFaphouse = document.getElementById('wmFaphouse');
    var wmTerabox = document.getElementById('wmTerabox');
    var switchBtn = document.getElementById('platformSwitch');
    var switchLabel = document.getElementById('switchLabel');
    var deckPrefix = document.getElementById('deckPrefix');
    var videoUrlInput = document.getElementById('videoUrlInput');
    var urlForm = document.getElementById('urlForm');
    var loadBtn = document.getElementById('loadBtn');
    var clockText = document.getElementById('clockText');
    var libraryBadge = document.getElementById('libraryBadge');
    var libraryBtn = document.getElementById('libraryBtn');
    var libraryDrawer = document.getElementById('libraryDrawer');
    var libraryList = document.getElementById('libraryList');
    var refreshLibraryBtn = document.getElementById('refreshLibraryBtn');
    var scrim = document.getElementById('scrim');
    var bootBar = document.getElementById('bootBar');
    var bootLabel = document.getElementById('bootLabel');
    var logLine = document.getElementById('logLine');
    var termLines = document.getElementById('termLines');

    var currentPlatform = 'faphouse';

    // ===== LETTER BUILD =====
    function splitLetters(root) {
        var words = root.querySelectorAll('.word');
        var idx = 0;
        words.forEach(function(word) {
            var text = word.textContent;
            word.textContent = '';
            for (var i = 0; i < text.length; i++) {
                var s = document.createElement('span');
                s.className = 'l';
                s.style.transitionDelay = (idx * 55) + 'ms';
                s.textContent = text[i];
                word.appendChild(s);
                idx++;
            }
        });
    }
    splitLetters(gateFaphouse);
    splitLetters(gateTerabox);
    splitLetters(gateFaphouse.querySelector('.sign-reflection'));
    splitLetters(gateTerabox.querySelector('.sign-reflection'));
    var a18 = document.getElementById('a18');
    if (a18) splitLetters(a18);

    // ===== SPLASH BOOT TYPING =====
    var bootLines = [
        { t: '> INITIALIZING THE HOUSE…', ok: false },
        { t: '> ADULT CONTENT DETECTED', ok: true },
        { t: '> AGE VERIFICATION REQUIRED', ok: true }
    ];
    var li = 0, ci = 0;
    function typeStep() {
        if (li >= bootLines.length) { revealSplash(); return; }
        var line = bootLines[li];
        ci++;
        termLines.innerHTML = line.t.slice(0, ci).replace(/>/, '<span class="ok">&gt;</span>');
        if (ci >= line.t.length) { li++; ci = 0; }
        setTimeout(typeStep, 26);
    }
    function revealSplash() {
        if (a18) a18.classList.add('in');
        setTimeout(function() { enterBtn.style.opacity = '1'; }, 400);
    }
    setTimeout(typeStep, 300);

    // ===== ENTER =====
    function enterApp() {
        if (splash) splash.classList.add('leave');
        gateFaphouse.classList.add('in');
        setTimeout(function() {
            if (splash) splash.style.display = 'none';
        }, 800);
        try { sessionStorage.setItem('fap18', '1'); } catch (e) {}
    }
    enterBtn.addEventListener('click', enterApp);
    try {
        if (sessionStorage.getItem('fap18') === '1') enterApp();
    } catch (e) {}

    // ===== PLATFORM SWAP =====
    function setPlatform(platform) {
        if (platform === currentPlatform) return;
        currentPlatform = platform;
        document.body.dataset.platform = platform;
        deckPrefix.textContent = platform === 'faphouse' ? 'fap://' : 'tera://';
        switchLabel.textContent = platform === 'faphouse' ? 'Terabox' : 'Faphouse';
        bootLabel.textContent = '> MOUNTING ' + platform.toUpperCase() + ' MODULE…';
        logLine.textContent = '> MOUNTING ' + platform.toUpperCase() + ' MODULE…';
        bootBar.classList.add('run');
        var out, inn, wmOut, wmIn;
        if (platform === 'faphouse') { out = gateTerabox; inn = gateFaphouse; wmOut = wmTerabox; wmIn = wmFaphouse; }
        else { out = gateFaphouse; inn = gateTerabox; wmOut = wmFaphouse; wmIn = wmTerabox; }
        wmOut.classList.add('glitch');
        setTimeout(function() {
            out.classList.remove('active', 'in');
            out.classList.add('down');
            inn.classList.remove('down');
            inn.classList.add('active', 'in');
            wmIn.classList.add('glitch');
            setTimeout(function() {
                wmIn.classList.remove('glitch');
                wmOut.classList.remove('glitch');
            }, 450);
        }, 420);
        setTimeout(function() {
            bootBar.classList.remove('run');
            logLine.textContent = '> MODULE ' + platform.toUpperCase() + ' — ONLINE';
        }, 1500);
    }

    gateFaphouse.addEventListener('click', function() { setPlatform('faphouse'); });
    gateTerabox.addEventListener('click', function() { setPlatform('terabox'); });
    switchBtn.addEventListener('click', function() {
        setPlatform(currentPlatform === 'faphouse' ? 'terabox' : 'faphouse');
    });

    // ===== AUTO-DETECT =====
    function detectPlatform(url) {
        if (!url) return null;
        if (/terabox|terafileshare|terafile|teracloud|filemirror/i.test(url)) return 'terabox';
        if (/faphouse|fap-house|fap/i.test(url)) return 'faphouse';
        return null;
    }
    videoUrlInput.addEventListener('input', function() {
        var p = detectPlatform(videoUrlInput.value);
        if (p) setPlatform(p);
    });
    videoUrlInput.addEventListener('paste', function() {
        var self = this;
        setTimeout(function() {
            var p = detectPlatform(self.value);
            if (p) setPlatform(p);
        }, 50);
    });

    // ===== LAUNCH =====
    urlForm.addEventListener('submit', function(e) {
        loadBtn.classList.add('loading');
        urlForm.action = currentPlatform === 'terabox' ? '/terabox' : '/play';
    });

    // ===== LIBRARY =====
    function getLibrary(platform) {
        try {
            var key = platform === 'faphouse' ? 'faphouseLibrary' : 'teraboxLibrary';
            return JSON.parse(localStorage.getItem(key) || '[]');
        } catch (e) { return []; }
    }
    function renderLibrary() {
        var items = [];
        ['faphouse', 'terabox'].forEach(function(pl) {
            getLibrary(pl).forEach(function(v) { items.push({ v: v, pl: pl }); });
        });
        libraryBadge.textContent = String(items.length);
        libraryList.innerHTML = '';
        if (items.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'drawer-empty';
            empty.textContent = 'No saved videos yet.';
            libraryList.appendChild(empty);
            return;
        }
        items.slice(0, 50).forEach(function(it) {
            var a = document.createElement('a');
            a.className = 'drawer-item';
            var target = it.v.url || it.v.videoUrl || '';
            a.href = (it.pl === 'faphouse' ? '/play?url=' : '/terabox?url=') + encodeURIComponent(target);
            var tag = document.createElement('span');
            tag.className = 'itag ' + (it.pl === 'faphouse' ? 'fap' : 'ter');
            tag.textContent = it.pl === 'faphouse' ? 'FAP' : 'TERA';
            var title = document.createElement('span');
            title.className = 'ititle';
            title.textContent = it.v.title || 'Saved video';
            var time = document.createElement('span');
            time.className = 'itime';
            time.textContent = it.v.watchedAt ? new Date(it.v.watchedAt).toLocaleDateString() : '';
            a.appendChild(tag);
            a.appendChild(title);
            a.appendChild(time);
            libraryList.appendChild(a);
        });
    }
    renderLibrary();
    refreshLibraryBtn.addEventListener('click', renderLibrary);
    function toggleDrawer(open) {
        var o = open !== undefined ? open : !libraryDrawer.classList.contains('open');
        libraryDrawer.classList.toggle('open', o);
        scrim.classList.toggle('open', o);
    }
    libraryBtn.addEventListener('click', function() { toggleDrawer(); });
    scrim.addEventListener('click', function() { toggleDrawer(false); });

    // ===== CLOCK =====
    function tick() {
        var d = new Date();
        var p = function(n) { return String(n).padStart(2, '0'); };
        clockText.textContent = p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds());
    }
    tick();
    setInterval(tick, 1000);

    // ===== 3D PARALLAX =====
    var canParallax = false;
    try {
        canParallax = window.matchMedia('(hover: hover) and (pointer: fine)').matches &&
                      !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) {}
    if (canParallax) {
        var pWrap = [gateFaphouse.querySelector('.parallax'), gateTerabox.querySelector('.parallax')];
        var tx = 0, ty = 0, cx = 0, cy = 0;
        document.addEventListener('mousemove', function(e) {
            tx = (e.clientX / window.innerWidth - 0.5);
            ty = (e.clientY / window.innerHeight - 0.5);
        });
        function pLoop() {
            cx += (tx - cx) * 0.07;
            cy += (ty - cy) * 0.07;
            var rx = -cy * 7;
            var ry = cx * 10;
            pWrap.forEach(function(el) {
                el.style.transform = 'rotateX(' + rx + 'deg) rotateY(' + ry + 'deg)';
            });
            requestAnimationFrame(pLoop);
        }
        pLoop();
    }

    // ===== PARTICLES =====
    var reduce = false;
    try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
    if (!reduce) {
        var canvas = document.getElementById('particles');
        var ctx = null;
        try { ctx = canvas && canvas.getContext ? canvas.getContext('2d') : null; } catch (e) {}
        if (!ctx) { /* particles unavailable */ }
        else {
            var W, H, parts = [];
        function sizeCanvas() {
            W = window.innerWidth; H = window.innerHeight;
            var dpr = Math.min(window.devicePixelRatio || 1, 2);
            canvas.width = W * dpr; canvas.height = H * dpr;
            canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
        function seedParts() {
            parts = [];
            var n = Math.min(46, Math.floor(W / 26));
            for (var i = 0; i < n; i++) {
                parts.push({
                    x: Math.random() * W,
                    y: Math.random() * H,
                    r: Math.random() * 1.5 + 0.4,
                    vy: -(Math.random() * 0.3 + 0.06),
                    vx: (Math.random() - 0.5) * 0.12,
                    a: Math.random() * 0.35 + 0.12
                });
            }
        }
        function drawParticles() {
            ctx.clearRect(0, 0, W, H);
            for (var i = 0; i < parts.length; i++) {
                var p = parts[i];
                p.y += p.vy; p.x += p.vx;
                if (p.y < -4) { p.y = H + 4; p.x = Math.random() * W; }
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, 6.2832);
                ctx.fillStyle = 'rgba(255,255,255,' + p.a + ')';
                ctx.fill();
            }
            requestAnimationFrame(drawParticles);
        }
        sizeCanvas();
        seedParts();
        drawParticles();
        window.addEventListener('resize', function() { sizeCanvas(); seedParts(); });
        }
    }

    // ===== KEYBOARD =====
    document.addEventListener('keydown', function(e) {
        if (e.key === 'f' || e.key === 'F') setPlatform('faphouse');
        if (e.key === 't' || e.key === 'T') setPlatform('terabox');
    });
});
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
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;800;900&family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://vjs.zencdn.net/8.0.0/video-js.css" rel="stylesheet" />
    <style>
        :root {
            --bg: #07070a;
            --ink: #f5f5f7;
            --ink-2: #9a9aa3;
            --acc: #ffd60a;
            --acc-rgb: 255, 214, 10;
            --line: rgba(255, 255, 255, 0.1);
            --ease: cubic-bezier(0.16, 1, 0.3, 1);
            --spring: cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: var(--bg);
            font-family: "Space Grotesk", -apple-system, sans-serif;
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
            background: radial-gradient(ellipse at center, rgba(var(--acc-rgb), 0.12), transparent 62%);
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
            border-radius: 24px;
            overflow: hidden;
            border: 1px solid var(--line);
            box-shadow: 0 30px 90px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(0,0,0,0.6);
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
            background: linear-gradient(180deg, rgba(0,0,0,0.72) 0%, transparent 100%);
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
        .header-brand .word { font-family: "Orbitron", sans-serif;
            font-weight: 800;
            font-size: 0.66rem;
            letter-spacing: 0.02em;
            color: #fff;
        }
        .header-brand .dot { color: var(--acc); text-shadow: 0 0 12px rgba(255,214,10,0.6); }
        .header-badge { font-family: "Orbitron", sans-serif;
            font-size: 0.55rem;
            font-weight: 800;
            color: #0a0a0b;
            background: var(--acc);
            border-radius: 999px;
            padding: 0.12rem 0.4rem;
        }
        .header-right { display: flex; align-items: center; gap: 0.5rem; }
        .quality-badge { font-family: "Orbitron", sans-serif;
            font-size: 0.55rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--acc);
            background: rgba(20,20,22,0.55);
            backdrop-filter: blur(16px) saturate(160%);
            -webkit-backdrop-filter: blur(16px) saturate(160%);
            border: 1px solid rgba(var(--acc-rgb), 0.35);
            border-radius: 999px;
            padding: 0.3rem 0.7rem;
        }
        .quality-badge.live { color: var(--acc); }
        .header-status {
            font-size: 0.55rem;
            font-weight: 600;
            color: rgba(255,255,255,0.8);
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
            background: var(--acc);
            box-shadow: 0 0 10px var(--acc);
            animation: pulse 1.5s ease-in-out infinite;
            display: inline-block;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
        .back-btn {
            background: rgba(20,20,22,0.55);
            backdrop-filter: blur(16px) saturate(160%);
            -webkit-backdrop-filter: blur(16px) saturate(160%);
            border: 1px solid rgba(255,255,255,0.12);
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
            transition: transform 180ms var(--ease), background 250ms var(--ease), border-color 250ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .back-btn:hover { background: rgba(20,20,22,0.78); border-color: var(--acc); }
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
            background: var(--acc);
            border: none;
            color: #0a0a0b;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 0 6px rgba(var(--acc-rgb), 0.2), 0 14px 50px rgba(var(--acc-rgb), 0.5);
            opacity: 0;
            pointer-events: none;
            transition: opacity 250ms var(--ease), transform 250ms var(--ease);
        }
        .center-play.visible { opacity: 1; pointer-events: auto; }
        @media (hover: hover) and (pointer: fine) {
            .center-play:hover { transform: translate(-50%, -50%) scale(1.06); }
        }
        .center-play:active { transform: translate(-50%, -50%) scale(0.94); }
        .center-play svg { width: 30px; height: 30px; fill: currentColor; margin-left: 4px; }

        /* ===== CONTROLS (overlay) ===== */
        .controls-wrapper {
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 20;
            padding: 1rem 1rem 0.9rem 1rem;
            background: linear-gradient(0deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.2) 70%, transparent 100%);
            opacity: 0;
            transition: opacity 300ms var(--ease);
        }
        .controls-wrapper.visible { opacity: 1; }
        .progress-section { width: 100%; padding: 0 0 0.55rem 0; }
        .progress-track {
            position: relative;
            width: 100%;
            height: 5px;
            background: rgba(255,255,255,0.22);
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
            box-shadow: 0 0 12px rgba(var(--acc-rgb), 0.7);
        }
        .progress-buffer {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            width: 0%;
            background: rgba(255,255,255,0.35);
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
            background: var(--acc);
            box-shadow: 0 2px 10px rgba(var(--acc-rgb), 0.8);
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
        .controls-row button:active { transform: scale(0.92); color: var(--acc); }
        .controls-row .seek-btn {
            font-size: 0.6rem;
            color: rgba(255,255,255,0.7);
            padding: 0.25rem 0.5rem;
            min-height: 30px;
        }
        @media (hover: hover) and (pointer: fine) {
            .controls-row .seek-btn:hover { color: var(--acc); background: rgba(255,255,255,0.1); }
        }
        .controls-row .time-display { font-family: "JetBrains Mono", monospace;
            font-size: 0.62rem;
            font-weight: 500;
            color: rgba(255,255,255,0.9);
            padding: 0.1rem 0.4rem;
            letter-spacing: 0.04em;
            min-width: 84px;
            text-align: center;
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
        }
        .controls-row .fs-btn { font-size: 0.58rem; color: rgba(255,255,255,0.7); min-height: 30px; }
        .controls-row .fs-btn svg { width: 17px; height: 17px; }
        .controls-row .icon-btn { width: 38px; height: 38px; padding: 0; }
        .controls-row .icon-btn svg { fill: currentColor; }
        .controls-row .play-btn {
            width: clamp(42px, 6vw, 52px);
            height: clamp(42px, 6vw, 52px);
            min-width: 42px;
            min-height: 42px;
            padding: 0;
            border-radius: 50%;
            background: var(--acc);
            color: #0a0a0b;
            box-shadow: 0 0 0 5px rgba(var(--acc-rgb), 0.18), 0 6px 26px rgba(var(--acc-rgb), 0.5);
        }
        @media (hover: hover) and (pointer: fine) {
            .controls-row .play-btn:hover { background: #ffe14d; color: #0a0a0b; }
        }
        .controls-row .play-btn svg { width: 20px; height: 20px; display: none; }
        .controls-row .play-btn svg.icon-play { margin-left: 2px; }
        .controls-row .play-btn.playing svg.icon-pause { display: block; }
        .controls-row .play-btn.playing svg.icon-play { display: none; }
        .controls-row .play-btn:not(.playing) svg.icon-play { display: block; }
        .volume-group { display: flex; align-items: center; gap: 0.4rem; }
        .controls-row .vol-btn {
            width: 36px;
            height: 36px;
            min-height: 36px;
            padding: 0;
            border-radius: 50%;
            color: rgba(255,255,255,0.85);
        }
        .controls-row .vol-btn svg { width: 18px; height: 18px; fill: currentColor; }
        .controls-row .vol-btn.muted { color: rgba(255,255,255,0.35); }
        @media (hover: hover) and (pointer: fine) {
            .controls-row .vol-btn:hover { background: rgba(255,255,255,0.12); color: var(--acc); }
        }
        .vol-slider {
            width: 80px;
            height: 5px;
            border-radius: 4px;
            background: rgba(255,255,255,0.22);
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
            background: var(--acc);
            box-shadow: 0 0 8px rgba(var(--acc-rgb), 0.7);
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
            background: rgba(0,0,0,0.35);
            opacity: 0;
            pointer-events: none;
            transition: opacity 300ms var(--ease);
        }
        .buffering-overlay.visible { opacity: 1; pointer-events: auto; }
        .buffering-spinner {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            border: 3px solid rgba(var(--acc-rgb), 0.25);
            border-top-color: var(--acc);
            animation: buffSpin 0.8s linear infinite;
        }
        @keyframes buffSpin { to { transform: rotate(360deg); } }

        /* ===== CLICK OVERLAY ===== */
        .click-overlay { position: absolute; inset: 0; z-index: 10; cursor: pointer; }

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
        .meta-title { font-family: "Orbitron", sans-serif;
            font-weight: 700;
            font-size: clamp(0.82rem, 2vw, 1rem);
            letter-spacing: 0.01em;
            color: var(--ink);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 60%;
        }
        .meta-title .a { color: var(--acc); text-shadow: 0 0 14px rgba(255,214,10,0.6); }
        .meta-caption {
            font-size: 0.68rem;
            font-weight: 400;
            color: var(--ink-2);
            margin-top: 0.25rem;
        }
        .meta-actions { display: flex; align-items: center; gap: 0.6rem; flex-shrink: 0; }
        .meta-btn { font-family: "Orbitron", sans-serif;
            background: var(--acc);
            color: #0a0a0b;
            border: none;
            border-radius: 999px;
            padding: 0.55rem 1.1rem;
            font-family: "Space Grotesk", sans-serif;
            font-weight: 700;
            font-size: 0.64rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 8px 28px rgba(var(--acc-rgb), 0.35);
            transition: transform 180ms var(--ease), box-shadow 300ms var(--ease);
        }
        @media (hover: hover) and (pointer: fine) {
            .meta-btn:hover { transform: translateY(-1px); box-shadow: 0 12px 40px rgba(var(--acc-rgb), 0.5); }
        }
        .meta-btn:active { transform: scale(0.97); }

        /* ===== TOAST ===== */
        .save-toast {
            position: fixed;
            bottom: 36px;
            left: 50%;
            transform: translate(-50%, 16px);
            background: rgba(20,20,22,0.94);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(var(--acc-rgb), 0.4);
            color: #fff;
            border-radius: 999px;
            padding: 0.6rem 1.2rem;
            font-family: inherit;
            font-size: 0.78rem;
            font-weight: 500;
            box-shadow: 0 12px 40px rgba(0,0,0,0.4);
            opacity: 0;
            pointer-events: none;
            z-index: 100;
            transition: opacity 300ms var(--ease), transform 400ms var(--ease);
        }
        .save-toast.show { opacity: 1; transform: translate(-50%, 0); }

        @media (max-width: 700px) {
            .app { padding: 0.7rem; gap: 0.9rem; }
            .video-wrapper { width: 100%; border-radius: 18px; }
            .header { padding: 0.7rem 0.8rem; }
            .header-brand .word { font-family: "Orbitron", sans-serif; font-size: 0.6rem; }
            .header-status { display: none; }
            .controls-wrapper { padding: 0.8rem 0.8rem 0.7rem 0.8rem; }
            .controls-row button { font-size: 0.6rem; min-height: 30px; }
            .controls-row .play-btn { width: 42px; height: 42px; min-width: 42px; min-height: 42px; }
            .controls-row .play-btn svg { width: 18px; height: 18px; }
            .controls-row .vol-btn { width: 32px; height: 32px; min-height: 32px; }
            .controls-row .icon-btn { width: 32px; height: 32px; }
            .vol-slider { width: 56px; }
            .controls-row .time-display { font-family: "JetBrains Mono", monospace; font-size: 0.56rem; min-width: 66px; }
            .center-play { width: 56px; height: 56px; }
            .center-play svg { width: 22px; height: 22px; }
            .meta { width: 100%; flex-direction: column; align-items: flex-start; gap: 0.6rem; }
            .meta-title { font-family: "Orbitron", sans-serif; max-width: 100%; }
            .meta-actions { width: 100%; }
            .meta-btn { font-family: "Orbitron", sans-serif; flex: 1; text-align: center; }
            .save-toast { bottom: 20px; }
        }
        @media (max-width: 450px) {
            .controls-row .time-display { font-family: "JetBrains Mono", monospace; font-size: 0.52rem; min-width: 60px; }
            .vol-slider { width: 40px; }
            .quality-badge { font-family: "Orbitron", sans-serif; display: none; }
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
                <span class="word">FAP<span class="dot">HOUSE</span></span>
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
            <div class="meta-title" id="videoTitle"><span class="a">FAP</span>HOUSE VIDEO</div>
            <div class="meta-caption">Saved to your library automatically on playback</div>
        </div>
        <div class="meta-actions">
            <a href="/" class="meta-btn">← Back</a>
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
