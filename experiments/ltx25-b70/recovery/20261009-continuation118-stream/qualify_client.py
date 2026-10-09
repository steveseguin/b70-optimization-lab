#!/usr/bin/env python3
"""Packet118 qualification driver: 2 setup + 9 qualification requests, then the verdict.

Packet118: the status must also show the launch's snapshot mode (--snapshot-mode) and decoder-graph pool cap
(--pool-cap-gb, omitted = none); neither is a request field, so the request sequence is packet 117's form.

One attempt per request, bounded waits, stdlib HTTP only. It never starts,
stops, signals or retries a server; any refusal, halt or timeout ends the run
and leaves the server latched for inspection. `--dry-run` prints the exact
request sequence (graph SHA-256s) without any network access.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_contract as contract  # noqa: E402

BASE_URL = 'http://127.0.0.1:8188'
SETUP_TIMEOUT_S = 1800      # the window probe captured text graphs in 326 s on packet 111
CHUNK_TIMEOUT_S = 900
VERDICT_TIMEOUT_S = 900       # includes the bounded decode and preview drains (300 s + 120 s)
POLL_S = 1.0


def requests_in_order(frames, text_reuse, placement, anchor, decoder_graph=contract.DEFAULT_DECODER_GRAPH,
                      anchor_decode=None, bencode_overlap=None, prep_ahead=None):
    rows = [(r['name'], r['graph']) for r in contract.setup_graphs()]
    for params in contract.qualification_params(frames, text_reuse, placement, anchor, decoder_graph,
                                                anchor_decode, bencode_overlap, prep_ahead):
        rows.append((contract.run_name(params), contract.build_chunk_graph(params)))
    return rows


def http(method, path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE_URL + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b'null')
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b'null')


def wait_completed(name, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, value = http('GET', '/ltx-stream/status')
        if status == 200:
            if value.get('halted'):
                raise SystemExit('Server halted during %s: %s' % (name, value['halted']))
            if name in value.get('completed_fixed_requests', []):
                return value
        elif status != 409:
            raise SystemExit('Status route failed (%s): %s' % (status, value))
        time.sleep(POLL_S)
    raise SystemExit('Timed out waiting for %s; no retry. Inspect the server run directory.' % name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text-reuse', type=int, choices=(0, 1), required=True,
                        help='must equal the server LTX_STREAM_TEXT_REUSE')
    parser.add_argument('--frames', type=int, choices=contract.FRAME_CHOICES, required=True,
                        help='must equal the server LTX_STREAM_FRAMES')
    parser.add_argument('--anchor', choices=contract.ANCHORS, required=True,
                        help='must equal the server LTX_ANCHOR')
    parser.add_argument('--placement', choices=sorted(contract.PLACEMENTS), required=True,
                        help='must equal the server LTX_SAMPLER_PLACEMENT')
    parser.add_argument('--decoder-graph', type=int, choices=contract.DECODER_GRAPH_CHOICES, required=True,
                        help='must equal the server LTX_DECODER_GRAPH (packet116)')
    parser.add_argument('--anchor-decode', choices=contract.ANCHOR_DECODE_CHOICES, required=True,
                        help='must equal the server LTX_ANCHOR_DECODE (packet117)')
    parser.add_argument('--bencode-overlap', type=int, choices=contract.BENCODE_OVERLAP_CHOICES, required=True,
                        help='must equal the server LTX_BENCODE_OVERLAP (packet117)')
    parser.add_argument('--prep-ahead', type=int, choices=contract.PREP_AHEAD_CHOICES, required=True,
                        help='must equal the server LTX_PREP_AHEAD (packet117)')
    parser.add_argument('--snapshot-mode', choices=contract.SNAPSHOT_MODES, required=True,
                        help='must equal the server LTX_SNAPSHOT_MODE (packet118)')
    parser.add_argument('--pool-cap-gb', default=None,
                        help='must equal the server LTX_DECODER_GRAPH_POOL_CAP_GB (packet118; omit when unset)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--log', type=Path, help='append-only JSON-lines log (created exclusively)')
    args = parser.parse_args()
    contract.check_levers(args.anchor, args.anchor_decode, args.bencode_overlap, args.prep_ahead)
    pool_cap = contract.parse_pool_cap(args.pool_cap_gb)
    rows = requests_in_order(args.frames, args.text_reuse, args.placement, args.anchor, args.decoder_graph,
                             args.anchor_decode, args.bencode_overlap, args.prep_ahead)
    if args.dry_run:
        for name, graph in rows:
            print(name, contract.sha256(contract.canonical(graph)))
        print('action:qualify-verdict')
        return
    log = args.log.open('x') if args.log else None
    client_id = contract.RUN_PREFIX + '-qualify-' + uuid.uuid4().hex[:12]
    status, value = http('GET', '/ltx-stream/status')
    if status != 200 or value.get('phase') != 'stream_setup' or value.get('text_reuse') != args.text_reuse \
            or value.get('frames') != args.frames or value.get('placement') != args.placement \
            or value.get('anchor') != args.anchor or value.get('packet') != contract.PACKET \
            or value.get('decoder_graph') != args.decoder_graph \
            or value.get('anchor_decode') != args.anchor_decode or value.get('bencode_overlap') != args.bencode_overlap \
            or value.get('prep_ahead') != args.prep_ahead \
            or value.get('snapshot_mode') != args.snapshot_mode \
            or value.get('decoder_graph_pool_cap_bytes') != pool_cap \
            or value.get('completed_fixed_requests'):
        raise SystemExit('Server is not a fresh packet118 setup phase with matching frames/anchor/decoder_graph/'
                         'levers/snapshot mode/pool cap/text_reuse: %s'
                         % value)
    for name, graph in rows:
        prompt_id = str(uuid.uuid4())
        started = time.time()
        status, value = http('POST', '/prompt', {'prompt': graph, 'client_id': client_id, 'prompt_id': prompt_id})
        if status != 200:
            raise SystemExit('Refused %s (%s): %s' % (name, status, value))
        done = wait_completed(name, SETUP_TIMEOUT_S if name.endswith(('window-probe', 'prepare')) else CHUNK_TIMEOUT_S)
        row = {'name': name, 'prompt_id': prompt_id, 'wall_s': round(time.time() - started, 3), 'phase': done['phase']}
        print(json.dumps(row), flush=True)
        if log:
            log.write(json.dumps(row) + '\n')
            log.flush()
    status, value = http('POST', '/ltx-stream/action', {'action': 'qualify-verdict'}, timeout=VERDICT_TIMEOUT_S)
    print(json.dumps({'verdict_http_status': status, 'verdict': value}), flush=True)
    if log:
        log.write(json.dumps({'verdict_http_status': status, 'verdict': value}) + '\n')
        log.close()
    if status != 200 or value.get('passed') is not True:
        raise SystemExit('Qualification did not pass; the server refuses streaming.')


if __name__ == '__main__':
    main()
