#!/usr/bin/env python3
"""A tiny fake of the packet 97 ComfyUI server, for testing ltx_stream_driver.py's Phase B.

    python3 -B fake_comfy.py --root ROOT --run-name RUN --port 18188 --clip SRC.mp4 [--delay 0.05]

Serves POST /prompt, GET /queue, GET /history/<id> and executes prompts one at a time, mimicking
the receipts and pipeline semantics of the real batch-2 timed arm:
- sampler: batch grouper (consecutive clips only, an index is never reused, stream_last closes a
  group; a violation is an execution error that LATCHES the fake, like the real sampler);
  prompt with clip i emits sampler clip i - Ds if its job exists, else a fill;
- decode: run_behind with depth Dd (a prompt with no predecessor primes);
- save: the MP4 of clip k goes to output/<name of the prompt that released k>/preview_00001_.mp4,
  written a little later by a writer thread, then pipeline-done-save-<k>.json;
- per prompt: pipeline-sampler/-decode/-save receipts and output/validation/<name>/summary.json
  (fake sha256s derived from the clip's own prompt text and seed).
Writes server-identity.json / server-args.json in the run dir and model-verification.json in ROOT.
Records test evidence in ROOT/fake-stats.json (max prompts in the server, history polls that were
not for the oldest uncompleted prompt).
Injection: --error-at-index N (execution error), --failed-receipt-at-index N (pipeline-failed receipt).
"""
import argparse, hashlib, json, os, shutil, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True, type=Path)
ap.add_argument('--run-name', required=True)
ap.add_argument('--port', type=int, default=18188)
ap.add_argument('--clip', required=True)
ap.add_argument('--delay', type=float, default=0.05, help='seconds per prompt execution')
ap.add_argument('--save-delay', type=float, default=0.02)
ap.add_argument('--error-at-index', type=int)
ap.add_argument('--failed-receipt-at-index', type=int)
a = ap.parse_args()

ROOT = a.root
RUN = ROOT / a.run_name
OUT = ROOT / 'output'
for d in (RUN, OUT / 'validation', ROOT / 'requests'):
    d.mkdir(parents=True, exist_ok=True)
(ROOT / 'model-verification.json').write_text(json.dumps({'status': 'passed'}) + '\n')
ticks = Path('/proc/self/stat').read_text().split(') ')[1].split()[19]
(RUN / 'server-identity.json').write_text(json.dumps({
    'pid': os.getpid(), 'proc_start_ticks': ticks,
    'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    'source_packet_manifest_sha256': 'fake', 'start_utc': time.ctime()}, indent=2) + '\n')
(RUN / 'server-args.json').write_text(json.dumps(['fake', '--port', str(a.port), '--output-directory', str(OUT)]) + '\n')

LOCK = threading.Lock()
COND = threading.Condition(LOCK)
QUEUE = []          # [number, prompt_id, graph, extra, outputs]
RUNNING = []
HISTORY = {}
ORDER = []          # prompt ids in submission order
ACKED = set()       # prompt ids whose completed history was served
STATS = {'max_in_server': 0, 'history_gets': 0, 'non_oldest_polls': 0, 'executed': 0, 'emitted': 0,
         'latched': None, 'stream_last_prompts': 0}
NUMBER = [0]
G = {'open': [], 'used': set(), 'clip_job': {}, 'jobs': {}, 'decode': {}, 'latched': None}


def sha(*parts):
    return hashlib.sha256('|'.join(str(p) for p in parts).encode()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1) + '\n')


def summary(name, text, seed):
    d = OUT / 'validation' / name
    d.mkdir(parents=True, exist_ok=True)
    tensors = {k: {'sha256': sha(text, seed, k), 'finite': True} for k in ('images', 'video_latent', 'audio_latent', 'waveform')}
    write(d / 'summary.json', {'run_name': name, 'tensors': tensors})
    (d / 'tensors.safetensors').write_bytes(b'x' * 1024)


def writer(prefix, k):
    time.sleep(a.save_delay)
    folder = OUT / prefix.split('/')[0]
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.clip, folder / 'preview_00001_.mp4')
    rel = prefix.split('/')[0] + '/preview_00001_.mp4'
    write(RUN / ('pipeline-done-save-%d.json' % k), {'stage': 'save', 'index': k, 'saved': rel,
                                                    'finished_unix': time.time()})


def execute(graph):
    s, d = graph['428']['inputs'], graph['426']['inputs']
    name, idx, last = s['run_name'], s['clip_index'], s.get('stream_last', 0)
    ds, dd, batch = s['depth'], d['depth'], s['batch']
    text, seed = graph['364']['inputs']['text'], graph['339']['inputs']['noise_seed']
    if G['latched']:
        raise RuntimeError('Previous pipeline failure; halt submissions and inspect evidence')
    if a.error_at_index is not None and idx == a.error_at_index:
        raise RuntimeError('injected execution error at clip %d' % idx)
    if a.failed_receipt_at_index is not None and idx == a.failed_receipt_at_index:
        write(RUN / ('pipeline-failed-sample-%d-%d.json' % (idx, int(time.time() * 1000))),
              {'stage': 'sample', 'index': idx, 'worker': 'ltx-sample-0', 'exception_type': 'RuntimeError',
               'exception_message': 'injected', 'traceback': 'Traceback\n  injected'})
    # grouper
    try:
        if idx in G['used']:
            raise RuntimeError('clip %d was already deposited on this server (stale index)' % idx)
        if G['open'] and idx != G['open'][-1] + 1:
            raise RuntimeError('clip %d does not follow the open group %s' % (idx, G['open']))
    except RuntimeError as e:
        G['latched'] = str(e)
        STATS['latched'] = str(e)
        raise
    G['open'].append(idx)
    G['used'].add(idx)
    G['clips_info'] = G.get('clips_info', {})
    G['clips_info'][idx] = (text, seed, name)
    if last:
        STATS['stream_last_prompts'] += 1
    if len(G['open']) >= batch or last:
        key = G['open'][0]
        for c in G['open']:
            G['clip_job'][c] = key
        G['open'] = []
    emit_s = idx - ds
    if emit_s >= 0 and emit_s in G['clip_job']:
        del G['clip_job'][emit_s]
    else:
        emit_s = -1
    write(RUN / ('pipeline-sampler-%s.json' % name), {'run_name': name, 'detail': {'emitted_index': emit_s}})
    emitted = -1
    if emit_s >= 0:
        if emit_s in G['decode']:
            raise RuntimeError('decode job already exists for clip %d' % emit_s)
        G['decode'][emit_s] = name + '/preview'
        e = emit_s - dd
        if e in G['decode']:
            emitted = e
    detail = {'emitted_index': emitted}
    if emitted >= 0:
        prefix = G['decode'].pop(emitted)
        detail['decode_split'] = {'decode_s': 0.4, 'device': 'xpu:2', 'slot': 'replica'}
        t, sd, _n = G['clips_info'].pop(emitted)
        summary(name, t, sd)
        threading.Thread(target=writer, args=(prefix, emitted), daemon=True).start()
        write(RUN / ('pipeline-save-%s.json' % name), {'prefix': prefix, 'run_name': name,
                                                      'status': 'queued-to-writer', 'saved_file': None})
        STATS['emitted'] += 1
    else:
        summary(name, 'fill', 0)
    write(RUN / ('pipeline-decode-%s.json' % name), {'run_name': name, 'detail': detail})


def executor():
    while True:
        with COND:
            while not QUEUE:
                COND.wait()
            item = QUEUE.pop(0)
            RUNNING.append(item)
        t0 = time.time()
        time.sleep(a.delay)
        msgs = [['execution_start', {'prompt_id': item[1], 'timestamp': int(t0 * 1000)}]]
        try:
            execute(item[2])
            msgs.append(['execution_cached', {'nodes': [], 'prompt_id': item[1], 'timestamp': int(time.time() * 1000)}])
            msgs.append(['execution_success', {'prompt_id': item[1], 'timestamp': int(time.time() * 1000)}])
            status = {'status_str': 'success', 'completed': True, 'messages': msgs}
        except Exception as e:  # noqa: BLE001
            msgs.append(['execution_error', {'prompt_id': item[1], 'exception_type': type(e).__name__,
                                             'exception_message': str(e), 'node_type': 'LTXPipelineSampler'}])
            status = {'status_str': 'error', 'completed': False, 'messages': msgs}
        with COND:
            RUNNING.remove(item)
            HISTORY[item[1]] = {'prompt': item, 'outputs': {}, 'status': status, 'meta': {}}
            STATS['executed'] += 1
            write(ROOT / 'fake-stats.json', STATS)


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/queue':
            with LOCK:
                return self.reply(200, {'queue_running': list(RUNNING), 'queue_pending': list(QUEUE)})
        if self.path.startswith('/history/'):
            pid = self.path[len('/history/'):]
            with LOCK:
                STATS['history_gets'] += 1
                oldest = next((p for p in ORDER if p not in ACKED), None)
                if pid != oldest:
                    STATS['non_oldest_polls'] += 1
                h = HISTORY.get(pid)
                if h and h['status'].get('completed'):
                    ACKED.add(pid)
                return self.reply(200, {pid: h} if h else {})
        self.reply(404, {})

    def do_POST(self):
        if self.path != '/prompt':
            return self.reply(404, {})
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        g = body['prompt']
        if g['428']['inputs']['clip_index'] > 100000000:
            return self.reply(400, {'error': 'value_bigger_than_max', 'node_errors': {'428': 'clip_index'}})
        with COND:
            pid = str(uuid.uuid4())
            NUMBER[0] += 1
            QUEUE.append([NUMBER[0], pid, g, {'client_id': body.get('client_id')}, ['414', '430']])
            ORDER.append(pid)
            STATS['max_in_server'] = max(STATS['max_in_server'], len(QUEUE) + len(RUNNING))
            COND.notify_all()
        self.reply(200, {'prompt_id': pid, 'number': NUMBER[0], 'node_errors': {}})


threading.Thread(target=executor, daemon=True).start()
srv = ThreadingHTTPServer(('127.0.0.1', a.port), H)
print('fake comfy on 127.0.0.1:%d, run dir %s' % (a.port, RUN), flush=True)
try:
    srv.serve_forever()
except KeyboardInterrupt:
    pass
