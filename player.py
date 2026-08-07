from flask import Flask, jsonify, request, render_template_string
import requests
import re
import json
from functools import lru_cache
from datetime import datetime
import os

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
        # If session exists and we're logged in, test it
        if self.logged_in and self.session:
            try:
                # Quick test to verify session is still valid
                test_resp = self.session.get(f"{BASE_URL}/", timeout=5, headers={
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36'
                })
                if test_resp.status_code == 200:
                    return self.session
            except:
                pass
        
        # If we get here, login fresh
        self.login()
        return self.session
    
    def login(self):
        """Login and store session"""
        print(f"🔐 Logging in...")
        self.session = requests.Session()
        
        # Set headers to look like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
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
            
            # Check if login was successful
            if login_res.status_code == 200:
                # Check if we got session cookies
                if "_identity" in self.session.cookies:
                    self.logged_in = True
                    self.last_login = datetime.now()
                    print(f"✅ Login successful!")
                    return True
                else:
                    # Sometimes the identity is in the response body
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
        """Get M3U8 URL with caching"""
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
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': BASE_URL,
                    'Connection': 'keep-alive'
                }
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch video: {response.status_code}")
                return None
            
            # Debug: Save response to check
            print(f"📄 Response length: {len(response.text)}")
            
            # Try multiple patterns to find M3U8 URL
            patterns = [
                r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+\.m3u8\?[^\s"\']*',
                r'https?://[^\s"\']+/hls/[^\s"\']+\.m3u8[^\s"\']*',
                r'https?://[^\s"\']+/stream/[^\s"\']+\.m3u8[^\s"\']*'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text)
                if matches:
                    print(f"✅ Found M3U8 URL: {matches[0][:100]}...")
                    return matches[0]
            
            # Also try to find it in JavaScript objects
            js_pattern = r'(?:src|url|source|file)\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
            js_matches = re.findall(js_pattern, response.text, re.IGNORECASE)
            if js_matches:
                print(f"✅ Found M3U8 in JS: {js_matches[0][:100]}...")
                return js_matches[0]
            
            print("❌ No M3U8 URL found in page")
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
        .debug { color: #666; font-size: 12px; margin-top: 10px; padding: 10px; background: #111; border-radius: 4px; }
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
                <div class="debug">🔍 Debug: {{ debug_info }}</div>
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
    
    # Clean the URL if needed
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
            return render_template_string(
                PLAYER_TEMPLATE,
                error="Could not find M3U8 URL for this video. Make sure the video is available and the URL is correct.",
                m3u8_url=None,
                video_url=video_url,
                debug_info="Login status: " + ("✅ Logged in" if client.logged_in else "❌ Not logged in")
            )
    except Exception as e:
        return render_template_string(
            PLAYER_TEMPLATE,
            error=f"Error: {str(e)}",
            m3u8_url=None,
            video_url=video_url,
            debug_info=f"Exception: {type(e).__name__}"
        )

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
    app.run(host='0.0.0.0', port=5000, debug=False)
