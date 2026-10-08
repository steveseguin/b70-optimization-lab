#!/usr/bin/env python3
"""Tiny multi-client MJPEG preview server: serves the latest JPEG written by ffmpeg (-update 1) at /stream.mjpg,
a single frame at /frame.jpg, sink stats at /stats.json, and an HTML page at /. Stdlib only, LAN preview only."""
import http.server, json, os, socketserver, sys, time, threading
FRAME = sys.argv[1] if len(sys.argv) > 1 else '/dev/shm/ltx-live/frame.jpg'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8090
STATS = '/home/steve/ltx-stream/s97-stream01/sink-stats.json'
PAGE = b"""<!doctype html><html><head><meta charset="utf-8"><title>LTX live preview</title>
<style>body{background:#111;color:#ddd;font:14px system-ui;margin:0;display:flex;flex-direction:column;align-items:center}
img{max-width:100vw;max-height:88vh;image-rendering:auto}pre{color:#9c9;font-size:12px;margin:6px}</style></head>
<body><img src="/stream.mjpg" alt="live"><pre id="s">loading stats...</pre>
<script>async function t(){try{const r=await fetch('/stats.json');const j=await r.json();
document.getElementById('s').textContent='played '+j.played_clips+' clips | lag '+j.current_lag_seconds+' s | buffered '+j.buffered_seconds+' s | holds '+j.holds+' | encoder restarts '+j.ffmpeg_restarts+' | '+j.updated_utc;}catch(e){}}
setInterval(t,2000);t();</script></body></html>"""
def read_frame():
    try:
        with open(FRAME, 'rb') as f: return f.read(), os.fstat(f.fileno()).st_mtime_ns
    except OSError: return None, None
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path in ('/', '/index.html'):
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.send_header('Content-Length', str(len(PAGE))); self.end_headers(); self.wfile.write(PAGE); return
        if self.path.startswith('/stats.json'):
            try: body = open(STATS, 'rb').read()
            except OSError: body = b'{}'
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body); return
        if self.path.startswith('/frame.jpg'):
            data, _ = read_frame()
            if not data: self.send_error(503, 'no frame yet'); return
            self.send_response(200); self.send_header('Content-Type', 'image/jpeg'); self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data); return
        if self.path.startswith('/stream.mjpg'):
            self.send_response(200); self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame'); self.send_header('Cache-Control', 'no-store'); self.end_headers()
            last = None
            try:
                while True:
                    data, m = read_frame()
                    if data and m != last and data[:2] == b'\xff\xd8' and data[-2:] == b'\xff\xd9':
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(data)).encode() + b'\r\n\r\n' + data + b'\r\n'); self.wfile.flush(); last = m
                    time.sleep(1/48)
            except (BrokenPipeError, ConnectionResetError): return
        self.send_error(404)
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True; allow_reuse_address = True
if __name__ == '__main__':
    print(f'MJPEG preview on 0.0.0.0:{PORT} from {FRAME}', flush=True); S(('0.0.0.0', PORT), H).serve_forever()
