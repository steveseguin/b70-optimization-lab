"""Verify every CPU gate and current seal; READY is the final file mutation."""
import argparse,json,subprocess,time
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
ap=argparse.ArgumentParser();ap.add_argument('--ready',action='store_true');args=ap.parse_args();limits()
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='main'
read=lambda f:json.loads(f.read_text())
root_checks={}
for leaf in ('packet163-replay.json',):
    f=P/'evidence'/leaf;assert read(f)['passed'];root_checks[str(f.relative_to(P))]=sha(f)
ready=[]
for name,lanes in [('one-card','A')]:
    p=P/name;checks={}
    for leaf in ('portable-inputs.json','build.json','identity-check.json','delta-check.json','analyzer-tests.json','report512-test.json',
                 'real-arm-sequence.json','native-sequence.json','preparation-probe.json','device-path-imports.json','flags.json'):
        f=p/'evidence'/leaf;r=read(f);assert r['passed'] and r['device_executed'] is False,(name,leaf)
        checks[str(f.relative_to(p))]=sha(f)
    build=read(p/'evidence/build.json')
    assert build['reused_object_files'] is False and build['arithmetic_qualified'] is False
    assert build['historical_binary_sha256']=='1364bb3de0e0742ea3c5419a3f6850cea3646466c19732ad5cf3fe9be2b1b7cf'
    native=read(p/'evidence/native-sequence.json')
    assert native['target_resets_per_native_owner']==14 and native['sensor_streams_per_reset']==4
    assert native['peak_child_rss_bytes']<4*1024**3
    assert len(native['results'])==1
    for result in native['results']:
        assert result['returncode']==0 and len(result['sensor_checks'])==56
    for lane in lanes:
        stem='one-'+lane
        report=P/'evidence'/f'rehearse-{stem}.json';r=read(report)
        assert r['passed'] and len(r['jobs'])==2
        assert all(j['passed'] and j['report']['passed'] and not j['service_started'] for j in r['jobs'])
        checks[str(report.relative_to(ROOT))]=sha(report)
        log=P/'evidence'/f'plan-{stem}.log'
        rows=[json.loads(line) for line in log.read_text().splitlines() if line.startswith('{')]
        assert len(rows)==2 and all(r['plan']=='passed' for r in rows)
        checks[str(log.relative_to(ROOT))]=sha(log)
        for attempt in ('a','b'):assert not (p/'evidence'/f'device-p178-full512-{lane}-{attempt}').exists()
    seal=read(p/'seal.json')
    for leaf,h in seal['files'].items():assert sha(p/leaf)==h,(name,leaf)
    identity=read(p/'identity.json');assert sha(p/'build/device/own-rt-iq3')==identity['binary_sha256']
    assert identity['native_arithmetic_unchanged_from_packet163'] and not identity['native_binary_unchanged_from_packet163']
    for rel,h in read(p/'inherited-native.json')['embedded_readonly_dependencies'].items():
        assert (ROOT/rel).is_relative_to(p) and sha(ROOT/rel)==h
    budget=read(p/'budget.json');assert budget['device_floor_bytes']==25_000_000_000 and budget['cpu_stop_bytes']==27_000_000_000
    checks['seal.json']=sha(p/'seal.json')
    proposal=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'/f'proposed-p178-{name}-A.txt'
    ready.append((p,dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
        seal_sha256=sha(p/'seal.json'),checks=checks,
        scope='portable rebuild of the one-card binary from the hash-pinned source archive passed every host-side gate; device qualification is pending and nothing arithmetic or performance is qualified until the device run',
        oracle_cap=128,full_output_oracle_exact=False,execution_order='incident-retrospective once, reset, prefill512, remaining11 once',
        synthetic_report_scope='shared64/128 plus local512; synthetic CPU evidence is not performance or arithmetic qualification',
        native_probe_scope=native['scope'],draft_probe_scope=native['draft_scope'],
        portable_rebuild=True,historical_binary_sha256=build['historical_binary_sha256'],
        historical_binary_hash_matches=build['historical_binary_hash_matches'],
        codex_shm_hash_matches=build['codex_shm_hash_matches'],
        proposal_sha256=sha(proposal))))
    print(name,'final checks PASS',flush=True)
proposals=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
proposal_rows=[]
for name,lane in [('one-card','A')]:
    f=proposals/f'proposed-p178-{name}-{lane}.txt';proposal_rows.append(dict(path=str(f.relative_to(ROOT)),sha256=sha(f)))
    jobs=[json.loads(s) for s in f.read_text().splitlines() if s and not s.startswith('#')]
    assert len(jobs)==2 and all(j['name'].startswith('packet178-') for j in jobs)
if args.ready:
    for p,value in ready:save(p/'READY-FOR-DEVICE.json',value)
    save(P/'READY-FOR-DEVICE.json',dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
        packets={str((p/'READY-FOR-DEVICE.json').relative_to(P)):sha(p/'READY-FOR-DEVICE.json') for p,_ in ready},proposals=proposal_rows,checks=root_checks,
        portable_rebuild=True,device_qualification_pending=True,full_output_oracle_exact=False,
        scope='CPU preparation of the portable-rebuilt one-card packet only; one-card lane A whole-host; device qualification pending; no queue action'))
    print('READY written last; no GPU run or queue action')
