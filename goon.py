from flask import Flask, jsonify, request, render_template_string
import requests
import re
import json
import os
from functools import lru_cache
from datetime import datetime, timedelta
import time
import logging

app = Flask(__name__)

# ============ LOGGING CONFIG ============
# This will output to Vercel logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ CONFIG ============
BASE_URL = "https://faphouse2.com"
EMAIL = os.environ.get('EMAIL', 'rockstarga69@gmail.com')
PASSWORD = os.environ.get('PASSWORD', 'Jaiisbeast@1')

# Cache settings
CACHE_DURATION = 300  # 5 minutes cache

# ============ SESSION MANAGER (Optimized for Vercel) ============
class FaphouseClient:
    def __init__(self):
        self.session = None
        self.logged_in = False
        self.session_created = False
        self.last_login_attempt = None
        
    def ensure_session(self):
        """Ensure we have a valid session"""
        # If session doesn't exist or expired, create/login
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
        
        # Set proper headers for login
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
            # First get the page to establish session
            logger.info("  📡 Getting initial page...")
            init_res = self.session.get(BASE_URL, timeout=10)
            logger.info(f"  📡 Initial page status: {init_res.status_code}")
            
            # Login payload
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
                    logger.info(f"  📡 Login response data: {str(data)[:200]}...")
                    if data.get('success') or data.get('data'):
                        self.logged_in = True
                        logger.info("✅ Login successful!")
                        self.last_login_attempt = datetime.now()
                        return True
                except Exception as e:
                    logger.warning(f"  ⚠️ Could not parse login response: {str(e)}")
                
                # Check if we have session cookies
                if len(self.session.cookies) > 0:
                    self.logged_in = True
                    logger.info(f"✅ Login successful (session established with {len(self.session.cookies)} cookies)!")
                    self.last_login_attempt = datetime.now()
                    return True
            
            logger.warning(f"❌ Login failed (HTTP {login_res.status_code})")
            if login_res.text:
                try:
                    error_data = login_res.json()
                    logger.warning(f"  Error response: {str(error_data)[:200]}")
                except:
                    logger.warning(f"  Response text: {login_res.text[:200]}")
            
            self.logged_in = False
            return False
            
        except requests.exceptions.Timeout:
            logger.error("❌ Login timeout - server not responding")
            self.logged_in = False
            return False
        except requests.exceptions.ConnectionError:
            logger.error("❌ Connection error - cannot reach server")
            self.logged_in = False
            return False
        except Exception as e:
            logger.error(f"❌ Login error: {str(e)}")
            self.logged_in = False
            return False
    
    @lru_cache(maxsize=100)
    def get_m3u8_url(self, video_url):
        """Get M3U8 URL with caching and multiple fallback attempts"""
        logger.info(f"🔍 Processing video URL: {video_url[:80]}...")
        
        # Clean URL
        if '#' in video_url:
            video_url = video_url.split('#')[0]
        
        # List of user agents to try
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1'
        ]
        
        # --- ATTEMPT 1: With Session/Login ---
        session = self.ensure_session()
        if session:
            try:
                logger.info("📡 Attempt 1: Using authenticated session...")
                response = session.get(
                    video_url, 
                    timeout=15, 
                    headers={
                        'User-Agent': user_agents[0],
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': BASE_URL,
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )
                logger.info(f"📡 Session GET Status: {response.status_code}")
                
                if response.status_code == 200:
                    m3u8 = self._extract_m3u8(response.text)
                    if m3u8:
                        logger.info("✅ Found M3U8 URL with session!")
                        return m3u8
                    else:
                        logger.warning("⚠️ No M3U8 found in session response.")
                elif response.status_code == 451:
                    logger.warning("❌ 451: Content blocked in your region")
                else:
                    logger.warning(f"⚠️ Session GET failed with status: {response.status_code}")
            except requests.exceptions.Timeout:
                logger.error("❌ Session GET timeout")
            except Exception as e:
                logger.error(f"❌ Session GET Exception: {str(e)}")

        # --- ATTEMPT 2: Guest/Fallback with different user agents ---
        logger.info("🔄 Attempt 2: Trying fallback fetch without login...")
        for i, ua in enumerate(user_agents[1:], start=1):
            try:
                logger.info(f"  🔄 Attempt 2.{i} with User-Agent: {ua[:30]}...")
                guest_session = requests.Session()
                guest_session.headers.update({
                    'User-Agent': ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': BASE_URL,
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                fallback_response = guest_session.get(video_url, timeout=15)
                logger.info(f"📡 Fallback {i} Status: {fallback_response.status_code}")
                
                if fallback_response.status_code == 200:
                    m3u8 = self._extract_m3u8(fallback_response.text)
                    if m3u8:
                        logger.info(f"✅ Found M3U8 URL with fallback {i}!")
                        return m3u8
                elif fallback_response.status_code == 451:
                    logger.warning(f"❌ 451: Content blocked for UA {i}")
            except Exception as e:
                logger.error(f"❌ Fallback {i} Exception: {str(e)}")

        # --- ATTEMPT 3: Try with a different domain if available ---
        try:
            alt_base_url = "https://faphouse.com"  # Alternative domain
            alt_video_url = video_url.replace(BASE_URL, alt_base_url)
            logger.info(f"🔄 Attempt 3: Trying alternative domain: {alt_video_url[:80]}...")
            
            alt_session = requests.Session()
            alt_session.headers.update({
                'User-Agent': user_agents[0],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': alt_base_url,
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            alt_response = alt_session.get(alt_video_url, timeout=15)
            logger.info(f"📡 Alternative domain status: {alt_response.status_code}")
            
            if alt_response.status_code == 200:
                m3u8 = self._extract_m3u8(alt_response.text)
                if m3u8:
                    logger.info("✅ Found M3U8 URL with alternative domain!")
                    return m3u8
        except Exception as e:
            logger.error(f"❌ Alternative domain Exception: {str(e)}")

        logger.error("❌ Failed to find M3U8 URL with all attempts.")
        return None

    def _extract_m3u8(self, html_content):
        """Helper to extract M3U8 URL from HTML content"""
        if not html_content:
            return None
            
        # More comprehensive patterns
        patterns = [
            r'https?://[^\s"\']+\.m3u8[^\s"\']*',
            r'https?://[^\s"\']+\.m3u8(?:\?[^\s"\']*)?',
            r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*=\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'file\s*:\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
            r'https?://[^\s<>]+\.m3u8',
            r'//[^\s"\']+\.m3u8[^\s"\']*',
            r'//[^\s"\']+\.m3u8(?:\?[^\s"\']*)?',
            r'https?://[^\s"\']+/playlist\.m3u8[^\s"\']*',
            r'https?://[^\s"\']+/hls/[^\s"\']+\.m3u8',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                m3u8_url = matches[0]
                # Clean up
                if isinstance(m3u8_url, tuple):
                    m3u8_url = m3u8_url[0]
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
                    logger.info(f"✅ Found M3U8: {m3u8_url[:100]}...")
                    return m3u8_url
        
        # If no direct URL found, try to find it in JavaScript
        js_patterns = [
            r'player\.setup\s*\(\s*{\s*file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'video\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'url\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                m3u8_url = matches[0]
                if isinstance(m3u8_url, tuple):
                    m3u8_url = m3u8_url[0]
                if m3u8_url.startswith('//'):
                    m3u8_url = 'https:' + m3u8_url
                logger.info(f"✅ Found M3U8 in JS: {m3u8_url[:100]}...")
                return m3u8_url
        
        return None

# Initialize client
client = FaphouseClient()

# ============ FLASK APP ============

@app.route('/')
def index():
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>🎬 Faphouse Player</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    background: #0a0a0a;
                    color: #fff;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }
                .container {
                    max-width: 600px;
                    width: 100%;
                    background: #1a1a1a;
                    border-radius: 12px;
                    padding: 40px;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.8);
                    text-align: center;
                }
                h1 { font-size: 32px; margin-bottom: 10px; }
                .subtitle { color: #888; margin-bottom: 30px; }
                .url-input {
                    margin: 20px 0;
                }
                .url-input input {
                    width: 100%;
                    padding: 15px;
                    background: #333;
                    border: 1px solid #444;
                    border-radius: 8px;
                    color: #fff;
                    font-size: 16px;
                }
                .url-input input:focus {
                    outline: none;
                    border-color: #4CAF50;
                }
                .url-input button {
                    width: 100%;
                    padding: 15px;
                    margin-top: 15px;
                    background: #4CAF50;
                    border: none;
                    border-radius: 8px;
                    color: #fff;
                    font-weight: bold;
                    font-size: 18px;
                    cursor: pointer;
                    transition: background 0.3s;
                }
                .url-input button:hover {
                    background: #45a049;
                }
                .hint {
                    color: #666;
                    font-size: 13px;
                    margin-top: 15px;
                }
                .hint code {
                    background: #222;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    word-break: break-all;
                }
                .endpoints {
                    margin-top: 30px;
                    padding: 20px;
                    background: #222;
                    border-radius: 8px;
                    text-align: left;
                }
                .endpoints h3 {
                    color: #888;
                    font-size: 14px;
                    margin-bottom: 10px;
                }
                .endpoint {
                    padding: 8px 0;
                    border-bottom: 1px solid #333;
                    font-size: 13px;
                    color: #aaa;
                }
                .endpoint:last-child { border-bottom: none; }
                .endpoint strong { color: #4CAF50; }
                .debug-link {
                    margin-top: 15px;
                    padding: 10px;
                    background: #222;
                    border-radius: 6px;
                    font-size: 12px;
                    color: #666;
                }
                .debug-link a {
                    color: #4CAF50;
                    text-decoration: none;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 Faphouse Player</h1>
                <p class="subtitle">Enter any video URL to watch</p>
                
                <div class="url-input">
                    <form method="GET" action="/play">
                        <input type="text" name="url" placeholder="Paste video URL here..." required>
                        <button type="submit">▶ Watch Now</button>
                    </form>
                    <div class="hint">
                        💡 Example: <code>https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u</code>
                    </div>
                </div>
                
                <div class="endpoints">
                    <h3>📡 API Endpoints</h3>
                    <div class="endpoint"><strong>GET</strong> /play?url=VIDEO_URL - Watch video</div>
                    <div class="endpoint"><strong>GET</strong> /api/m3u8?url=VIDEO_URL - Get M3U8 URL</div>
                    <div class="endpoint"><strong>GET</strong> /api/status - Check status</div>
                    <div class="endpoint"><strong>GET</strong> /api/debug?url=VIDEO_URL - Debug URL</div>
                </div>
                
                <div class="debug-link">
                    🔍 <a href="/api/debug?url=https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u">Debug this example</a>
                </div>
            </div>
        </body>
        </html>
    """)

@app.route('/play')
def play_video():
    video_url = request.args.get('url')
    
    if not video_url:
        return "❌ No URL provided", 400
    
    # Clean URL
    if '#' in video_url:
        video_url = video_url.split('#')[0]
    
    try:
        logger.info(f"🎬 Play request for: {video_url}")
        m3u8_url = client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>🎬 Video Player</title>
                    <link href="https://vjs.zencdn.net/8.0.0/video-js.css" rel="stylesheet" />
                    <style>
                        * { margin: 0; padding: 0; box-sizing: border-box; }
                        body {
                            background: #0a0a0a;
                            color: #fff;
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            padding: 20px;
                        }
                        .container {
                            max-width: 1200px;
                            width: 100%;
                            background: #1a1a1a;
                            border-radius: 12px;
                            padding: 20px;
                            box-shadow: 0 8px 32px rgba(0,0,0,0.8);
                        }
                        .video-wrapper {
                            width: 100%;
                            background: #000;
                            border-radius: 8px;
                            overflow: hidden;
                            position: relative;
                            aspect-ratio: 16/9;
                        }
                        #player {
                            width: 100%;
                            height: 100%;
                        }
                        .info {
                            margin-top: 15px;
                            padding: 15px;
                            background: #222;
                            border-radius: 8px;
                            font-size: 13px;
                            word-break: break-all;
                        }
                        .info a { color: #4CAF50; text-decoration: none; }
                        .badge {
                            display: inline-block;
                            background: #4CAF50;
                            color: #fff;
                            padding: 2px 12px;
                            border-radius: 20px;
                            font-size: 11px;
                            font-weight: bold;
                            margin-left: 10px;
                        }
                        .status-bar {
                            display: flex;
                            align-items: center;
                            gap: 20px;
                            margin-bottom: 15px;
                            flex-wrap: wrap;
                        }
                        .status-bar h2 {
                            display: flex;
                            align-items: center;
                            font-size: 20px;
                        }
                        .status-dot {
                            display: inline-block;
                            width: 10px;
                            height: 10px;
                            border-radius: 50%;
                            background: #4CAF50;
                            animation: pulse 1.5s infinite;
                        }
                        @keyframes pulse {
                            0% { opacity: 1; }
                            50% { opacity: 0.3; }
                            100% { opacity: 1; }
                        }
                        .back-link {
                            display: inline-block;
                            margin-top: 10px;
                            color: #888;
                            text-decoration: none;
                        }
                        .back-link:hover { color: #fff; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="status-bar">
                            <h2>
                                🎬 Faphouse
                                <span class="badge">ULTRA</span>
                            </h2>
                            <span class="status-dot"></span>
                            <span class="video-title">Playing</span>
                        </div>
                        
                        <div class="video-wrapper">
                            <video id="player" class="video-js vjs-default-skin" controls autoplay preload="auto">
                                <source src="{{ m3u8_url }}" type="application/x-mpegURL">
                            </video>
                        </div>
                        
                        <div class="info">
                            <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                                <div>
                                    <strong>📹 Video:</strong> 
                                    <a href="{{ video_url }}" target="_blank">{{ video_url[:60] }}...</a>
                                </div>
                                <div>
                                    <strong>📊 Status:</strong> 
                                    <span style="color: #4CAF50;">● Playing</span>
                                </div>
                            </div>
                            <div style="margin-top: 10px; font-size: 11px; color: #666;">
                                M3U8 URL: <span style="word-break: break-all;">{{ m3u8_url[:80] }}...</span>
                            </div>
                        </div>
                        
                        <a href="/" class="back-link">← Back to Home</a>
                    </div>
                    
                    <script src="https://vjs.zencdn.net/8.0.0/video.min.js"></script>
                    <script>
                        document.addEventListener('DOMContentLoaded', function() {
                            var player = videojs('player', {
                                html5: {
                                    hls: {
                                        enableLowInitialPlaylist: true,
                                        smoothQualityChange: true,
                                        overrideNative: true
                                    }
                                }
                            });
                            
                            player.ready(function() {
                                console.log('✅ Player ready');
                                this.play().catch(function(e) {
                                    console.log('Auto-play prevented:', e);
                                });
                            });
                        });
                    </script>
                </body>
                </html>
            """, m3u8_url=m3u8_url, video_url=video_url)
        else:
            return render_template_string("""
                <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                    <div style="max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #ff4444;">❌ Could not find M3U8 URL</h2>
                        <p style="color: #888; margin: 20px 0;">The video might be unavailable or blocked in your region.</p>
                        <p style="color: #666; font-size: 13px; margin: 10px 0;">Try using the debug endpoint to see what's happening:</p>
                        <p style="background: #222; padding: 10px; border-radius: 6px; font-size: 12px; word-break: break-all;">
                            <a href="/api/debug?url={{ video_url }}" style="color: #4CAF50; text-decoration: none;">
                                /api/debug?url={{ video_url }}
                            </a>
                        </p>
                        <div style="margin-top: 20px;">
                            <a href="/" style="color: #4CAF50; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">← Go Home</a>
                        </div>
                    </div>
                </div>
            """, video_url=video_url)
    except Exception as e:
        logger.error(f"❌ Play error: {str(e)}")
        return render_template_string("""
            <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                <div style="max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #ff4444;">❌ Error</h2>
                    <p style="color: #888; margin: 20px 0;">{{ error }}</p>
                    <a href="/" style="color: #4CAF50; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">← Go Home</a>
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

@app.route('/api/debug')
def debug_url():
    """Debug endpoint to see what's happening"""
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    debug_info = {
        "video_url": video_url,
        "base_url": BASE_URL,
        "logged_in": client.logged_in,
        "session_created": client.session_created,
    }
    
    try:
        if '#' in video_url:
            video_url = video_url.split('#')[0]
        
        # Try to fetch the page
        session = client.ensure_session()
        if session:
            response = session.get(video_url, timeout=15)
            debug_info["status_code"] = response.status_code
            debug_info["content_length"] = len(response.text)
            debug_info["content_preview"] = response.text[:500]
            
            # Try to extract M3U8
            m3u8 = client._extract_m3u8(response.text)
            debug_info["m3u8_found"] = bool(m3u8)
            debug_info["m3u8_url"] = m3u8
            
            # Check for common patterns in HTML
            html_patterns = {
                "video-js": "video-js" in response.text,
                "hls": "hls" in response.text.lower(),
                "m3u8": ".m3u8" in response.text,
                "player": "player" in response.text.lower(),
                "src": "src=" in response.text,
                "file": "file:" in response.text,
            }
            debug_info["html_patterns"] = html_patterns
        else:
            debug_info["error"] = "Could not create session"
            
    except Exception as e:
        debug_info["error"] = str(e)
    
    return jsonify(debug_info)

# ============ FOR VERCEL ============
# This is the handler that Vercel will call
def handler(request, context):
    return app(request.environ, context)

# ============ MAIN (for local testing) ============
if __name__ == "__main__":
    print(f"""
{'='*70}
🎬 Faphouse Player API (Vercel Optimized)
{'='*70}

✅ Features:
  • Multiple fallback attempts for M3U8 extraction
  • Different user agents to bypass blocks
  • Alternative domain support
  • Comprehensive logging for debugging
  • LRU caching for fast responses

📌 Endpoints:
  📺 /play?url=VIDEO_URL     - Watch video
  📡 /api/m3u8?url=VIDEO_URL - Get M3U8 URL
  📊 /api/status             - Check status
  🔍 /api/debug?url=VIDEO_URL - Debug a URL

🔐 Credentials:
  EMAIL: {EMAIL[:5]}... 
  PASSWORD: {'*' * 8}
{'='*70}
""")
    
    print("🚀 Starting server for local testing...")
    app.run(host='0.0.0.0', port=5000, debug=True)
