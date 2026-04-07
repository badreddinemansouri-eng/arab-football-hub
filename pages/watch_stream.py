import streamlit as st
import re
import json
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime, timedelta
import requests
import zoneinfo
from supabase import create_client
import streamlit.components.v1 as components

# ═══════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════
st.set_page_config(
    page_title="Badr TV - بث مباشر",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SUPABASE_URL      = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
tz_tunis = zoneinfo.ZoneInfo("Africa/Tunis")

for k, v in {
    "extraction_attempted": False,
    "extracted_url": None,
    "extraction_failed": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════
#  HIDE STREAMLIT'S OWN UI COMPLETELY
#  This must come first and uses st.markdown — it
#  ONLY hides elements, no visual CSS, so it always
#  works even when Streamlit strips complex <style>.
# ═══════════════════════════════════════════════
st.markdown("""
<style>
header[data-testid="stHeader"],
footer,
#MainMenu,
.stDeployButton,
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],
section[data-testid="stSidebar"] {
    display: none !important;
}
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}
.main { padding: 0 !important; background: #f0f5ff !important; }
.stApp { background: #f0f5ff !important; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
#  QUERY PARAMS
# ═══════════════════════════════════════════════
match_id = st.query_params.get("match_id", None)
if isinstance(match_id, list):
    match_id = match_id[0]

selected_url = st.query_params.get("stream_url", None)
if isinstance(selected_url, list):
    selected_url = selected_url[0]
if selected_url:
    selected_url = unquote(selected_url)

# ═══════════════════════════════════════════════
#  FETCH MATCH
# ═══════════════════════════════════════════════
match_data = None
if match_id:
    try:
        res = supabase.table("matches").select("*").eq("fixture_id", match_id).execute()
        if res.data:
            match_data = res.data[0]
    except Exception:
        pass

# ═══════════════════════════════════════════════
#  COLLECT STREAMS
# ═══════════════════════════════════════════════
all_streams = []
if match_data:
    raw = match_data.get("streams", [])
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except Exception: raw = []
    all_streams.extend(raw)
    try:
        admin_rows = supabase.table("admin_streams")\
            .select("*").eq("fixture_id", match_id).eq("is_active", True)\
            .execute().data or []
        for a in admin_rows:
            all_streams.append({
                "title":    a.get("stream_title","بث مباشر"),
                "url":      a["stream_url"],
                "source":   a.get("stream_source","admin"),
                "verified": True,
            })
    except Exception:
        pass

# ═══════════════════════════════════════════════
#  RECENT NEWS
# ═══════════════════════════════════════════════
@st.cache_data(ttl=3600)
def get_recent_news():
    try:
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        return supabase.table("news").select("*")\
            .gte("published_at", cutoff).order("published_at", desc=True)\
            .limit(4).execute().data or []
    except Exception:
        return []

recent_news = get_recent_news()

# ═══════════════════════════════════════════════
#  URL → EMBED BUILDER  (universal)
# ═══════════════════════════════════════════════
def _clean_yt(u):
    m = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', u)
    return f"https://www.youtube.com/embed/{m.group(1)}?autoplay=1&rel=0" if m else u

def _find_ld(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('embedUrl','contentUrl','url') and isinstance(v,str) and 'http' in v:
                return v
            r = _find_ld(v)
            if r: return r
    elif isinstance(obj, list):
        for i in obj:
            r = _find_ld(i)
            if r: return r
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def extract_embed(url):
    for proxy in [
        f"https://api.allorigins.win/raw?url={quote(url)}",
        f"https://thingproxy.freeboard.io/fetch/{url}",
    ]:
        try:
            r = requests.get(proxy, headers={'User-Agent':'Mozilla/5.0'}, timeout=9)
            if r.status_code == 200:
                t = r.text
                for pat in [
                    r'<meta[^>]+property="og:video[^"]*"[^>]+content="([^"]+)"',
                    r'<meta[^>]+content="([^"]+)"[^>]+property="og:video[^"]*"',
                    r'<meta[^>]+property="twitter:player"[^>]+content="([^"]+)"',
                ]:
                    m2 = re.search(pat, t)
                    if m2: return _clean_yt(m2.group(1))
                for j in re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', t, re.DOTALL):
                    try:
                        f = _find_ld(json.loads(j))
                        if f: return _clean_yt(f)
                    except: pass
                m2 = re.search(r'<iframe[^>]+src="(https?://[^"]+)"', t)
                if m2: return _clean_yt(m2.group(1))
                m2 = re.search(r'["\']([^"\']+\.m3u8[^"\']*)["\']', t)
                if m2: return m2.group(1)
        except: pass
    return None

def build_embed(url):
    p = urlparse(url); d = p.netloc.lower(); path = p.path.lower(); q = parse_qs(p.query)
    if any(x in d for x in ["youtube.com","youtu.be"]):
        vid = path.strip('/') if "youtu.be" in d else q.get("v",[None])[0]
        if vid: return {"url":f"https://www.youtube.com/embed/{vid}?autoplay=1&rel=0","type":"iframe","name":"YouTube"}
    if "facebook.com" in d and any(x in url for x in ["/videos/","/watch/","/reel/"]):
        return {"url":f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=1280&autoplay=1","type":"iframe","name":"Facebook"}
    if "instagram.com" in d:
        parts = path.split('/')
        if len(parts)>=3: return {"url":f"https://www.instagram.com/p/{parts[2]}/embed","type":"iframe","name":"Instagram"}
    if "twitter.com" in d or "x.com" in d:
        m = re.search(r'/status/(\d+)', path)
        if m: return {"url":f"https://twitframe.com/show?url={quote(url)}","type":"iframe","name":"Twitter"}
    if "tiktok.com" in d:
        m = re.search(r'/video/(\d+)', path)
        if m: return {"url":f"https://www.tiktok.com/embed/v2/{m.group(1)}","type":"iframe","name":"TikTok"}
    if "dailymotion.com" in d or "dai.ly" in d:
        m = re.search(r'/video/([^_?/]+)', url)
        if m: return {"url":f"https://www.dailymotion.com/embed/video/{m.group(1)}?autoplay=1","type":"iframe","name":"Dailymotion"}
    if "vimeo.com" in d:
        vid = path.strip('/').split('/')[0]
        if vid.isdigit(): return {"url":f"https://player.vimeo.com/video/{vid}?autoplay=1","type":"iframe","name":"Vimeo"}
    if "ok.ru" in d:
        m = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if m: return {"url":f"https://ok.ru/videoembed/{m.group(1)}","type":"iframe","name":"OK.ru"}
    if "vk.com" in d:
        m = re.search(r'video(-?\d+)_(\d+)', url)
        if m:
            oid,vid=m.groups()
            return {"url":f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1","type":"iframe","name":"VK"}
    if "streamable.com" in d:
        vid = path.strip('/')
        if vid: return {"url":f"https://streamable.com/e/{vid}","type":"iframe","name":"Streamable"}
    if "rutube.ru" in d:
        m = re.search(r'/video/([a-zA-Z0-9]+)', url)
        if m: return {"url":f"https://rutube.ru/play/embed/{m.group(1)}","type":"iframe","name":"Rutube"}
    if "twitch.tv" in d:
        ch = path.strip('/')
        if ch: return {"url":f"https://player.twitch.tv/?channel={ch}&parent=badr.streamlit.app&autoplay=true","type":"iframe","name":"Twitch"}
    if path.endswith('.m3u8') or 'm3u8' in url:
        return {"url":url,"type":"hls","name":"HLS Stream"}
    if path.endswith(('.mp4','.webm','.ogg')):
        return {"url":url,"type":"video","name":"Video"}
    # Universal fallback — try direct iframe for any streaming site
    return {"url":url,"type":"iframe","name":"بث مباشر"}

# ═══════════════════════════════════════════════
#  BUILD MATCH META
# ═══════════════════════════════════════════════
if not match_id or not match_data:
    # Error page — still rendered as HTML component
    error_html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
<style>
* { font-family:'Cairo',sans-serif; box-sizing:border-box; margin:0; padding:0; }
body { background:#f0f5ff; display:flex; align-items:center; justify-content:center; height:100vh; }
.err { text-align:center; padding:40px; }
.err-icon { font-size:4rem; margin-bottom:16px; }
.err-title { font-size:1.4rem; font-weight:900; color:#0d1829; margin-bottom:8px; }
.err-sub { color:#6a82a8; font-size:.9rem; margin-bottom:24px; }
.err-btn { background:linear-gradient(135deg,#1148b8,#1976d2); color:#fff; text-decoration:none;
  padding:12px 28px; border-radius:14px; font-weight:700; font-size:.9rem; }
</style>
</head>
<body>
<div class="err">
  <div class="err-icon">❌</div>
  <div class="err-title">المباراة غير موجودة</div>
  <div class="err-sub">تعذّر تحميل بيانات المباراة</div>
  <a href="/" class="err-btn">← العودة للرئيسية</a>
</div>
</body></html>"""
    components.html(error_html, height=400, scrolling=False)
    st.stop()

home_team = match_data['home_team']
away_team = match_data['away_team']
_fb = lambda n,c="1148b8": f"https://ui-avatars.com/api/?name={quote(n[:2])}&background={c}&color=fff&size=100&bold=true"
home_logo = match_data.get('home_logo') or _fb(home_team)
away_logo = match_data.get('away_logo') or _fb(away_team,"0a2d7a")
league    = match_data.get('league','')
status    = match_data.get('status','')
is_live   = status == "LIVE"

try:
    lt       = datetime.fromisoformat(match_data["match_time"].replace('Z','+00:00')).astimezone(tz_tunis)
    time_str = lt.strftime('%H:%M — %d/%m/%Y')
except Exception:
    time_str = "---"

hs  = match_data.get('home_score')
aws = match_data.get('away_score')
score_display = f"{hs} - {aws}" if hs is not None else "VS"
score_label   = "FT" if status=="FINISHED" else ("LIVE" if is_live else "VS")

# ═══════════════════════════════════════════════
#  BUILD PLAYER HTML
# ═══════════════════════════════════════════════
player_html = ""
if selected_url:
    embed = build_embed(selected_url)
    embed_url = embed["url"]
    etype     = embed["type"]

    # Try extraction for direct_iframe if not yet tried
    if etype == "iframe" and embed_url == selected_url and not st.session_state.extraction_attempted:
        st.session_state.extraction_attempted = True
        extracted = extract_embed(selected_url)
        if extracted and extracted != selected_url:
            st.session_state.extracted_url = extracted

    if st.session_state.extracted_url:
        extracted_e = build_embed(st.session_state.extracted_url)
        embed_url   = extracted_e["url"]
        etype       = extracted_e["type"]

    if etype == "hls":
        player_html = f"""
        <div class="player-shell">
          <div class="player-bar"></div>
          <div class="player-topbar">
            <div class="ptb-left">
              {"<span class='live-badge-sm'>● LIVE</span>" if is_live else ""}
              <span class="ptb-title">{home_team} vs {away_team}</span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span id="stream-status" style="font-size:.68rem;color:rgba(255,255,255,.6);font-weight:600;">جاري التحميل...</span>
              <a href="{selected_url}" target="_blank" class="ptb-ext"><i class="fa fa-external-link-alt"></i> خارجي</a>
            </div>
          </div>
          <div class="player-ratio">
            <div id="hlsp" style="width:100%;height:100%;background:#000;"></div>
          </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"></script>
        <script>
        (function(){{
          var SRC    = '{embed_url}';
          var status = document.getElementById('stream-status');
          var c      = document.getElementById('hlsp');
          var v      = document.createElement('video');
          var retries = 0;
          var MAX_RETRIES = 10;
          var hls;

          v.controls   = true;
          v.autoplay   = true;
          v.playsinline = true;
          v.muted      = false;
          v.style.cssText = 'width:100%;height:100%;background:#000;display:block;';
          c.appendChild(v);

          function setStatus(txt, color){{
            if(status){{ status.textContent = txt; status.style.color = color || 'rgba(255,255,255,.6)'; }}
          }}

          function initHls(){{
            if(hls){{ hls.destroy(); }}

            hls = new Hls({{
              // ── BUFFER SETTINGS ──────────────────────────────
              maxBufferLength:          90,   // keep 90s buffer
              maxMaxBufferLength:       180,  // allow up to 3min buffer
              maxBufferSize:            200*1024*1024, // 200MB buffer
              maxBufferHole:            1.5,  // tolerate 1.5s holes
              // ── LIVE STREAM SETTINGS ─────────────────────────
              liveSyncDurationCount:    3,    // stay 3 segments behind live edge
              liveMaxLatencyDurationCount: 10,
              liveBackBufferLength:     60,
              // ── NETWORK RETRY SETTINGS ───────────────────────
              manifestLoadingMaxRetry:  6,
              manifestLoadingRetryDelay:2000,
              manifestLoadingMaxRetryTimeout: 32000,
              levelLoadingMaxRetry:     6,
              levelLoadingRetryDelay:   2000,
              fragLoadingMaxRetry:      8,
              fragLoadingRetryDelay:    1500,
              // ── QUALITY SETTINGS ─────────────────────────────
              startLevel:              -1,   // auto quality selection
              abrEwmaDefaultEstimate:  500000,
              // ── STABILITY ────────────────────────────────────
              enableWorker:            true,
              lowLatencyMode:          false, // disable for stability
              backBufferLength:        60,
            }});

            hls.loadSource(SRC);
            hls.attachMedia(v);

            hls.on(Hls.Events.MANIFEST_PARSED, function(e, data){{
              setStatus('✅ جاهز للبث', '#4ade80');
              retries = 0;
              v.play().catch(function(){{
                // autoplay blocked — user needs to tap play
                setStatus('▶ اضغط للتشغيل', 'rgba(255,255,255,.8)');
              }});
            }});

            hls.on(Hls.Events.FRAG_BUFFERED, function(){{
              setStatus('🔴 بث مباشر', '#ef4444');
            }});

            // ── STALL DETECTION ──────────────────────────────
            var stallTimer = null;
            var lastTime   = 0;
            v.addEventListener('timeupdate', function(){{
              lastTime = v.currentTime;
            }});
            v.addEventListener('waiting', function(){{
              setStatus('⏳ جاري التحميل...', '#fbbf24');
              // if stalled for 8s, skip forward to live edge
              stallTimer = setTimeout(function(){{
                if(v.buffered.length > 0){{
                  var end = v.buffered.end(v.buffered.length - 1);
                  if(end - v.currentTime > 5){{
                    v.currentTime = end - 1;
                    setStatus('⏩ تخطي للحظي', '#60a5fa');
                  }}
                }}
              }}, 8000);
            }});
            v.addEventListener('playing', function(){{
              if(stallTimer) clearTimeout(stallTimer);
              setStatus('🔴 بث مباشر', '#ef4444');
            }});

            // ── LIVE EDGE SYNC: every 30s, drift back to live ──
            setInterval(function(){{
              if(!v.paused && hls && hls.liveSyncPosition){{
                var drift = hls.liveSyncPosition - v.currentTime;
                if(drift > 20){{   // if more than 20s behind live
                  v.currentTime = hls.liveSyncPosition;
                  setStatus('⏩ مزامنة مع البث', '#60a5fa');
                }}
              }}
            }}, 30000);

            // ── ERROR HANDLER & AUTO-RECONNECT ───────────────
            hls.on(Hls.Events.ERROR, function(event, data){{
              if(!data.fatal) return; // non-fatal: hls.js handles internally

              if(data.type === Hls.ErrorTypes.NETWORK_ERROR){{
                retries++;
                if(retries <= MAX_RETRIES){{
                  var delay = Math.min(2000 * retries, 16000);
                  setStatus('⚠️ إعادة الاتصال ' + retries + '/' + MAX_RETRIES + '...', '#fbbf24');
                  setTimeout(function(){{ hls.startLoad(); }}, delay);
                }} else {{
                  setStatus('❌ فشل الاتصال — يعاد المحاولة...', '#f87171');
                  // Full restart after 20s
                  setTimeout(function(){{ retries=0; initHls(); }}, 20000);
                }}
              }} else if(data.type === Hls.ErrorTypes.MEDIA_ERROR){{
                setStatus('🔧 إصلاح الوسائط...', '#fbbf24');
                hls.recoverMediaError();
              }} else {{
                // Fatal: destroy and restart
                setStatus('🔄 إعادة تشغيل البث...', '#fbbf24');
                setTimeout(function(){{ retries=0; initHls(); }}, 5000);
              }}
            }});
          }}

          if(Hls.isSupported()){{
            initHls();
          }} else if(v.canPlayType('application/vnd.apple.mpegurl')){{
            // Native HLS (iOS Safari / macOS Safari)
            v.src = SRC;
            v.addEventListener('loadedmetadata', function(){{ v.play(); }});
            setStatus('📱 HLS نيتف', '#4ade80');
          }} else {{
            setStatus('❌ المتصفح لا يدعم HLS', '#f87171');
          }}

          // ── PAGE VISIBILITY: pause/resume on tab switch ──
          document.addEventListener('visibilitychange', function(){{
            if(document.hidden){{
              // tab hidden — don't destroy, just note
            }} else {{
              // came back — sync to live edge
              if(hls && hls.liveSyncPosition && !v.paused){{
                v.currentTime = hls.liveSyncPosition;
              }}
            }}
          }});
        }})();
        </script>"""
    elif etype == "video":
        player_html = f"""
        <div class="player-shell">
          <div class="player-bar"></div>
          <div class="player-topbar">
            <div class="ptb-left">
              {"<span class='live-badge-sm'>● LIVE</span>" if is_live else ""}
              <span class="ptb-title">{home_team} vs {away_team}</span>
            </div>
            <a href="{selected_url}" target="_blank" class="ptb-ext"><i class="fa fa-external-link-alt"></i> خارجي</a>
          </div>
          <div class="player-ratio">
            <video controls autoplay playsinline style="width:100%;height:100%;background:#000;">
              <source src="{embed_url}" type="video/mp4">
              <source src="{embed_url}" type="video/webm">
            </video>
          </div>
        </div>"""
    else:
        player_html = f"""
        <div class="player-shell">
          <div class="player-bar"></div>
          <div class="player-topbar">
            <div class="ptb-left">
              {"<span class='live-badge-sm'>● LIVE</span>" if is_live else ""}
              <span class="ptb-title">{home_team} vs {away_team}</span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span id="ifr-status" style="font-size:.68rem;color:rgba(255,255,255,.6);font-weight:600;">جاري التحميل...</span>
              <a href="{selected_url}" target="_blank" class="ptb-ext"><i class="fa fa-external-link-alt"></i> خارجي</a>
            </div>
          </div>
          <div class="player-ratio" id="player-wrap">
            <iframe id="stream-frame"
              src="{embed_url}"
              allow="autoplay;fullscreen;encrypted-media;picture-in-picture;accelerometer;gyroscope"
              allowfullscreen
              referrerpolicy="no-referrer-when-downgrade"
              scrolling="no"
              style="width:100%;height:100%;border:none;background:#000;"
              onload="document.getElementById('ifr-status').textContent='✅ تم التحميل';
                      document.getElementById('ifr-status').style.color='#4ade80';">
            </iframe>
          </div>
        </div>
        <script>
        (function(){{
          var frame  = document.getElementById('stream-frame');
          var status = document.getElementById('ifr-status');
          var wrap   = document.getElementById('player-wrap');
          var reloadCount = 0;
          var MAX_RELOADS = 5;
          var SRC = '{embed_url}';
          var ORIG_SRC = '{selected_url}';

          function setStatus(txt, color){{
            if(status){{ status.textContent=txt; status.style.color=color||'rgba(255,255,255,.6)'; }}
          }}

          // ── IFRAME LOAD EVENTS ────────────────────────────
          frame.addEventListener('load', function(){{
            setStatus('✅ البث جاهز', '#4ade80');
            reloadCount = 0;
          }});
          frame.addEventListener('error', function(){{
            handleError();
          }});

          function handleError(){{
            reloadCount++;
            if(reloadCount <= MAX_RELOADS){{
              var delay = Math.min(3000 * reloadCount, 15000);
              setStatus('⚠️ إعادة التحميل ' + reloadCount + '...', '#fbbf24');
              setTimeout(function(){{
                frame.src = SRC + (SRC.includes('?') ? '&' : '?') + '_r=' + Date.now();
              }}, delay);
            }} else {{
              setStatus('❌ فشل البث - جرب رابطاً آخر', '#f87171');
              // Show open externally button prominently
              wrap.innerHTML = '<div style="width:100%;height:100%;background:#000814;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:20px;text-align:center;">'
                + '<div style="font-size:3rem;">📡</div>'
                + '<div style="color:rgba(255,255,255,.7);font-size:.9rem;font-weight:600;">تعذّر عرض البث داخل الصفحة</div>'
                + '<a href="' + ORIG_SRC + '" target="_blank" style="background:linear-gradient(135deg,#c91c1c,#ef4444);color:#fff;padding:12px 28px;border-radius:14px;text-decoration:none;font-weight:800;font-size:.9rem;box-shadow:0 8px 24px rgba(239,68,68,.4);">▶ فتح البث مباشرة</a>'
                + '</div>';
            }}
          }}

          // ── AUTO-REFRESH for stale streams ──────────────
          // Many streaming sites expire their embed token every ~30min
          var refreshTimer = setInterval(function(){{
            if(!document.hidden && reloadCount < MAX_RELOADS){{
              setStatus('🔄 تحديث البث...', '#60a5fa');
              frame.src = SRC + (SRC.includes('?') ? '&' : '?') + '_t=' + Date.now();
            }}
          }}, 25 * 60 * 1000); // refresh every 25 minutes

          // ── VISIBILITY: resync when tab becomes active ───
          document.addEventListener('visibilitychange', function(){{
            if(!document.hidden){{
              setStatus('🔄 مزامنة...', '#60a5fa');
              setTimeout(function(){{
                frame.src = SRC + (SRC.includes('?') ? '&' : '?') + '_v=' + Date.now();
              }}, 500);
            }}
          }});
        }})();
        </script>"""

# ═══════════════════════════════════════════════
#  BUILD STREAM CARDS HTML
# ═══════════════════════════════════════════════
def get_stream_icon(s):
    url_l = s.get("url","").lower()
    src_l = s.get("source","").lower()
    if "youtube" in url_l or "youtube" in src_l:
        return '<span style="color:#FF0000;font-size:2rem;">▶</span>', "YouTube"
    if "facebook" in url_l or "facebook" in src_l:
        return '<span style="color:#4267B2;font-size:2rem;">f</span>', "Facebook"
    if "twitch" in url_l or "twitch" in src_l:
        return '<span style="color:#9146FF;font-size:2rem;">♟</span>', "Twitch"
    if "instagram" in url_l:
        return '<span style="color:#E1306C;font-size:2rem;">📷</span>', "Instagram"
    if "tiktok" in url_l:
        return '<span style="color:#010101;font-size:2rem;">♪</span>', "TikTok"
    if ".m3u8" in url_l or "hls" in src_l:
        return '<span style="color:#ef4444;font-size:2rem;">📡</span>', "HLS"
    if "admin" in src_l or "official" in src_l:
        return '<span style="color:#10b981;font-size:2rem;">🛡</span>', "رسمي"
    return '<span style="color:#1976d2;font-size:2rem;">▶</span>', "بث"

stream_cards_html = ""
if all_streams:
    for s in all_streams:
        icon_html, label = get_stream_icon(s)
        enc  = quote(s['url'], safe='')
        link = f"/watch_stream?match_id={match_id}&stream_url={enc}"
        title = s.get("title","بث مباشر")[:26]
        v_badge = '<span class="badge-v">✓ رسمي</span>' if s.get("verified") else ""
        hd_badge = '<span class="badge-hd">HD</span>' if any(x in s.get("title","").upper() for x in ["HD","1080","720"]) else ""
        is_active = selected_url == s.get("url","")
        active_cls = "stream-btn active" if is_active else "stream-btn"
        stream_cards_html += f"""
        <a href="{link}" class="{active_cls}">
          <div class="sb-icon">{icon_html}</div>
          <div class="sb-name">{title}</div>
          <div class="sb-type">{label}</div>
          <div class="sb-badges">{v_badge}{hd_badge}</div>
        </a>"""
else:
    stream_cards_html = """
    <div class="no-streams">
      <div style="font-size:2rem;margin-bottom:12px;">📡</div>
      <div style="font-weight:800;font-size:1rem;margin-bottom:6px;">لا توجد روابط بث متاحة</div>
      <div style="font-size:.82rem;opacity:.7;">يتم إضافة روابط البث قبل انطلاق المباراة مباشرةً</div>
    </div>"""

# ═══════════════════════════════════════════════
#  BUILD NEWS HTML
# ═══════════════════════════════════════════════
news_html = ""
for item in recent_news:
    title = item.get('title','')
    src   = item.get('source','')
    nurl  = item.get('url','#')
    img   = item.get('image','')
    try:
        dt = datetime.fromisoformat(item["published_at"].replace('Z','+00:00')).astimezone(tz_tunis)
        ds = dt.strftime("%H:%M — %d/%m")
    except Exception:
        ds = ""
    img_html = f'<img src="{img}" class="nc-img">' if img else '<div class="nc-img-ph">⚽</div>'
    news_html += f"""
    <a href="{nurl}" target="_blank" class="news-card">
      {img_html}
      <div class="nc-body">
        <div class="nc-title">{title}</div>
        <div class="nc-meta">📰 {src} &nbsp;🕒 {ds}</div>
      </div>
    </a>"""

# ═══════════════════════════════════════════════
#  BUILD SHARE URLS
# ═══════════════════════════════════════════════
try:
    host     = st.context.headers.get('host','')
    protocol = 'https' if st.context.headers.get('x-forwarded-proto','http')=='https' else 'http'
    base_url = f"{protocol}://{host}"
except Exception:
    base_url = "https://badr-tv.streamlit.app"

page_url   = f"{base_url}/watch_stream?match_id={match_id}"
share_text = quote(f"شاهد {home_team} vs {away_team} بث مباشر على Badr TV {page_url}")
wa_url  = f"https://wa.me/?text={share_text}"
tw_url  = f"https://twitter.com/intent/tweet?text={share_text}"
fb_url  = f"https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}"

# ═══════════════════════════════════════════════
#  LIVE BADGES
# ═══════════════════════════════════════════════
nav_live = '<span class="nav-live-pill"><span class="ndot"></span>LIVE</span>' if is_live else ""
score_color = "#ef4444" if is_live else "#1148b8"
meta_live_tag = (
    '<span class="tag tag-live"><span class="tdot"></span> مباشر الآن</span>'
    if is_live
    else f'<span class="tag">{score_label}</span>'
)

count_badge = f'<span class="count-badge">{len(all_streams)}</span>' if all_streams else ""

# ═══════════════════════════════════════════════
#  COMPLETE HTML PAGE
#  Rendered via st.components.v1.html() — the ONLY
#  method that guarantees CSS always applies in
#  Streamlit 1.56 regardless of re-runs or st.stop()
# ═══════════════════════════════════════════════
LOGO_URL = "https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg"

full_page = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
/* ═══ RESET ═══ */
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box;font-family:'Cairo',sans-serif;}}
html{{scroll-behavior:smooth;}}
body{{background:#eef2fd;color:#0d1829;min-height:100vh;overflow-x:hidden;}}
a{{text-decoration:none;color:inherit;}}

/* ═══ NAV ═══ */
.nav{{
  position:sticky;top:0;z-index:9999;
  background:linear-gradient(135deg,#071d5c 0%,#0f3391 40%,#1565c0 75%,#1976d2 100%);
  height:64px;display:flex;align-items:center;justify-content:space-between;
  padding:0 20px;
  box-shadow:0 4px 30px rgba(7,29,92,.5);
  border-bottom:1px solid rgba(255,255,255,.08);
}}
.nav-brand{{display:flex;align-items:center;gap:10px;}}
.nav-logo{{width:38px;height:38px;border-radius:50%;object-fit:cover;
  border:2px solid rgba(255,255,255,.35);box-shadow:0 0 14px rgba(255,255,255,.15);}}
.nav-name{{font-size:.95rem;font-weight:900;color:#fff;letter-spacing:.2px;line-height:1.1;}}
.nav-sub{{font-size:.58rem;color:rgba(255,255,255,.5);display:block;letter-spacing:.8px;}}
.nav-right{{display:flex;align-items:center;gap:10px;}}
.nav-live-pill{{
  background:linear-gradient(135deg,#c91c1c,#ef4444);
  color:#fff;border-radius:20px;padding:5px 12px;
  font-size:.7rem;font-weight:800;letter-spacing:1px;
  display:flex;align-items:center;gap:5px;
  box-shadow:0 0 16px rgba(239,68,68,.55);
  animation:glowpulse 1.4s infinite;
}}
.ndot{{width:7px;height:7px;background:#fff;border-radius:50%;animation:blink 1s infinite;}}
@keyframes glowpulse{{0%,100%{{box-shadow:0 0 16px rgba(239,68,68,.55);}}50%{{box-shadow:0 0 28px rgba(239,68,68,.85);}}}}
@keyframes blink{{0%,100%{{opacity:1;}}50%{{opacity:.1;}}}}
.back-btn{{
  background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);
  color:#fff;padding:7px 15px;border-radius:20px;
  font-size:.78rem;font-weight:700;transition:background .2s;white-space:nowrap;
}}
.back-btn:hover{{background:rgba(255,255,255,.26);}}

/* ═══ PAGE WRAPPER ═══ */
.page{{max-width:900px;margin:0 auto;padding:18px 14px 80px;}}

/* ═══ MATCH HERO ═══ */
.hero{{
  background:#fff;border-radius:24px;overflow:hidden;
  box-shadow:0 8px 40px rgba(15,56,200,.12);
  border:1px solid rgba(21,101,192,.12);
  margin-bottom:18px;position:relative;
}}
.hero-stripe{{
  height:5px;
  background:linear-gradient(90deg,#071d5c,#1565c0 45%,#ef4444);
}}
.hero-body{{padding:24px 18px 18px;}}
.hero-teams{{display:flex;align-items:center;justify-content:space-between;gap:12px;}}
.hero-team{{flex:1;text-align:center;}}
.hero-logo{{
  width:80px;height:80px;object-fit:contain;display:block;
  margin:0 auto 10px;
  filter:drop-shadow(0 6px 14px rgba(0,0,0,.14));
  transition:transform .3s cubic-bezier(.34,1.56,.64,1);
  border-radius:8px;
}}
.hero-logo:hover{{transform:scale(1.12);}}
.hero-team-name{{font-size:.95rem;font-weight:800;color:#0d1829;line-height:1.3;word-break:break-word;}}
.hero-score-box{{
  flex-shrink:0;text-align:center;
  background:linear-gradient(145deg,#eef2fd,#e0e9fc);
  border-radius:20px;padding:16px 20px;min-width:100px;
  border:1px solid rgba(21,101,192,.14);
}}
.hero-score-val{{
  font-size:2.8rem;font-weight:900;line-height:1;display:block;
  letter-spacing:2px;color:{score_color};
}}
.hero-score-lbl{{font-size:.68rem;font-weight:700;color:#8899bb;margin-top:5px;display:block;letter-spacing:.6px;}}
.hero-tags{{
  display:flex;align-items:center;justify-content:center;
  flex-wrap:wrap;gap:8px;margin-top:16px;padding-top:14px;
  border-top:1px solid #edf2fc;
}}
.tag{{
  background:#eef2fd;border:1px solid #d8e4f8;border-radius:20px;
  padding:5px 13px;font-size:.73rem;font-weight:600;color:#4a6090;
  display:inline-flex;align-items:center;gap:5px;
}}
.tag-live{{
  background:linear-gradient(135deg,#c91c1c,#ef4444);
  border-color:#ef4444;color:#fff;
  box-shadow:0 0 14px rgba(239,68,68,.4);
  animation:glowpulse 1.4s infinite;
}}
.tdot{{width:7px;height:7px;background:#fff;border-radius:50%;animation:blink 1s infinite;}}

/* ═══ AD SLOT ═══ */
.ad-slot{{
  background:linear-gradient(135deg,#f0f4ff,#e8eef8);
  border:1.5px dashed #b8cef0;border-radius:16px;
  padding:14px 18px;margin:0 0 18px;
  text-align:center;color:#8899bb;font-size:.82rem;
  min-height:70px;display:flex;align-items:center;justify-content:center;gap:8px;
}}

/* ═══ SECTION HEADER ═══ */
.sec-hdr{{
  display:flex;align-items:center;gap:11px;
  margin-bottom:14px;padding-bottom:12px;
  border-bottom:2px solid #dde8f8;
}}
.sec-hdr-icon{{
  width:38px;height:38px;border-radius:12px;
  background:linear-gradient(135deg,#0f3391,#1976d2);
  display:flex;align-items:center;justify-content:center;
  font-size:1.05rem;flex-shrink:0;
  box-shadow:0 4px 14px rgba(21,101,192,.3);
  color:#fff;
}}
.sec-hdr-title{{font-size:1.1rem;font-weight:800;color:#0d1829;}}
.count-badge{{
  background:#1976d2;color:#fff;border-radius:20px;
  padding:2px 10px;font-size:.7rem;font-weight:800;margin-right:auto;
}}

/* ═══ STREAM GRID ═══ */
.stream-grid{{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
  gap:12px;margin-bottom:18px;
}}
.stream-btn{{
  background:#fff;border:2px solid #dde8f8;border-radius:18px;
  padding:18px 12px 14px;text-align:center;
  display:flex;flex-direction:column;align-items:center;gap:7px;
  cursor:pointer;transition:all .22s cubic-bezier(.34,1.56,.64,1);
  box-shadow:0 3px 14px rgba(21,101,192,.06);position:relative;overflow:hidden;
}}
.stream-btn::before{{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#0f3391,#1976d2,#ef4444);
  opacity:0;transition:opacity .22s;
}}
.stream-btn:hover{{border-color:#1976d2;transform:translateY(-5px) scale(1.02);
  box-shadow:0 14px 32px rgba(21,101,192,.2);}}
.stream-btn:hover::before{{opacity:1;}}
.stream-btn.active{{border-color:#1976d2;background:linear-gradient(145deg,#eef2fd,#e0e9fc);
  box-shadow:0 8px 24px rgba(21,101,192,.22);}}
.stream-btn.active::before{{opacity:1;}}
.sb-icon{{font-size:2.4rem;line-height:1;}}
.sb-name{{font-weight:700;font-size:.88rem;color:#0d1829;line-height:1.3;}}
.sb-type{{font-size:.7rem;color:#7a90b8;}}
.sb-badges{{display:flex;gap:5px;flex-wrap:wrap;justify-content:center;}}
.badge-v{{background:#10b981;color:#fff;padding:2px 8px;border-radius:10px;font-size:.62rem;font-weight:800;}}
.badge-hd{{background:#7c3aed;color:#fff;padding:2px 8px;border-radius:10px;font-size:.62rem;font-weight:800;}}
.no-streams{{
  background:#fffbeb;border:1.5px solid #fde68a;border-right:5px solid #f59e0b;
  border-radius:18px;padding:28px 20px;text-align:center;color:#92400e;
  box-shadow:0 4px 16px rgba(245,158,11,.08);margin-bottom:18px;
}}

/* ═══ PLAYER ═══ */
.player-shell{{
  background:#000814;border-radius:22px;overflow:hidden;
  border:2px solid rgba(21,101,192,.3);
  box-shadow:0 20px 60px rgba(7,29,92,.3);
  margin-bottom:18px;
}}
.player-bar{{height:3px;background:linear-gradient(90deg,#0f3391,#1976d2,#ef4444);animation:barslide 2s linear infinite;background-size:200%;}}
@keyframes barslide{{0%{{background-position:0%}}100%{{background-position:200%}}}}
.player-topbar{{
  background:linear-gradient(90deg,rgba(7,29,92,.95),rgba(21,101,192,.7));
  padding:10px 16px;display:flex;align-items:center;justify-content:space-between;
  backdrop-filter:blur(10px);
}}
.ptb-left{{display:flex;align-items:center;gap:8px;}}
.live-badge-sm{{
  background:linear-gradient(135deg,#c91c1c,#ef4444);
  color:#fff;border-radius:6px;padding:3px 9px;
  font-size:.68rem;font-weight:800;letter-spacing:1px;
  animation:glowpulse 1.4s infinite;
}}
.ptb-title{{font-size:.82rem;font-weight:700;color:rgba(255,255,255,.85);}}
.ptb-ext{{
  background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);
  color:rgba(255,255,255,.8);padding:5px 12px;border-radius:10px;
  font-size:.72rem;font-weight:600;transition:background .2s;white-space:nowrap;
}}
.ptb-ext:hover{{background:rgba(255,255,255,.22);color:#fff;}}
.player-ratio{{position:relative;padding-bottom:56.25%;height:0;overflow:hidden;
  background:radial-gradient(ellipse,#0a1830,#000814);}}
.player-ratio iframe,.player-ratio video,.player-ratio #hlsp{{
  position:absolute;top:0;left:0;width:100%;height:100%;border:none;}}

/* ═══ NEWS ═══ */
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-bottom:18px;}}
.news-card{{
  background:#fff;border:1px solid #dde8f8;border-radius:16px;
  overflow:hidden;transition:all .18s;
  box-shadow:0 2px 10px rgba(21,101,192,.05);
  display:flex;flex-direction:column;
}}
.news-card:hover{{border-color:#1976d2;box-shadow:0 8px 24px rgba(21,101,192,.14);transform:translateY(-2px);}}
.nc-img{{width:100%;height:120px;object-fit:cover;display:block;}}
.nc-img-ph{{width:100%;height:80px;background:linear-gradient(135deg,#0f3391,#1976d2);
  display:flex;align-items:center;justify-content:center;font-size:1.8rem;color:rgba(255,255,255,.3);}}
.nc-body{{padding:12px;flex:1;}}
.nc-title{{font-size:.85rem;font-weight:700;color:#0d1829;line-height:1.5;margin-bottom:8px;}}
.nc-meta{{font-size:.7rem;color:#7a90b8;}}

/* ═══ SHARE ═══ */
.share-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:18px;}}
.share-btn{{
  display:flex;align-items:center;justify-content:center;gap:7px;
  padding:12px 8px;border-radius:14px;font-weight:700;font-size:.83rem;
  transition:all .18s;box-shadow:0 4px 14px rgba(0,0,0,.1);
  color:#fff;border:none;cursor:pointer;
}}
.share-btn:hover{{transform:translateY(-3px);filter:brightness(.9);}}
.sw{{background:#25D366;}}.st{{background:#1DA1F2;}}.sf{{background:#4267B2;}}

/* ═══ FOOTER ═══ */
.page-footer{{
  text-align:center;padding:20px;margin-top:10px;
  color:#8899bb;font-size:.75rem;
  border-top:1px solid #dde8f8;
}}

/* ═══ RESPONSIVE ═══ */
@media(max-width:600px){{
  .page{{padding:12px 10px 80px;}}
  .nav{{height:56px;padding:0 12px;}}
  .hero-logo{{width:60px;height:60px;}}
  .hero-team-name{{font-size:.82rem;}}
  .hero-score-val{{font-size:2.2rem;}}
  .hero-score-box{{padding:12px 14px;min-width:80px;}}
  .stream-grid{{grid-template-columns:repeat(2,1fr);gap:9px;}}
  .share-grid{{grid-template-columns:1fr 1fr;gap:8px;}}
  .news-grid{{grid-template-columns:1fr;}}
  .sec-hdr-title{{font-size:.95rem;}}
  .player-topbar{{flex-direction:column;align-items:flex-start;gap:6px;}}
}}
</style>
</head>
<body>

<!-- NAV -->
<nav class="nav">
  <div class="nav-brand">
    <img src="{LOGO_URL}" class="nav-logo" alt="Badr TV">
    <div>
      <div class="nav-name">Badr TV</div>
      <span class="nav-sub">منصة كرة القدم الشاملة</span>
    </div>
  </div>
  <div class="nav-right">
    {nav_live}
    <a href="/" class="back-btn">← الرئيسية</a>
  </div>
</nav>

<div class="page">

  <!-- MATCH HERO -->
  <div class="hero">
    <div class="hero-stripe"></div>
    <div class="hero-body">
      <div class="hero-teams">
        <div class="hero-team">
          <img src="{home_logo}" class="hero-logo" onerror="this.src='https://ui-avatars.com/api/?name=HM&background=0f3391&color=fff&size=80&bold=true'">
          <div class="hero-team-name">{home_team}</div>
        </div>
        <div class="hero-score-box">
          <span class="hero-score-val">{score_display}</span>
          <span class="hero-score-lbl">{score_label}</span>
        </div>
        <div class="hero-team">
          <img src="{away_logo}" class="hero-logo" onerror="this.src='https://ui-avatars.com/api/?name=AW&background=0a2d7a&color=fff&size=80&bold=true'">
          <div class="hero-team-name">{away_team}</div>
        </div>
      </div>
      <div class="hero-tags">
        <span class="tag">🏆 {league}</span>
        <span class="tag">🕐 {time_str}</span>
        {meta_live_tag}
      </div>
    </div>
  </div>

  <!-- AD TOP -->
  <div class="ad-slot">📢 مساحة إعلانية</div>

  <!-- STREAM SECTION -->
  <div class="sec-hdr">
    <div class="sec-hdr-icon">📡</div>
    <div class="sec-hdr-title">اختر قناة البث</div>
    {count_badge}
  </div>
  <div class="stream-grid">
    {stream_cards_html}
  </div>

  <!-- PLAYER -->
  {player_html}

  <!-- AD MID -->
  {"<div class='ad-slot'>📢 مساحة إعلانية</div>" if selected_url else ""}

  <!-- NEWS -->
  {"<div class='sec-hdr'><div class='sec-hdr-icon'>📰</div><div class='sec-hdr-title'>آخر الأخبار</div></div><div class='news-grid'>" + news_html + "</div>" if recent_news else ""}

  <!-- SHARE -->
  <div class="sec-hdr">
    <div class="sec-hdr-icon">📤</div>
    <div class="sec-hdr-title">شارك المباراة</div>
  </div>
  <div class="share-grid">
    <a href="{wa_url}" target="_blank" class="share-btn sw"><i class="fab fa-whatsapp"></i> واتساب</a>
    <a href="{tw_url}" target="_blank" class="share-btn st"><i class="fab fa-twitter"></i> تويتر</a>
    <a href="{fb_url}" target="_blank" class="share-btn sf"><i class="fab fa-facebook-f"></i> فيسبوك</a>
  </div>

  <div class="page-footer">
    Badr TV © {datetime.now().year} — منصة كرة القدم الشاملة
  </div>

</div><!-- /page -->

</body>
</html>"""

# ═══════════════════════════════════════════════
#  RENDER — single HTML component, CSS guaranteed
# ═══════════════════════════════════════════════
components.html(full_page, height=4200, scrolling=True)
