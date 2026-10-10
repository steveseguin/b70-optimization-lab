#!/usr/bin/env python3
"""Fetch only structurally proven header ranges. No tensor payload or HF SDK."""
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import urllib.request

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
PARSER = LANE / 'stage1/packet1b/loaders/headers.py'
spec = importlib.util.spec_from_file_location('headers', PARSER)
headers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(headers)
CAP = 64_000_000  # stricter than 64 MiB; total returned body bytes per file
CHUNK = 1_048_576


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.urls = []

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        self.urls.append(newurl)
        return super().redirect_request(req, fp, code, msg, hdrs, newurl)


class RangeStream:
    def __init__(self, url, size):
        self.url, self.size = url, size
        self.pos = self.safe_end = 0
        self.data = bytearray()
        self.requests = []
        self.progress_path = None

    def guarantee_header(self, end):
        self.safe_end = max(self.safe_end, end)

    def read(self, n):
        wanted = self.pos + n
        # Parser requests themselves are structural, and hints are lower bounds
        # on remaining structure. Never round upward to a generic chunk size.
        self.guarantee_header(wanted)
        while len(self.data) < wanted:
            start = len(self.data)
            end = min(self.safe_end, start + CHUNK, CAP) - 1
            if end < start:
                raise ValueError('64 MB per-file hard cap')
            redirects = Redirects()
            opener = urllib.request.build_opener(redirects)
            # Distinct query avoids a proxy serving a cached different Range.
            url = self.url + f'?header_range={start}-{end}'
            req = urllib.request.Request(url, headers={
                'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity',
                'User-Agent': 'own-xpu-runtime-header-census/1'})
            with opener.open(req, timeout=60) as response:
                expected = f'bytes {start}-{end}/{self.size}'
                if response.status != 206 or response.headers.get('Content-Range') != expected:
                    raise ValueError('Range/size mismatch; body not read')
                if response.headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('encoded response rejected')
                if int(response.headers.get('Content-Length', -1)) != end-start+1:
                    raise ValueError('Content-Length mismatch; body not read')
                data = response.read(end-start+1)
                if len(data) != end-start+1:
                    raise ValueError('short range')
                self.requests.append(dict(url=url, redirects=redirects.urls,
                    final_url=response.url, range=f'bytes={start}-{end}',
                    content_range=expected, bytes_fetched=len(data), sha256=digest(data)))
            self.data.extend(data)
            if self.progress_path:
                self.progress_path.write_text(json.dumps(dict(url=self.url,
                    bytes_fetched=len(self.data), sha256=digest(self.data),
                    requests=self.requests), indent=2)+'\n')
                self.progress_path.with_suffix('.header.gz').write_bytes(gzip.compress(self.data, mtime=0))
        result = bytes(self.data[self.pos:wanted])
        self.pos = wanted
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true', required=True)
    ap.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        raise SystemExit('Run at nice 19 with OMP_NUM_THREADS=2')
    allow = json.loads((LANE / 'data/unsloth-flash-next-stage2-files.json').read_text())
    # Refresh publisher metadata, never download a weight through the API.
    with urllib.request.urlopen(allow['api_url'], timeout=60) as r:
        raw = r.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError('metadata response cap')
    hf = json.loads(raw)
    assert hf['sha'] == allow['revision']
    siblings = {s['rfilename']: s for s in hf['siblings']}
    out = HERE / 'headers'
    out.mkdir(exist_ok=True)
    (HERE / 'hf-metadata.json.gz').write_bytes(gzip.compress(raw, mtime=0))
    receipt_path = HERE / 'fetch-receipt.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else dict(schema='own-xpu-runtime.stage2.packet1c.fetch-receipt.v1',
        retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        repository=allow['repo'], revision=allow['revision'],
        api=dict(url=allow['api_url'], bytes_fetched=len(raw), sha256=digest(raw)),
        per_file_cap_bytes=CAP, chunk_cap_bytes=CHUNK, tensor_data_bytes_fetched=0,
        source_parser_sha256=digest(PARSER.read_bytes()), files=[])
    receipt.setdefault('api_requests', []).append(dict(url=allow['api_url'],
        bytes_fetched=len(raw),sha256=digest(raw)))
    receipt['api'] = dict(url=allow['api_url'],bytes_fetched=len(raw),sha256=digest(raw))
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    selected = [f for f in allow['files'] if not f['path'].startswith('UD-Q4_K_XL/')]
    for f in selected:
        if any(x['path'] == f['path'] for x in receipt['files']):
            continue
        s = siblings[f['path']]
        assert s['size'] == s['lfs']['size'] == f['bytes']
        assert s['lfs']['sha256'] == f['sha256']
        url = f"https://huggingface.co/{allow['repo']}/resolve/{allow['revision']}/{f['path']}"
        stream = RangeStream(url, f['bytes'])
        stream.progress_path = HERE / 'fetch-progress.json'
        if stream.progress_path.exists():
            progress = json.loads(stream.progress_path.read_text())
            assert progress['url'] == url
            stream.data = bytearray(gzip.decompress(stream.progress_path.with_suffix('.header.gz').read_bytes()))
            assert len(stream.data) == progress['bytes_fetched']
            assert digest(stream.data) == progress['sha256']
            stream.requests = progress['requests']
        print('Reading', f['path'], flush=True)
        parsed = headers.gguf_header(stream, f['bytes'])
        assert len(stream.data) == parsed['header_bytes_read'] <= parsed['data_start']
        name = f['path'].replace('/', '__') + '.header.gz'
        (out / name).write_bytes(gzip.compress(stream.data, mtime=0))
        entry = dict(path=f['path'], url=url, hf_file_bytes=f['bytes'],
            hf_lfs_sha256=f['sha256'], payload_hash_verified=False,
            size_verified_against='fresh HF size + LFS size + every Content-Range total',
            header_path='headers/'+name, header_bytes_fetched=len(stream.data),
            header_sha256=digest(stream.data), data_start=parsed['data_start'],
            tensors=len(parsed['tensors']), requests=stream.requests)
        receipt['files'].append(entry)
        receipt['header_bytes_fetched'] = sum(x['header_bytes_fetched'] for x in receipt['files'])
        (HERE / 'fetch-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        print('Complete:', len(stream.data), 'header bytes,', len(stream.requests), 'ranges,', len(parsed['tensors']), 'tensors', flush=True)
        stream.progress_path.unlink()
        stream.progress_path.with_suffix('.header.gz').unlink()


if __name__ == '__main__':
    main()
