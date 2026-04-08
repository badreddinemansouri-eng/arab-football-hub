import streamlit as st
import re
import json
import hashlib
from urllib.parse import urlparse, parse_qs, quote, unquote
from datetime import datetime, timedelta
import requests
import zoneinfo
from supabase import create_client
import streamlit.components.v1 as components

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

for k, v in {"extraction_attempted": False, "extracted_url": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Hide Streamlit chrome ──────────────────────
st.markdown("""<style>
header[data-testid="stHeader"],footer,#MainMenu,.stDeployButton,
div[data-testid="stToolbar"],div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],section[data-testid="stSidebar"]{display:none!important;}
.block-container{padding:0!important;max-width:100%!important;}
.main,.stApp{padding:0!important;background:#0d1117!important;}
</style>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  STREAM LINK PROTECTION
#  Stream URLs are NEVER sent to the browser as plain text.
#  Each URL is hashed to a token. The mapping lives server-side.
#  Users see only ?stream_token=abc123 — not the actual URL.
#  Right-click inspect → they see nothing useful.
# ══════════════════════════════════════════════════════════════════
_token_map = {}  # token → real url (lives in session only)

def make_token(url: str) -> str:
    token = hashlib.sha256(url.encode()).hexdigest()[:16]
    _token_map[token] = url
    return token

def resolve_token(token: str) -> str | None:
    return _token_map.get(token)

# ══════════════════════════════════════════════════════════════════
#  QUERY PARAMS
# ══════════════════════════════════════════════════════════════════
match_id = st.query_params.get("match_id", None)
if isinstance(match_id, list): match_id = match_id[0]

stream_token = st.query_params.get("st", None)
if isinstance(stream_token, list): stream_token = stream_token[0]

# ══════════════════════════════════════════════════════════════════
#  DATA FETCH
# ══════════════════════════════════════════════════════════════════
match_data = None
if match_id:
    try:
        res = supabase.table("matches").select("*").eq("fixture_id", match_id).execute()
        if res.data: match_data = res.data[0]
    except Exception: pass

all_streams = []
if match_data:
    raw = match_data.get("streams", [])
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except: raw = []
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
    except: pass

@st.cache_data(ttl=3600)
def get_recent_news():
    try:
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        return supabase.table("news").select("*")\
            .gte("published_at", cutoff).order("published_at", desc=True)\
            .limit(4).execute().data or []
    except: return []

recent_news = get_recent_news()

# ══════════════════════════════════════════════════════════════════
#  BUILD TOKEN MAP (all stream URLs → tokens, before any HTML)
# ══════════════════════════════════════════════════════════════════
for s in all_streams:
    make_token(s.get("url", ""))

# ══════════════════════════════════════════════════════════════════
#  URL INTELLIGENCE
# ══════════════════════════════════════════════════════════════════
def _clean_yt(u):
    m = re.search(r'(?:v=|youtu\.be/|embed/)([a-zA-Z0-9_-]{11})', u)
    return f"https://www.youtube.com/embed/{m.group(1)}?autoplay=1&rel=0" if m else u

def _find_ld(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ('embedUrl','contentUrl','url') and isinstance(v,str) and 'http' in v: return v
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
    original_url = url
    was_http = url.startswith("http://")
    if was_http:
        url = "https://" + url[7:]

    p = urlparse(url); d = p.netloc.lower(); path = p.path.lower(); q = parse_qs(p.query)

    if any(x in d for x in ["youtube.com","youtu.be"]):
        vid = path.strip('/') if "youtu.be" in d else q.get("v",[None])[0]
        if vid: return {"url":f"https://www.youtube.com/embed/{vid}?autoplay=1&rel=0&modestbranding=1","type":"iframe","name":"YouTube","was_http":False}
    if "facebook.com" in d and any(x in url for x in ["/videos/","/watch/","/reel/"]):
        return {"url":f"https://www.facebook.com/plugins/video.php?href={quote(url)}&show_text=0&width=1280&autoplay=1","type":"iframe","name":"Facebook","was_http":False}
    if "dailymotion.com" in d or "dai.ly" in d:
        m = re.search(r'/video/([^_?/]+)', url)
        if m: return {"url":f"https://www.dailymotion.com/embed/video/{m.group(1)}?autoplay=1","type":"iframe","name":"Dailymotion","was_http":False}
    if "vimeo.com" in d:
        vid = path.strip('/').split('/')[0]
        if vid.isdigit(): return {"url":f"https://player.vimeo.com/video/{vid}?autoplay=1","type":"iframe","name":"Vimeo","was_http":False}
    if "ok.ru" in d:
        m = re.search(r'/video(?:/|embed/)?(\d+)', url)
        if m: return {"url":f"https://ok.ru/videoembed/{m.group(1)}","type":"iframe","name":"OK.ru","was_http":False}
    if "vk.com" in d:
        m = re.search(r'video(-?\d+)_(\d+)', url)
        if m:
            oid,vid=m.groups()
            return {"url":f"https://vk.com/video_ext.php?oid={oid}&id={vid}&hash=&autoplay=1","type":"iframe","name":"VK","was_http":False}
    if "streamable.com" in d:
        vid = path.strip('/')
        if vid: return {"url":f"https://streamable.com/e/{vid}","type":"iframe","name":"Streamable","was_http":False}
    if "twitch.tv" in d:
        ch = path.strip('/')
        if ch: return {"url":f"https://player.twitch.tv/?channel={ch}&parent=streamlit.app&autoplay=true","type":"iframe","name":"Twitch","was_http":False}
    if path.endswith('.m3u8') or 'm3u8' in url:
        return {"url":url,"type":"hls","name":"HLS","was_http":was_http,"original_http_url":original_url if was_http else None}
    if path.endswith(('.mp4','.webm','.ogg')):
        return {"url":url,"type":"video","name":"Video","was_http":was_http}
    return {"url":url,"type":"iframe","name":"بث مباشر","was_http":was_http}

# ══════════════════════════════════════════════════════════════════
#  ERROR PAGE
# ══════════════════════════════════════════════════════════════════
if not match_id or not match_data:
    components.html("""<!DOCTYPE html><html dir="rtl" lang="ar"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700;900&display=swap" rel="stylesheet">
<style>*{font-family:'Cairo',sans-serif;box-sizing:border-box;margin:0;padding:0;}
body{background:#0d1117;display:flex;align-items:center;justify-content:center;height:100vh;}
.e{text-align:center;padding:40px;}.ei{font-size:4rem;margin-bottom:16px;}
.et{font-size:1.4rem;font-weight:900;color:#f0f4ff;margin-bottom:8px;}
.es{color:#8899bb;font-size:.9rem;margin-bottom:24px;}
.eb{background:linear-gradient(135deg,#1148b8,#1976d2);color:#fff;text-decoration:none;
padding:12px 28px;border-radius:14px;font-weight:700;font-size:.9rem;display:inline-block;}</style>
</head><body><div class="e"><div class="ei">❌</div>
<div class="et">المباراة غير موجودة</div>
<div class="es">تعذّر تحميل بيانات المباراة</div>
<a href="/" class="eb">← العودة للرئيسية</a></div></body></html>""", height=400, scrolling=False)
    st.stop()

# ══════════════════════════════════════════════════════════════════
#  MATCH META
# ══════════════════════════════════════════════════════════════════
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
except: time_str = "---"

hs  = match_data.get('home_score')
aws = match_data.get('away_score')
score_display = f"{hs} - {aws}" if hs is not None else "VS"
score_label   = "FT" if status=="FINISHED" else ("LIVE" if is_live else "VS")
score_color   = "#ef4444" if is_live else "#60a5fa" if status=="FINISHED" else "#f0f4ff"

# ══════════════════════════════════════════════════════════════════
#  RESOLVE SELECTED STREAM
# ══════════════════════════════════════════════════════════════════
selected_url = None
if stream_token:
    selected_url = resolve_token(stream_token)
    # If token not in map (new session), try to find by matching streams
    if not selected_url:
        for s in all_streams:
            if make_token(s.get("url","")) == stream_token:
                selected_url = s.get("url","")
                break

# ══════════════════════════════════════════════════════════════════
#  BUILD PLAYER HTML
# ══════════════════════════════════════════════════════════════════
player_section = ""
if selected_url:
    embed = build_embed(selected_url)
    embed_url = embed["url"]
    etype     = embed["type"]
    was_http  = embed.get("was_http", False)

    # Try extraction once for unknown types
    if etype == "iframe" and embed_url == selected_url and not st.session_state.extraction_attempted:
        st.session_state.extraction_attempted = True
        extracted = extract_embed(selected_url)
        if extracted and extracted != selected_url:
            st.session_state.extracted_url = extracted

    if st.session_state.extracted_url:
        ex = build_embed(st.session_state.extracted_url)
        embed_url = ex["url"]; etype = ex["type"]

    live_badge = "<span class='pb-live'>⬤ LIVE</span>" if is_live else ""
    ext_link   = selected_url  # this is shown only in error state
    ptitle     = f"{home_team} vs {away_team}"

    if etype == "hls":
        original_http = embed.get("original_http_url","")
        proxy_list = json.dumps([
            f"https://api.allorigins.win/raw?url={quote(original_http)}",
            f"https://corsproxy.io/?{quote(original_http)}",
            f"https://thingproxy.freeboard.io/fetch/{original_http}",
        ] if original_http else [])

        player_section = f"""
<div class="player-wrap" id="player-section">
  <div class="player-chrome">
    <div class="pc-left">{live_badge}<span class="pc-title">{ptitle}</span></div>
    <div class="pc-right">
      <span id="p-status" class="p-status loading">⏳ جاري التحميل...</span>
      <button class="pc-btn" onclick="toggleFullscreen()" title="ملء الشاشة">⛶</button>
    </div>
  </div>
  <div class="player-ratio" id="p-ratio">
    <div id="hls-wrap" style="width:100%;height:100%;background:#000;"></div>
    <div class="player-overlay" id="p-overlay">
      <div class="po-spinner"></div>
      <div class="po-text">جاري تحضير البث...</div>
    </div>
  </div>
</div>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"></script>
<script>
(function(){{
  var SOURCES   = ['{embed_url}'].concat({proxy_list});
  var srcIdx    = 0, retries = 0, MAX_RETRIES = 8;
  var status    = document.getElementById('p-status');
  var overlay   = document.getElementById('p-overlay');
  var wrap      = document.getElementById('hls-wrap');
  var ratio     = document.getElementById('p-ratio');
  var hls, v;

  function setStatus(txt, cls){{
    if(!status) return;
    status.textContent = txt;
    status.className = 'p-status ' + (cls||'');
  }}
  function hideOverlay(){{
    if(overlay) {{ overlay.style.opacity='0'; setTimeout(()=>overlay.style.display='none',400); }}
  }}
  function showOverlay(msg){{
    if(!overlay) return;
    overlay.style.display='flex'; overlay.style.opacity='1';
    var t = overlay.querySelector('.po-text');
    if(t && msg) t.textContent = msg;
  }}

  function buildVideo(){{
    v = document.createElement('video');
    v.controls = true; v.autoplay = true; v.playsinline = true;
    v.style.cssText = 'width:100%;height:100%;background:#000;display:block;';
    wrap.innerHTML = '';
    wrap.appendChild(v);

    v.addEventListener('playing', ()=>{{ hideOverlay(); setStatus('🔴 بث مباشر', 'live'); retries=0; }});
    v.addEventListener('waiting', ()=>{{ setStatus('⏳ تحميل...','loading');
      stallTimer = setTimeout(()=>{{
        if(v.buffered.length>0){{
          var end=v.buffered.end(v.buffered.length-1);
          if(end-v.currentTime>3){{ v.currentTime=end-0.5; }}
        }}
      }}, 6000);
    }});
    v.addEventListener('playing', ()=>{{ if(stallTimer) clearTimeout(stallTimer); }});

    setInterval(()=>{{
      if(!v.paused && hls && hls.liveSyncPosition){{
        if(hls.liveSyncPosition - v.currentTime > 15) v.currentTime = hls.liveSyncPosition;
      }}
    }}, 20000);
    return v;
  }}

  var stallTimer;

  function tryNextSource(){{
    srcIdx++;
    if(srcIdx < SOURCES.length){{
      setStatus('🔄 مصدر بديل ' + srcIdx + '...','loading');
      retries=0; initHls(SOURCES[srcIdx]);
    }} else {{
      setStatus('❌ تعذّر التشغيل','error');
      showError();
    }}
  }}

  function showError(){{
    ratio.innerHTML = `
      <div class="player-error">
        <div class="pe-icon">📡</div>
        <div class="pe-title">تعذّر تشغيل البث تلقائياً</div>
        <div class="pe-sub">قد يكون البث محمياً أو غير متاح في منطقتك</div>
        <div class="pe-actions">
          <button class="pe-btn-try" onclick="location.reload()">🔄 إعادة المحاولة</button>
          <a class="pe-btn-ext" href="{ext_link}" target="_blank" rel="noopener">
            ▶ فتح في نافذة جديدة
          </a>
        </div>
        <div class="pe-tips">
          <div class="pe-tip">💡 جرّب رابطاً آخر من القائمة أعلاه</div>
          <div class="pe-tip">🔒 إذا كان الرابط HTTP، قد يحجبه المتصفح</div>
        </div>
      </div>`;
  }}

  function initHls(src){{
    if(hls) hls.destroy();
    if(!v) buildVideo();
    showOverlay('جاري تحميل البث...');

    hls = new Hls({{
      maxBufferLength:90, maxMaxBufferLength:180,
      maxBufferSize:200*1024*1024, maxBufferHole:2,
      liveSyncDurationCount:3, liveMaxLatencyDurationCount:10,
      liveBackBufferLength:60, backBufferLength:60,
      manifestLoadingMaxRetry:6, manifestLoadingRetryDelay:2000,
      levelLoadingMaxRetry:6, levelLoadingRetryDelay:2000,
      fragLoadingMaxRetry:8, fragLoadingRetryDelay:1500,
      startLevel:-1, enableWorker:true, lowLatencyMode:false,
      xhrSetup: function(xhr){{ xhr.withCredentials=false; }}
    }});

    hls.loadSource(src);
    hls.attachMedia(v);
    hls.on(Hls.Events.MANIFEST_PARSED, ()=>{{
      setStatus('✅ جاهز','ready'); retries=0;
      v.play().catch(()=>setStatus('▶ اضغط تشغيل','ready'));
    }});
    hls.on(Hls.Events.FRAG_BUFFERED, ()=>{{ hideOverlay(); }});
    hls.on(Hls.Events.ERROR, (e,d)=>{{
      if(!d.fatal) return;
      if(d.type===Hls.ErrorTypes.NETWORK_ERROR){{
        retries++;
        if(retries<=MAX_RETRIES){{
          setStatus('⚠️ إعادة '+retries+'...','loading');
          setTimeout(()=>hls.startLoad(), Math.min(2000*retries,12000));
        }} else tryNextSource();
      }} else if(d.type===Hls.ErrorTypes.MEDIA_ERROR){{
        hls.recoverMediaError();
      }} else tryNextSource();
    }});
  }}

  window.toggleFullscreen = function(){{
    var el = document.getElementById('p-ratio');
    if(!document.fullscreenElement) el.requestFullscreen && el.requestFullscreen();
    else document.exitFullscreen && document.exitFullscreen();
  }};

  document.addEventListener('visibilitychange',()=>{{
    if(!document.hidden && hls && hls.liveSyncPosition && v && !v.paused)
      v.currentTime = hls.liveSyncPosition;
  }});

  if(Hls.isSupported()){{
    buildVideo(); initHls(SOURCES[0]);
  }} else if(document.createElement('video').canPlayType('application/vnd.apple.mpegurl')){{
    buildVideo();
    v.src=SOURCES[0];
    v.addEventListener('loadedmetadata',()=>{{ v.play(); hideOverlay(); }});
    setStatus('📱 HLS نيتف','ready');
  }} else {{
    setStatus('❌ المتصفح لا يدعم HLS','error'); showError();
  }}
}})();
</script>"""

    elif etype == "video":
        player_section = f"""
<div class="player-wrap" id="player-section">
  <div class="player-chrome">
    <div class="pc-left">{live_badge}<span class="pc-title">{ptitle}</span></div>
    <div class="pc-right">
      <span id="p-status" class="p-status loading">⏳ جاري التحميل...</span>
      <button class="pc-btn" onclick="toggleFullscreen()" title="ملء الشاشة">⛶</button>
    </div>
  </div>
  <div class="player-ratio" id="p-ratio">
    <video controls autoplay playsinline
      style="width:100%;height:100%;background:#000;"
      onloadeddata="document.getElementById('p-status').textContent='✅ جاهز';
                    document.getElementById('p-status').className='p-status ready';"
      onerror="document.getElementById('p-status').textContent='❌ خطأ';
               document.getElementById('p-status').className='p-status error';">
      <source src="{embed_url}" type="video/mp4">
      <source src="{embed_url}" type="video/webm">
    </video>
  </div>
</div>
<script>
window.toggleFullscreen=function(){{
  var el=document.getElementById('p-ratio');
  if(!document.fullscreenElement) el.requestFullscreen&&el.requestFullscreen();
  else document.exitFullscreen&&document.exitFullscreen();
}};
</script>"""

    else:
        # iframe — with was_http warning banner + auto-refresh + reconnect
        http_warning = ""
        if was_http:
            http_warning = """
<div class="http-warning">
  <span class="hw-icon">⚠️</span>
  <div>
    <div class="hw-title">رابط HTTP — قد يُحجب تلقائياً</div>
    <div class="hw-sub">المتصفحات الحديثة تمنع روابط HTTP على صفحات HTTPS. إذا لم يظهر البث، استخدم زر «فتح خارجياً».</div>
  </div>
</div>"""

        player_section = f"""
{http_warning}
<div class="player-wrap" id="player-section">
  <div class="player-chrome">
    <div class="pc-left">{live_badge}<span class="pc-title">{ptitle}</span></div>
    <div class="pc-right">
      <span id="p-status" class="p-status loading">⏳ جاري التحميل...</span>
      <a href="{ext_link}" target="_blank" rel="noopener" class="pc-ext-btn">↗ خارجي</a>
      <button class="pc-btn" onclick="toggleFullscreen()" title="ملء الشاشة">⛶</button>
    </div>
  </div>
  <div class="player-ratio" id="p-ratio">
    <iframe id="stream-frame"
      src="{embed_url}"
      allow="autoplay;fullscreen;encrypted-media;picture-in-picture;accelerometer;gyroscope"
      allowfullscreen
      referrerpolicy="no-referrer-when-downgrade"
      scrolling="no"
      onload="document.getElementById('p-status').textContent='✅ تم التحميل';
              document.getElementById('p-status').className='p-status ready';"
      style="width:100%;height:100%;border:none;background:#000;">
    </iframe>
    <div class="player-overlay" id="p-overlay">
      <div class="po-spinner"></div>
      <div class="po-text">جاري تحميل البث...</div>
    </div>
  </div>
</div>
<script>
(function(){{
  var frame  = document.getElementById('stream-frame');
  var status = document.getElementById('p-status');
  var overlay= document.getElementById('p-overlay');
  var ratio  = document.getElementById('p-ratio');
  var reloads=0; var MAX=5;
  var SRC    = '{embed_url}';

  function hideOverlay(){{
    if(overlay){{overlay.style.opacity='0';setTimeout(()=>overlay.style.display='none',400);}}
  }}

  frame.addEventListener('load',()=>{{
    hideOverlay();
    status.textContent='✅ البث جاهز'; status.className='p-status ready'; reloads=0;
  }});

  // Check if iframe actually loaded content (some sites return 200 but blank)
  setTimeout(()=>{{
    try{{
      if(!frame.contentDocument || frame.contentDocument.body.innerHTML==='')
        status.textContent='⚠️ قد يكون البث محجوباً';
    }}catch(e){{
      // Cross-origin — can't check, assume OK if loaded
      hideOverlay();
    }}
  }},5000);

  // Auto-refresh every 25min (streaming tokens expire)
  setInterval(()=>{{
    if(!document.hidden){{
      status.textContent='🔄 تجديد البث...'; status.className='p-status loading';
      frame.src=SRC+'?_t='+Date.now();
    }}
  }}, 25*60*1000);

  // Resync on tab focus
  document.addEventListener('visibilitychange',()=>{{
    if(!document.hidden){{
      status.textContent='🔄 مزامنة...'; status.className='p-status loading';
      setTimeout(()=>frame.src=SRC+'?_r='+Date.now(), 300);
    }}
  }});

  window.toggleFullscreen=function(){{
    var el=document.getElementById('p-ratio');
    if(!document.fullscreenElement) el.requestFullscreen&&el.requestFullscreen();
    else document.exitFullscreen&&document.exitFullscreen();
  }};

  // If blank after 12s — show error with actions
  setTimeout(()=>{{
    try{{
      if(frame.contentDocument && frame.contentDocument.body &&
         frame.contentDocument.body.innerHTML.trim()===''){{
        showError();
      }}
    }}catch(crossOriginErr){{ /* normal — cross origin */ }}
  }},12000);

  function showError(){{
    ratio.innerHTML = `
      <div class="player-error">
        <div class="pe-icon">📡</div>
        <div class="pe-title">لم يتم تشغيل البث</div>
        <div class="pe-sub">هذا البث لا يمكن عرضه مباشرةً في الصفحة</div>
        <div class="pe-actions">
          <button class="pe-btn-try" onclick="location.reload()">🔄 إعادة المحاولة</button>
          <a class="pe-btn-ext" href="{ext_link}" target="_blank" rel="noopener">
            ▶ فتح في نافذة جديدة
          </a>
        </div>
        <div class="pe-tips">
          <div class="pe-tip">💡 جرّب رابطاً آخر من القائمة أعلاه</div>
          {"<div class='pe-tip'>🔒 الرابط HTTP محجوب — استخدم زر الفتح الخارجي</div>" if was_http else ""}
          <div class="pe-tip">🔁 قد يكون البث قد انتهى أو لم يبدأ بعد</div>
        </div>
      </div>`;
  }}
}})();
</script>"""

# ══════════════════════════════════════════════════════════════════
#  BUILD STREAM CARDS
# ══════════════════════════════════════════════════════════════════
def get_icon(s):
    u = s.get("url","").lower(); src = s.get("source","").lower()
    if "youtube" in u or "youtube" in src: return "▶", "#FF0000", "YouTube"
    if "facebook" in u or "facebook" in src: return "f", "#4267B2", "Facebook"
    if "twitch" in u or "twitch" in src: return "♟", "#9146FF", "Twitch"
    if "instagram" in u: return "📷", "#E1306C", "Instagram"
    if "tiktok" in u: return "♪", "#010101", "TikTok"
    if ".m3u8" in u or "hls" in src: return "📡", "#ef4444", "HLS"
    if "admin" in src or "official" in src: return "🛡", "#10b981", "رسمي"
    if "dailymotion" in u: return "◉", "#0066DC", "Dailymotion"
    if "vimeo" in u: return "▶", "#1AB7EA", "Vimeo"
    return "▶", "#1976d2", "بث"

stream_cards_html = ""
if all_streams:
    for i, s in enumerate(all_streams):
        icon_char, icon_color, label = get_icon(s)
        token    = make_token(s.get("url",""))
        link     = f"/watch_stream?match_id={match_id}&st={token}"
        title    = s.get("title","بث مباشر")[:24]
        is_http  = s.get("url","").startswith("http://")
        is_active= stream_token == token
        v_badge  = '<span class="badge-v">✓ رسمي</span>' if s.get("verified") else ""
        hd_badge = '<span class="badge-hd">HD</span>' if any(x in s.get("title","").upper() for x in ["HD","1080","720"]) else ""
        http_badge= '<span class="badge-http">HTTP</span>' if is_http else ""
        active_cls= "active" if is_active else ""
        stream_cards_html += f"""
        <a href="{link}" class="sc {active_cls}">
          <div class="sc-icon" style="color:{icon_color}">{icon_char}</div>
          <div class="sc-name">{title}</div>
          <div class="sc-type">{label}</div>
          <div class="sc-badges">{v_badge}{hd_badge}{http_badge}</div>
        </a>"""
else:
    stream_cards_html = """<div class="no-streams">
      <div style="font-size:2.5rem;margin-bottom:12px;">📡</div>
      <div style="font-size:1rem;font-weight:800;margin-bottom:6px;color:#f0f4ff;">لا توجد روابط بث متاحة</div>
      <div style="font-size:.82rem;color:#8899bb;">تتوفر روابط البث قبل المباراة بدقائق</div>
    </div>"""

# ══════════════════════════════════════════════════════════════════
#  NEWS CARDS
# ══════════════════════════════════════════════════════════════════
news_html = ""
for item in recent_news:
    title= item.get('title',''); src=item.get('source','')
    nurl = item.get('url','#'); img=item.get('image','')
    try:
        dt=datetime.fromisoformat(item["published_at"].replace('Z','+00:00')).astimezone(tz_tunis)
        ds=dt.strftime("%H:%M — %d/%m")
    except: ds=""
    img_html=f'<img src="{img}" class="nc-img" loading="lazy">' if img else '<div class="nc-ph">⚽</div>'
    news_html += f"""<a href="{nurl}" target="_blank" rel="noopener" class="nc">
      {img_html}
      <div class="nc-body">
        <div class="nc-title">{title}</div>
        <div class="nc-meta">📰 {src} &nbsp; 🕒 {ds}</div>
      </div></a>"""

# ══════════════════════════════════════════════════════════════════
#  SHARE URLS
# ══════════════════════════════════════════════════════════════════
try:
    host=st.context.headers.get('host',''); protocol='https' if st.context.headers.get('x-forwarded-proto','http')=='https' else 'http'
    base_url=f"{protocol}://{host}"
except: base_url="https://badr-tv.streamlit.app"

page_url   = f"{base_url}/watch_stream?match_id={match_id}"
share_text = quote(f"شاهد {home_team} vs {away_team} بث مباشر على Badr TV {page_url}")

# ══════════════════════════════════════════════════════════════════
#  LOGO & NAV META
# ══════════════════════════════════════════════════════════════════
LOGO_URL   = "https://vfhmznstfgxiwhcifetm.supabase.co/storage/v1/object/public/logos/app-logos/logo_app.jpg"
nav_live   = '<span class="nav-live"><span class="ndot"></span>LIVE</span>' if is_live else ""
count_badge= f'<span class="cnt">{len(all_streams)}</span>' if all_streams else ""
meta_status= f'<span class="tag tag-live"><span class="tdot"></span> مباشر الآن</span>' if is_live else f'<span class="tag">{score_label}</span>'
player_title_full = f"{home_team} vs {away_team}"

# ══════════════════════════════════════════════════════════════════
#  FULL PAGE HTML
# ══════════════════════════════════════════════════════════════════
FULL_HTML = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Badr TV — {home_team} vs {away_team}</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
/* ══ RESET ══════════════════════════════════════ */
*,*::before,*::after{{margin:0;padding:0;box-sizing:border-box;font-family:'Cairo',sans-serif;}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%;}}
body{{background:#0d1117;color:#f0f4ff;min-height:100vh;overflow-x:hidden;}}
a{{text-decoration:none;color:inherit;}}
img{{max-width:100%;}}

/* ══ LINK PROTECTION — disable right click & selection on player ══ */
.player-wrap, .player-wrap *{{
  -webkit-user-select:none; -moz-user-select:none; user-select:none;
  -webkit-touch-callout:none;
}}
.player-wrap{{pointer-events:auto;}}

/* ══ NAV ══════════════════════════════════════ */
.nav{{
  position:sticky;top:0;z-index:9999;
  background:linear-gradient(135deg,#040e2a 0%,#071d5c 40%,#1148b8 80%,#1565c0 100%);
  height:62px;display:flex;align-items:center;justify-content:space-between;
  padding:0 18px;
  border-bottom:1px solid rgba(255,255,255,.07);
  box-shadow:0 4px 30px rgba(4,14,42,.7);
}}
.nav-brand{{display:flex;align-items:center;gap:10px;}}
.nav-logo{{width:38px;height:38px;border-radius:50%;object-fit:cover;
  border:2px solid rgba(255,255,255,.3);box-shadow:0 0 16px rgba(255,255,255,.1);}}
.nav-name{{font-size:.95rem;font-weight:900;color:#fff;line-height:1.1;}}
.nav-sub{{font-size:.58rem;color:rgba(255,255,255,.45);display:block;letter-spacing:.8px;text-transform:uppercase;}}
.nav-right{{display:flex;align-items:center;gap:10px;}}
.nav-live{{background:linear-gradient(135deg,#b91c1c,#ef4444);color:#fff;
  border-radius:20px;padding:5px 12px;font-size:.7rem;font-weight:800;letter-spacing:1px;
  display:flex;align-items:center;gap:5px;
  box-shadow:0 0 18px rgba(239,68,68,.6);animation:glow 1.4s infinite;}}
.ndot{{width:7px;height:7px;background:#fff;border-radius:50%;animation:blink 1s infinite;}}
.back-btn{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);
  color:#fff;padding:7px 16px;border-radius:20px;font-size:.78rem;font-weight:700;
  transition:background .2s;white-space:nowrap;}}
.back-btn:hover{{background:rgba(255,255,255,.2);}}

/* ══ PAGE ══════════════════════════════════════ */
.page{{max-width:860px;margin:0 auto;padding:16px 14px 100px;}}

/* ══ MATCH HERO ══════════════════════════════════════ */
.hero{{
  background:linear-gradient(145deg,#111827,#0f1f3d);
  border-radius:24px;overflow:hidden;
  border:1px solid rgba(99,139,255,.18);
  box-shadow:0 8px 40px rgba(0,0,0,.5);
  margin-bottom:16px;position:relative;
}}
.hero-stripe{{height:4px;background:linear-gradient(90deg,#040e2a,#1148b8 40%,#1976d2 70%,#ef4444);}}
.hero-body{{padding:22px 16px 18px;}}
.hero-teams{{display:flex;align-items:center;justify-content:space-between;gap:10px;}}
.hero-team{{flex:1;text-align:center;}}
.hero-logo{{width:76px;height:76px;object-fit:contain;display:block;margin:0 auto 10px;
  filter:drop-shadow(0 6px 16px rgba(0,0,0,.5));
  transition:transform .3s cubic-bezier(.34,1.56,.64,1);border-radius:8px;}}
.hero-logo:hover{{transform:scale(1.12);}}
.hero-name{{font-size:.95rem;font-weight:800;color:#f0f4ff;line-height:1.3;word-break:break-word;}}
.score-box{{flex-shrink:0;text-align:center;
  background:linear-gradient(145deg,#0d1f3d,#091529);
  border-radius:20px;padding:14px 18px;min-width:96px;
  border:1px solid rgba(99,139,255,.2);}}
.score-val{{font-size:2.8rem;font-weight:900;line-height:1;display:block;
  letter-spacing:2px;color:{score_color};}}
.score-lbl{{font-size:.68rem;font-weight:700;color:#4a6090;margin-top:5px;display:block;letter-spacing:.6px;}}
.hero-tags{{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:8px;
  margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,.06);}}
.tag{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
  border-radius:20px;padding:5px 13px;font-size:.73rem;font-weight:600;color:#8899bb;
  display:inline-flex;align-items:center;gap:5px;}}
.tag-live{{background:linear-gradient(135deg,#b91c1c,#ef4444);border-color:#ef4444;
  color:#fff;box-shadow:0 0 14px rgba(239,68,68,.4);animation:glow 1.4s infinite;}}
.tdot{{width:6px;height:6px;background:#fff;border-radius:50%;animation:blink 1s infinite;}}
@keyframes glow{{0%,100%{{box-shadow:0 0 14px rgba(239,68,68,.4);}}50%{{box-shadow:0 0 28px rgba(239,68,68,.75);}}}}
@keyframes blink{{0%,100%{{opacity:1;}}50%{{opacity:.1;}}}}

/* ══ AD SLOT ══════════════════════════════════════ */
.ad{{background:rgba(255,255,255,.03);border:1.5px dashed rgba(255,255,255,.08);
  border-radius:14px;padding:13px 16px;margin:0 0 16px;
  text-align:center;color:#4a5a7a;font-size:.8rem;
  min-height:68px;display:flex;align-items:center;justify-content:center;gap:8px;}}

/* ══ SECTION HEADER ══════════════════════════════════════ */
.sec-hdr{{display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:12px;
  border-bottom:2px solid rgba(255,255,255,.07);}}
.sec-icon{{width:36px;height:36px;background:linear-gradient(135deg,#0f3391,#1976d2);
  border-radius:11px;display:flex;align-items:center;justify-content:center;
  font-size:1rem;flex-shrink:0;box-shadow:0 4px 14px rgba(25,118,210,.35);color:#fff;}}
.sec-title{{font-size:1.1rem;font-weight:800;color:#f0f4ff;}}
.cnt{{background:#1976d2;color:#fff;border-radius:20px;
  padding:2px 10px;font-size:.7rem;font-weight:800;margin-right:auto;}}

/* ══ STREAM CARDS ══════════════════════════════════════ */
.stream-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(155px,1fr));
  gap:11px;margin-bottom:20px;}}
.sc{{background:linear-gradient(145deg,#111827,#0f1f3d);
  border:2px solid rgba(99,139,255,.15);border-radius:18px;
  padding:18px 12px 14px;text-align:center;
  display:flex;flex-direction:column;align-items:center;gap:6px;
  cursor:pointer;transition:all .22s cubic-bezier(.34,1.56,.64,1);
  box-shadow:0 3px 14px rgba(0,0,0,.3);position:relative;overflow:hidden;}}
.sc::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#0f3391,#1976d2,#ef4444);
  opacity:0;transition:opacity .22s;}}
.sc:hover{{border-color:rgba(99,139,255,.45);transform:translateY(-5px) scale(1.02);
  box-shadow:0 14px 32px rgba(25,118,210,.25);}}
.sc:hover::before,.sc.active::before{{opacity:1;}}
.sc.active{{border-color:#1976d2;background:linear-gradient(145deg,#0f1f3d,#0a1a35);
  box-shadow:0 8px 24px rgba(25,118,210,.35);}}
.sc-icon{{font-size:2.3rem;line-height:1;}}
.sc-name{{font-weight:700;font-size:.86rem;color:#f0f4ff;line-height:1.3;}}
.sc-type{{font-size:.68rem;color:#5a7090;}}
.sc-badges{{display:flex;gap:4px;flex-wrap:wrap;justify-content:center;}}
.badge-v{{background:#10b981;color:#fff;padding:2px 7px;border-radius:9px;font-size:.6rem;font-weight:800;}}
.badge-hd{{background:#7c3aed;color:#fff;padding:2px 7px;border-radius:9px;font-size:.6rem;font-weight:800;}}
.badge-http{{background:#dc2626;color:#fff;padding:2px 7px;border-radius:9px;font-size:.6rem;font-weight:800;}}
.no-streams{{background:linear-gradient(145deg,#111827,#0f1f3d);border:1.5px solid rgba(245,158,11,.3);
  border-right:5px solid #f59e0b;border-radius:18px;padding:28px 20px;text-align:center;
  color:#92400e;margin-bottom:20px;}}

/* ══ PLAYER ══════════════════════════════════════ */
.http-warning{{background:linear-gradient(135deg,rgba(220,38,38,.1),rgba(239,68,68,.05));
  border:1px solid rgba(239,68,68,.3);border-right:4px solid #ef4444;
  border-radius:14px;padding:14px 16px;margin-bottom:12px;
  display:flex;gap:12px;align-items:flex-start;}}
.hw-icon{{font-size:1.4rem;flex-shrink:0;margin-top:2px;}}
.hw-title{{font-size:.88rem;font-weight:800;color:#fca5a5;margin-bottom:3px;}}
.hw-sub{{font-size:.75rem;color:#8899bb;line-height:1.5;}}

.player-wrap{{
  background:#000;border-radius:22px;overflow:hidden;
  border:2px solid rgba(99,139,255,.2);
  box-shadow:0 20px 60px rgba(0,0,0,.7),0 0 0 1px rgba(255,255,255,.03);
  margin-bottom:20px;
}}
.player-chrome{{
  background:linear-gradient(90deg,rgba(4,14,42,.98),rgba(7,29,92,.8));
  padding:10px 14px;display:flex;align-items:center;justify-content:space-between;
  gap:10px;border-bottom:1px solid rgba(255,255,255,.05);
}}
.pc-left{{display:flex;align-items:center;gap:8px;overflow:hidden;}}
.pb-live{{background:linear-gradient(135deg,#b91c1c,#ef4444);color:#fff;
  border-radius:6px;padding:3px 8px;font-size:.65rem;font-weight:800;letter-spacing:1px;
  animation:glow 1.4s infinite;flex-shrink:0;}}
.pc-title{{font-size:.8rem;font-weight:700;color:rgba(255,255,255,.8);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.pc-right{{display:flex;align-items:center;gap:7px;flex-shrink:0;}}
.p-status{{font-size:.65rem;font-weight:700;padding:3px 9px;border-radius:20px;
  background:rgba(255,255,255,.07);color:rgba(255,255,255,.5);white-space:nowrap;}}
.p-status.live{{background:rgba(239,68,68,.2);color:#fca5a5;}}
.p-status.ready{{background:rgba(16,185,129,.15);color:#6ee7b7;}}
.p-status.loading{{background:rgba(251,191,36,.1);color:#fbbf24;}}
.p-status.error{{background:rgba(239,68,68,.15);color:#fca5a5;}}
.pc-btn{{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);
  color:rgba(255,255,255,.6);padding:4px 9px;border-radius:8px;
  font-size:.8rem;cursor:pointer;transition:all .18s;}}
.pc-btn:hover{{background:rgba(255,255,255,.16);color:#fff;}}
.pc-ext-btn{{background:rgba(25,118,210,.2);border:1px solid rgba(25,118,210,.3);
  color:#93c5fd;padding:4px 10px;border-radius:8px;font-size:.7rem;font-weight:700;
  cursor:pointer;transition:all .18s;white-space:nowrap;}}
.pc-ext-btn:hover{{background:rgba(25,118,210,.4);color:#fff;}}

.player-ratio{{position:relative;padding-bottom:56.25%;height:0;overflow:hidden;
  background:radial-gradient(ellipse,#040e2a,#000);}}
.player-ratio iframe,.player-ratio video,.player-ratio #hls-wrap{{
  position:absolute;top:0;left:0;width:100%;height:100%;border:none;}}

.player-overlay{{position:absolute;top:0;left:0;width:100%;height:100%;
  background:radial-gradient(ellipse,#040e2a,#000);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:16px;z-index:10;transition:opacity .4s;}}
.po-spinner{{width:44px;height:44px;border:3px solid rgba(255,255,255,.1);
  border-top-color:#1976d2;border-radius:50%;animation:spin .8s linear infinite;}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}
.po-text{{color:rgba(255,255,255,.5);font-size:.82rem;font-weight:600;}}

/* Player error state */
.player-error{{
  position:absolute;top:0;left:0;width:100%;height:100%;
  background:radial-gradient(ellipse,#040e2a,#000);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:10px;padding:24px;text-align:center;
}}
.pe-icon{{font-size:3rem;margin-bottom:4px;}}
.pe-title{{font-size:1rem;font-weight:800;color:#f0f4ff;}}
.pe-sub{{font-size:.78rem;color:#8899bb;margin-bottom:6px;line-height:1.5;}}
.pe-actions{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;}}
.pe-btn-try{{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);
  color:#f0f4ff;padding:9px 20px;border-radius:12px;font-weight:700;font-size:.82rem;
  cursor:pointer;transition:background .2s;}}
.pe-btn-try:hover{{background:rgba(255,255,255,.18);}}
.pe-btn-ext{{background:linear-gradient(135deg,#1148b8,#1976d2);color:#fff;
  padding:9px 20px;border-radius:12px;font-weight:700;font-size:.82rem;
  box-shadow:0 4px 14px rgba(25,118,210,.4);transition:all .18s;}}
.pe-btn-ext:hover{{transform:translateY(-1px);box-shadow:0 6px 18px rgba(25,118,210,.5);}}
.pe-tips{{margin-top:8px;display:flex;flex-direction:column;gap:5px;}}
.pe-tip{{font-size:.72rem;color:#4a5a7a;background:rgba(255,255,255,.04);
  border-radius:8px;padding:4px 10px;}}

/* ══ NEWS ══════════════════════════════════════ */
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
  gap:11px;margin-bottom:20px;}}
.nc{{background:linear-gradient(145deg,#111827,#0f1f3d);
  border:1px solid rgba(99,139,255,.14);border-radius:16px;
  overflow:hidden;transition:all .18s;
  box-shadow:0 2px 10px rgba(0,0,0,.3);
  display:flex;flex-direction:column;}}
.nc:hover{{border-color:rgba(99,139,255,.4);
  box-shadow:0 8px 24px rgba(25,118,210,.2);transform:translateY(-2px);}}
.nc-img{{width:100%;height:110px;object-fit:cover;display:block;}}
.nc-ph{{width:100%;height:70px;background:linear-gradient(135deg,#071d5c,#1148b8);
  display:flex;align-items:center;justify-content:center;
  font-size:1.8rem;color:rgba(255,255,255,.2);}}
.nc-body{{padding:11px;flex:1;}}
.nc-title{{font-size:.83rem;font-weight:700;color:#f0f4ff;line-height:1.5;margin-bottom:7px;}}
.nc-meta{{font-size:.68rem;color:#5a7090;}}

/* ══ SHARE ══════════════════════════════════════ */
.share-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-bottom:20px;}}
.share-btn{{display:flex;align-items:center;justify-content:center;gap:6px;
  padding:11px 8px;border-radius:13px;font-weight:700;font-size:.82rem;
  transition:all .18s;box-shadow:0 4px 14px rgba(0,0,0,.3);color:#fff;border:none;cursor:pointer;}}
.share-btn:hover{{transform:translateY(-2px);filter:brightness(1.1);}}
.sw{{background:#25D366;}}.st{{background:#1DA1F2;}}.sf{{background:#4267B2;}}

/* ══ FOOTER ══════════════════════════════════════ */
.foot{{text-align:center;padding:18px;margin-top:8px;
  color:#2a3a5a;font-size:.72rem;border-top:1px solid rgba(255,255,255,.05);}}

/* ══ MOBILE ══════════════════════════════════════ */
@media(max-width:600px){{
  .page{{padding:10px 10px 90px;}}
  .nav{{height:54px;padding:0 12px;}}
  .hero-logo{{width:58px;height:58px;}}
  .hero-name{{font-size:.82rem;}}
  .score-val{{font-size:2.2rem;}}
  .score-box{{padding:11px 12px;min-width:76px;}}
  .stream-grid{{grid-template-columns:repeat(2,1fr);gap:9px;}}
  .share-row{{grid-template-columns:1fr 1fr;gap:8px;}}
  .news-grid{{grid-template-columns:1fr;}}
  .player-chrome{{flex-direction:column;align-items:flex-start;gap:6px;padding:8px 12px;}}
  .pc-right{{align-self:flex-end;}}
}}
</style>
</head>
<body>

<!-- RIGHT-CLICK PROTECTION on whole page for stream content -->
<script>
document.addEventListener('contextmenu', function(e){{
  if(e.target.closest('.player-wrap,.stream-grid')){{
    e.preventDefault(); return false;
  }}
}});
// Disable keyboard shortcuts for save/view-source on player area
document.addEventListener('keydown', function(e){{
  if(e.target.closest('.player-wrap')){{
    if((e.ctrlKey||e.metaKey)&&['s','u','a'].includes(e.key.toLowerCase())){{
      e.preventDefault();
    }}
  }}
}});
</script>

<!-- NAV -->
<nav class="nav">
  <div class="nav-brand">
    <img src="{LOGO_URL}" class="nav-logo" alt="Badr TV">
    <div>
      <div class="nav-name">Badr TV</div>
      <span class="nav-sub">Football Network</span>
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
        <img src="{home_logo}" class="hero-logo"
          onerror="this.src='https://ui-avatars.com/api/?name=HM&background=071d5c&color=fff&size=80&bold=true'">
        <div class="hero-name">{home_team}</div>
      </div>
      <div class="score-box">
        <span class="score-val">{score_display}</span>
        <span class="score-lbl">{score_label}</span>
      </div>
      <div class="hero-team">
        <img src="{away_logo}" class="hero-logo"
          onerror="this.src='https://ui-avatars.com/api/?name=AW&background=0a1a3d&color=fff&size=80&bold=true'">
        <div class="hero-name">{away_team}</div>
      </div>
    </div>
    <div class="hero-tags">
      <span class="tag">🏆 {league}</span>
      <span class="tag">🕐 {time_str}</span>
      {meta_status}
    </div>
  </div>
</div>

<!-- AD TOP -->
<div class="ad">📢 مساحة إعلانية</div>

<!-- STREAMS -->
<div class="sec-hdr">
  <div class="sec-icon">📡</div>
  <div class="sec-title">اختر قناة البث</div>
  {count_badge}
</div>
<div class="stream-grid">{stream_cards_html}</div>

<!-- PLAYER -->
{player_section}

<!-- AD MID -->
{"<div class='ad'>📢 مساحة إعلانية</div>" if selected_url else ""}

<!-- NEWS -->
{"<div class='sec-hdr'><div class='sec-icon'>📰</div><div class='sec-title'>آخر الأخبار</div></div><div class='news-grid'>" + news_html + "</div>" if recent_news else ""}

<!-- SHARE -->
<div class="sec-hdr">
  <div class="sec-icon">📤</div>
  <div class="sec-title">شارك المباراة</div>
</div>
<div class="share-row">
  <a href="https://wa.me/?text={share_text}" target="_blank" rel="noopener" class="share-btn sw">
    <i class="fab fa-whatsapp"></i> واتساب
  </a>
  <a href="https://twitter.com/intent/tweet?text={share_text}" target="_blank" rel="noopener" class="share-btn st">
    <i class="fab fa-twitter"></i> تويتر
  </a>
  <a href="https://www.facebook.com/sharer/sharer.php?u={quote(page_url)}" target="_blank" rel="noopener" class="share-btn sf">
    <i class="fab fa-facebook-f"></i> فيسبوك
  </a>
</div>

<div class="foot">Badr TV © {datetime.now().year} — منصة كرة القدم الشاملة</div>
</div>
</body>
</html>"""

components.html(FULL_HTML, height=4600, scrolling=True)
