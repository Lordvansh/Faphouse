from flask import Flask, jsonify, request, render_template_string
import requests
import re
import json
from functools import lru_cache
from datetime import datetime
import os
import base64
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

# ============ CONFIG ============
BASE_URL = "https://faphouse2.com"
EMAIL = "rockstarga69@gmail.com"
PASSWORD = "Jaiisbeast@1"

# ============ LOGIN WITH SESSION REUSE ============
class FaphouseClient:
    def __init__(self):
        self.session = None
        self.last_login = None
        self.logged_in = False
        
    def ensure_session(self):
        """Ensure we have a valid session - properly handles Vercel's stateless nature"""
        if self.logged_in and self.session:
            try:
                test_resp = self.session.get(f"{BASE_URL}/", timeout=5, headers={
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
                })
                if test_resp.status_code == 200:
                    return self.session
            except:
                pass
        
        self.login()
        return self.session
    
    def login(self):
        """Login and store session"""
        print(f"🔐 Logging in...")
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': BASE_URL,
            'Referer': f"{BASE_URL}/",
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        
        try:
            # First, get the main page to get cookies
            init_res = self.session.get(BASE_URL, timeout=10)
            
            # Login payload
            payload = {
                "login": EMAIL,
                "password": PASSWORD,
                "rememberMe": "1",
                "recaptcha": "",
                "trackingParamsBag": "eyJwcm9tb19pZCI6IiIsInZpZGVvX2lkIjpudWxsLCJzdHVkaW9faWQiOm51bGwsInByb2R1Y2VyX2lkIjpudWxsLCJvcmllbnRhdGlvbiI6InN0cmFpZ2h0IiwibWxfcGFnZSI6Im1haW5fcGFnZSIsIm1sX3BhZ2VfdmFsdWVfaWQiOm51bGwsIm1sX3BhZ2VfdmFsdWUiOm51bGwsIm1sX3BhZ2VfbnVtYmVyIjpudWxsLCJtbF9yZWZfcGFnZV92YWx1ZV9pZCI6bnVsbCwibWxfcmVmX3BhZ2VfdmFsdWUiOiIiLCJtbF9yZWZfcGFnZV9udW1iZXIiOm51bGwsIm1sX3JlZl9wYWdlIjoiZGlyZWN0In0="
            }
            
            login_res = self.session.post(
                f"{BASE_URL}/api/auth/signin",
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            )
            
            if login_res.status_code == 200:
                if "_identity" in self.session.cookies:
                    self.logged_in = True
                    self.last_login = datetime.now()
                    print(f"✅ Login successful!")
                    return True
                else:
                    try:
                        resp_data = login_res.json()
                        if resp_data.get('success') or resp_data.get('status') == 'success':
                            self.logged_in = True
                            self.last_login = datetime.now()
                            print(f"✅ Login successful (from response)!")
                            return True
                    except:
                        pass
                    
                    print(f"❌ Login failed: No session cookie")
                    return False
            else:
                print(f"❌ Login failed: {login_res.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            return False
    
    @lru_cache(maxsize=50)
    def get_m3u8_url(self, video_url):
        """Get M3U8 URL with caching and multiple extraction methods"""
        session = self.ensure_session()
        if not session:
            print("❌ No valid session available")
            return None
            
        try:
            print(f"📡 Fetching: {video_url}")
            
            # Fetch video page with proper headers
            response = session.get(
                video_url, 
                timeout=15,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': video_url,
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch video: {response.status_code}")
                return None
            
            html_content = response.text
            print(f"📄 Response length: {len(html_content)}")
            
            # Method 1: Direct M3U8 URL pattern
            patterns = [
                r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+\.m3u8\?[^\s"\']*',
                r'https?://[^\s"\']+/hls/[^\s"\']+\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+/stream/[^\s"\']+\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+/playlist\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+/index\.m3u8[^\s"\']*'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    print(f"✅ Found M3U8 URL (Method 1): {matches[0][:100]}...")
                    return matches[0]
            
            # Method 2: JavaScript variables containing M3U8
            js_patterns = [
                r'(?:src|url|source|file|videoUrl|hlsUrl|m3u8Url)\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
                r'(?:src|url|source|file|videoUrl|hlsUrl|m3u8Url)\s*[:=]\s*["\']([^"\']+\.m3u8\?[^"\']*)["\']',
                r'(?:src|url|source|file|videoUrl|hlsUrl|m3u8Url)\s*[:=]\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
                r'["\'](https?://[^\s"\']+\.m3u8[^\s"\']*)["\']'
            ]
            
            for pattern in js_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    print(f"✅ Found M3U8 URL (Method 2): {matches[0][:100]}...")
                    return matches[0]
            
            # Method 3: Look for data attributes
            data_patterns = [
                r'data-(?:src|url|source|file|video)[\s]*=[\s]*["\']([^"\']+\.m3u8[^"\']*)["\']',
                r'data-(?:src|url|source|file|video)[\s]*=[\s]*["\']([^"\']+\.m3u8\?[^"\']*)["\']'
            ]
            
            for pattern in data_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    print(f"✅ Found M3U8 URL (Method 3): {matches[0][:100]}...")
                    return matches[0]
            
            # Method 4: Search in JSON objects within the page
            json_pattern = r'\{[^{}]*"(?:src|url|source|file|videoUrl|hlsUrl|m3u8Url)"\s*:\s*"([^"]+\.m3u8[^"]*)"[^{}]*\}'
            json_matches = re.findall(json_pattern, html_content, re.IGNORECASE)
            if json_matches:
                print(f"✅ Found M3U8 URL (Method 4): {json_matches[0][:100]}...")
                return json_matches[0]
            
            # Method 5: Try to find in script tags with video data
            script_pattern = r'<script[^>]*>.*?(?:video|player|hls|stream|source).*?\.m3u8.*?</script>'
            script_tags = re.findall(script_pattern, html_content, re.IGNORECASE | re.DOTALL)
            for script in script_tags:
                matches = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', script, re.IGNORECASE)
                if matches:
                    print(f"✅ Found M3U8 URL (Method 5): {matches[0][:100]}...")
                    return matches[0]
            
            # Method 6: Try to get video ID and construct URL
            video_id_match = re.search(r'/videos/[^/]+-([A-Za-z0-9]+)', video_url)
            if video_id_match:
                video_id = video_id_match.group(1)
                print(f"📝 Extracted video ID: {video_id}")
                
                # Try to get M3U8 from API
                api_urls = [
                    f"{BASE_URL}/api/video/{video_id}",
                    f"{BASE_URL}/api/video/info/{video_id}",
                    f"{BASE_URL}/api/stream/{video_id}",
                    f"{BASE_URL}/api/hls/{video_id}"
                ]
                
                for api_url in api_urls:
                    try:
                        api_resp = session.get(api_url, timeout=5, headers={
                            'Accept': 'application/json',
                            'X-Requested-With': 'XMLHttpRequest'
                        })
                        if api_resp.status_code == 200:
                            try:
                                data = api_resp.json()
                                # Look for M3U8 in various places in JSON
                                json_str = json.dumps(data)
                                m3u8_in_json = re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', json_str, re.IGNORECASE)
                                if m3u8_in_json:
                                    print(f"✅ Found M3U8 URL (Method 6 - API): {m3u8_in_json[0][:100]}...")
                                    return m3u8_in_json[0]
                            except:
                                pass
                    except:
                        pass
            
            # Method 7: Check if there's a redirect to M3U8
            if response.history:
                for resp in response.history:
                    if '.m3u8' in resp.url:
                        print(f"✅ Found M3U8 URL (Method 7 - Redirect): {resp.url[:100]}...")
                        return resp.url
            
            # If we got here, no M3U8 found - save a sample for debugging
            print("❌ No M3U8 URL found in page")
            print(f"📝 Page sample (first 500 chars): {html_content[:500]}")
            
            # Try to find any video URL pattern
            video_patterns = [
                r'https?://[^\s"\']+\.(?:mp4|m3u8|ts)[^\s"\']*',
                r'https?://[^\s"\']+/(?:video|stream|playlist)[^\s"\']*',
            ]
            for pattern in video_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    print(f"📎 Found possible video URL: {matches[0][:100]}...")
            
            return None
            
        except requests.exceptions.Timeout:
            print("❌ Request timed out")
            return None
        except Exception as e:
            print(f"❌ Error fetching M3U8: {str(e)}")
            return None

# Initialize client
client = FaphouseClient()

# ============ FLASK APP ============

# HTML Player Template
PLAYER_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 Faphouse Player</title>
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
        #player { width: 100%; height: 100%; }
        .info {
            margin-top: 15px;
            padding: 15px;
            background: #222;
            border-radius: 8px;
            font-size: 13px;
            word-break: break-all;
        }
        .info a { color: #4CAF50; text-decoration: none; }
        .info a:hover { text-decoration: underline; }
        .error {
            color: #ff4444;
            padding: 40px;
            text-align: center;
            font-size: 18px;
        }
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
        .video-title { color: #888; font-size: 14px; }
        .url-input {
            margin: 20px 0;
            padding: 20px;
            background: #222;
            border-radius: 8px;
        }
        .url-input input {
            width: 70%;
            padding: 12px;
            background: #333;
            border: 1px solid #444;
            border-radius: 6px;
            color: #fff;
            font-size: 14px;
        }
        .url-input input:focus {
            outline: none;
            border-color: #4CAF50;
        }
        .url-input button {
            padding: 12px 30px;
            background: #4CAF50;
            border: none;
            border-radius: 6px;
            color: #fff;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
            transition: background 0.3s;
            margin-left: 10px;
        }
        .url-input button:hover { background: #45a049; }
        .url-input .hint { color: #888; font-size: 12px; margin-top: 8px; }
        .debug { color: #666; font-size: 12px; margin-top: 10px; padding: 10px; background: #111; border-radius: 4px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-bar">
            <h2>🎬 Faphouse <span class="badge">ULTRA</span></h2>
            <span class="status-dot"></span>
            <span class="video-title">Live Stream</span>
        </div>
        
        {% if error %}
            <div class="error">
                <div style="font-size: 48px; margin-bottom: 20px;">❌</div>
                {{ error }}
                {% if debug_info %}
                <div class="debug">🔍 Debug Info:\n{{ debug_info }}</div>
                {% endif %}
            </div>
            <div class="url-input">
                <form method="GET" action="/play">
                    <input type="text" name="url" placeholder="Enter Faphouse video URL..." value="{{ video_url or '' }}">
                    <button type="submit">▶ Play</button>
                    <div class="hint">💡 Example: https://faphouse2.com/videos/shared-bed-stepsister-fuck-C6Qi1u</div>
                </form>
            </div>
        {% else %}
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
            </div>
        {% endif %}
    </div>

    <script src="https://vjs.zencdn.net/8.0.0/video.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            {% if not error %}
                var player = videojs('player', {
                    html5: {
                        hls: {
                            enableLowInitialPlaylist: true,
                            smoothQualityChange: true,
                            overrideNative: true
                        }
                    },
                    controlBar: {
                        children: [
                            'playToggle', 'volumePanel', 'currentTimeDisplay',
                            'timeDivider', 'durationDisplay', 'progressControl',
                            'liveDisplay', 'qualitySelector', 'fullscreenToggle'
                        ]
                    }
                });
                
                player.ready(function() {
                    console.log('✅ Player ready');
                    this.play().catch(function(e) {
                        console.log('Auto-play prevented:', e);
                    });
                });
                
                player.on('error', function() {
                    console.error('Player error:', this.error());
                });
            {% endif %}
        });
    </script>
</body>
</html>
"""

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
                .url-input { margin: 20px 0; }
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
                .url-input button:hover { background: #45a049; }
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
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎬 Faphouse Player</h1>
                <p class="subtitle">Enter any Faphouse video URL to watch</p>
                
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
                    <div class="endpoint"><strong>GET</strong> /play?url=VIDEO_URL - Watch video in browser</div>
                    <div class="endpoint"><strong>GET</strong> /api/m3u8?url=VIDEO_URL - Get M3U8 URL (JSON)</div>
                    <div class="endpoint"><strong>GET</strong> /api/debug?url=VIDEO_URL - Debug page content</div>
                    <div class="endpoint"><strong>GET</strong> /api/status - Check API status</div>
                </div>
            </div>
        </body>
        </html>
    """)

@app.route('/play')
def play_video():
    video_url = request.args.get('url')
    
    if not video_url:
        return render_template_string("""
            <div style="padding: 40px; text-align: center; background: #0a0a0a; color: #fff; min-height: 100vh; font-family: Arial;">
                <div style="max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #ff4444;">❌ No URL provided</h2>
                    <p style="color: #888; margin: 20px 0;">Please go back and enter a valid Faphouse video URL.</p>
                    <a href="/" style="color: #4CAF50; text-decoration: none; display: inline-block; padding: 10px 30px; background: #222; border-radius: 6px;">← Go Home</a>
                </div>
            </div>
        """)
    
    video_url = video_url.strip()
    if not video_url.startswith('http'):
        video_url = f"https://{video_url}"
    
    try:
        print(f"🎯 Processing URL: {video_url}")
        m3u8_url = client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return render_template_string(
                PLAYER_TEMPLATE,
                error=None,
                m3u8_url=m3u8_url,
                video_url=video_url,
                debug_info=None
            )
        else:
            # Get debug info by fetching the page and showing what we found
            debug_info = "Could not extract M3U8 URL. Common reasons:\n"
            debug_info += "1. The video may require a different login method\n"
            debug_info += "2. The video URL might be incorrect\n"
            debug_info += "3. The site's structure may have changed\n"
            debug_info += "4. Try a different video URL\n\n"
            debug_info += f"Login status: {'✅ Logged in' if client.logged_in else '❌ Not logged in'}\n"
            
            return render_template_string(
                PLAYER_TEMPLATE,
                error="Could not find M3U8 URL for this video. Make sure the video is available and the URL is correct.",
                m3u8_url=None,
                video_url=video_url,
                debug_info=debug_info
            )
    except Exception as e:
        return render_template_string(
            PLAYER_TEMPLATE,
            error=f"Error: {str(e)}",
            m3u8_url=None,
            video_url=video_url,
            debug_info=f"Exception: {type(e).__name__}"
        )

@app.route('/api/debug')
def debug_video():
    """Debug endpoint to show page content"""
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    session = client.ensure_session()
    if not session:
        return jsonify({"error": "No session"}), 500
    
    try:
        response = session.get(video_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        })
        
        html = response.text
        
        # Find all potential video URLs
        patterns = [
            r'https?://[^\s"\']+\.m3u8[^\s"\']*',
            r'https?://[^\s"\']+\.mp4[^\s"\']*',
            r'https?://[^\s"\']+/hls/[^\s"\']+',
            r'https?://[^\s"\']+/stream/[^\s"\']+',
        ]
        
        found_urls = []
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                found_urls.extend(matches[:5])  # First 5 matches
        
        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "content_length": len(html),
            "found_urls": found_urls,
            "page_sample": html[:1000],
            "logged_in": client.logged_in
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/m3u8')
def get_m3u8():
    video_url = request.args.get('url')
    
    if not video_url:
        return jsonify({
            "error": "Missing 'url' parameter",
            "usage": "/api/m3u8?url=VIDEO_URL"
        }), 400
    
    try:
        m3u8_url = client.get_m3u8_url(video_url)
        
        if m3u8_url:
            return jsonify({
                "success": True,
                "m3u8_url": m3u8_url,
                "video_url": video_url,
                "cached": client.get_m3u8_url.cache_info().hits > 0,
                "logged_in": client.logged_in
            })
        else:
            return jsonify({
                "success": False,
                "error": "No M3U8 URL found",
                "logged_in": client.logged_in
            }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/status')
def status():
    return jsonify({
        "status": "online",
        "logged_in": client.logged_in,
        "cache_info": client.get_m3u8_url.cache_info()._asdict()
    })

# ============ FOR VERCEL ============
if __name__ == "__main__":
    print("🎬 Faphouse Player running locally")
    client.login()
    app.run(host='0.0.0.0', port=5000, debug=True)
