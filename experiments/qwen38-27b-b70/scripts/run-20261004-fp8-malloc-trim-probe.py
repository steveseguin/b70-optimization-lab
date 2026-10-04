#!/usr/bin/env python3
"""Host-memory probe (2026-10-04): can a loaded two-card FP8 server give its free heap back without changing anything?

One research server on the shipped depth-5 recipe plus the `b70-malloc-trim` overlay. Order: strict (exact + speed),
memory snapshot, trigger `malloc_trim(0)` in every vLLM process, snapshot, strict again (exact + speed, and whether the
heap grows straight back), snapshot, graceful stop. No server before, none after. A measurement, not a campaign:
the question is how many GiB come back and whether exactness and speed are untouched.
"""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

OUT = Path(os.environ.get('CAMPAIGN_OUT', '/mnt/fast-ai/bench-results/fp8-malloc-trim-20261004'))
os.environ['CAMPAIGN_OUT'] = str(OUT)
ROOT = Path('/home/steve/b70-optimization-lab')
spec = importlib.util.spec_from_file_location('review', ROOT / 'experiments/qwen38-27b-b70/scripts/run-20260916-fp8-review-campaign.py')
review = importlib.util.module_from_spec(spec); spec.loader.exec_module(review)
R = review
R.SERVICE_STATE = Path('/nonexistent/no-resident-service')
REF_STRICT = Path('/mnt/fast-ai/bench-results/fp8-comm2-20260917/tp2-ag-mtp0-strict')
ARGS = ['--tp', '2', '--mem', '0.95', '--max-model-len', str(R.TP2_MML), '--batched', '4096', '--fa-verify-rows',
        '--mtp', '5', '--draft-int4', '--shortlist', R.SHORTLIST,
        '--overlay', 'b70-allgather-allreduce', '--extra-env', 'B70_ALLGATHER_ALLREDUCE=1',
        '--overlay', 'b70-malloc-trim', '--extra-env', 'B70_MALLOC_TRIM=1', '--extra-env', 'B70_MALLOC_TRIM_DIR=/b70trim']


def snapshot(label):
    cid = subprocess.run(['docker', 'ps', '-q', '--no-trunc'], capture_output=True, text=True).stdout.split()
    snap = {'label': label, 'at': R.now()}
    for line in open('/proc/meminfo'):
        key, value = line.split(':')
        if key in ('MemAvailable', 'AnonPages', 'Cached'):
            snap[f'host_{key}_kb'] = int(value.split()[0])
    if cid:
        stat = Path(f'/sys/fs/cgroup/system.slice/docker-{cid[0]}.scope/memory.stat')
        if stat.exists():
            for line in stat.read_text().splitlines():
                key, value = line.split()
                if key in ('anon', 'file', 'kernel'):
                    snap[f'container_{key}_bytes'] = int(value)
    R.log(f"snapshot {label}: host available {snap.get('host_MemAvailable_kb', 0) / 2**20:.2f} GiB, "
          f"container anon {snap.get('container_anon_bytes', 0) / 2**30:.2f} GiB")
    return snap


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    trim_dir = OUT / 'trim'; trim_dir.mkdir()
    os.chmod(trim_dir, 0o777)
    since = R.now()
    R.log(f'malloc-trim probe start; git {subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()}')
    results = R.RESULTS
    results['started'] = since
    results['preflight_health_rc'] = R.health('preflight-health')
    R.save_results()
    if results['preflight_health_rc'] != 0:
        raise SystemExit(4)
    R.fault_check(since)
    srv = R.Research('tp2-trim', 18195, ARGS + ['--mount-dir', f'{trim_dir}:/b70trim'])
    r = results['tp2-trim'] = {'server': {k: srv.state.get(k) for k in ('status', 'error', 'ready_at')}, 'snapshots': []}
    if srv.ready:
        if os.environ.get('TRIM_PROBE_CENSUS_ONLY') == '1':
            (trim_dir / 'census').write_text('1')
            time.sleep(40)
            r['census'] = [json.loads(p.read_text()) for p in sorted(trim_dir.glob('*-census.json'))]
            for rec in r['census']:
                R.log(f"census pid {rec['pid']} {rec.get('comm', '')}: RssAnon {rec['rss_anon_kb'] / 2**20:.2f} GiB, "
                      f"{rec.get('cpu_tensor_storages')} CPU tensor storages = {rec.get('cpu_tensor_bytes', 0) / 2**30:.2f} GiB")
            r['stop'] = srv.stop()
            R.save_results(); R.fault_check(since); R.wait_gpus_free()
            results['finished'] = R.now(); R.save_results()
            R.log('=== census probe complete ===')
            return
        r['strict_before'] = R.strict(srv.base, 'tp2-trim-before', REF_STRICT)
        R.save_results(); R.fault_check(since)
        r['snapshots'].append(snapshot('loaded, after strict 1'))
        (trim_dir / 'now').write_text('1')
        time.sleep(15)
        records = [json.loads(p.read_text()) for p in sorted(trim_dir.glob('*.json'))]
        r['trim_records'] = records
        for rec in records:
            R.log(f"trim pid {rec['pid']} {rec.get('comm', '')}: {rec['rss_anon_kb_before'] / 2**20:.2f} -> "
                  f"{rec['rss_anon_kb_after'] / 2**20:.2f} GiB in {rec['seconds']} s")
        r['snapshots'].append(snapshot('after trim'))
        R.save_results(); R.fault_check(since)
        r['strict_after'] = R.strict(srv.base, 'tp2-trim-after', REF_STRICT)
        R.save_results(); R.fault_check(since)
        r['snapshots'].append(snapshot('after strict 2'))
        R.log(f"strict before {r['strict_before'].get('exact')} at {r['strict_before'].get('tok_s_1_100')}, "
              f"after {r['strict_after'].get('exact')} at {r['strict_after'].get('tok_s_1_100')}")
    r['stop'] = srv.stop()
    R.save_results(); R.fault_check(since); R.wait_gpus_free()
    results['finished'] = R.now()
    R.save_results()
    R.log('=== malloc-trim probe complete ===')


if __name__ == '__main__':
    main()
