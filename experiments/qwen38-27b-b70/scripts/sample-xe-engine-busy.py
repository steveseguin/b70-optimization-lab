"""Samples each card's compute/copy-engine busy cycles (xe fdinfo, summed over GPU clients) and the server's token
counters every 0.25 s; one JSON line per sample. Read-only; ends after --minutes or when --stop exists."""
import argparse, json, os, re, time, urllib.request
ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--port', type=int, default=18196)
ap.add_argument('--minutes', type=float, default=100); ap.add_argument('--stop', required=True); a = ap.parse_args()
KEYS = ('drm-pdev', 'drm-cycles-ccs', 'drm-total-cycles-ccs', 'drm-cycles-bcs')
def clients():
    out = []
    for pid in os.listdir('/proc'):
        if not pid.isdigit(): continue
        try:
            for fd in os.listdir(f'/proc/{pid}/fd'):
                try:
                    if 'renderD' in os.readlink(f'/proc/{pid}/fd/{fd}'): out.append((pid, fd))
                except OSError: pass
        except OSError: pass
    return out
def metrics():
    try:
        txt = urllib.request.urlopen(f'http://127.0.0.1:{a.port}/metrics', timeout=0.2).read().decode()
    except Exception:
        return None, None
    g = p = None
    for line in txt.splitlines():
        if line.startswith('vllm:generation_tokens_total'): g = float(line.split()[-1])
        elif line.startswith('vllm:prompt_tokens_total'): p = float(line.split()[-1])
    return g, p
end = time.time() + a.minutes * 60; cl, refreshed = [], 0
with open(a.out, 'a') as f:
    while time.time() < end and not os.path.exists(a.stop):
        t = time.time()
        if t - refreshed > 5: cl, refreshed = clients(), t
        cards = {}
        for pid, fd in cl:
            try: info = open(f'/proc/{pid}/fdinfo/{fd}').read()
            except OSError: continue
            d = dict(re.findall(r'^(drm-[a-z0-9-]+):\s+(\S+)', info, re.M))
            if d.get('drm-driver') != 'xe' or 'drm-pdev' not in d: continue
            c = cards.setdefault(d['drm-pdev'], [0, 0, 0])
            c[0] += int(d.get('drm-cycles-ccs', 0)); c[1] = max(c[1], int(d.get('drm-total-cycles-ccs', 0))); c[2] += int(d.get('drm-cycles-bcs', 0))
        g, p = metrics()
        f.write(json.dumps({'t': round(t, 3), 'cards': cards, 'gen': g, 'prompt': p, 'n': len(cl)}) + '\n'); f.flush()
        time.sleep(max(0, 0.25 - (time.time() - t)))
