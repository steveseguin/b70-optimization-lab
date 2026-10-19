"""Verify every CPU gate and current seal; READY is the final file mutation."""
import argparse,json,subprocess,time
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
ap=argparse.ArgumentParser();ap.add_argument('--ready',action='store_true');args=ap.parse_args();limits()
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='main'
read=lambda f:json.loads(f.read_text())
root_checks={}
for leaf in ('packet163-replay.json',):
    f=P/'evidence'/leaf;assert read(f)['passed'];root_checks[leaf]=sha(f)
f=P/'evidence/prefill-ceiling.json'
assert read(f)['measured'] is False and read(f)['promotion_eligible'] is False
root_checks['design-sensitivity']=sha(f)
ready=[]
for name,lanes in [('one-card','A'),('two-card','AB')]:
    p=P/name;checks={}
    for leaf in ('build.json','identity-check.json','delta-check.json','analyzer-tests.json','report512-test.json',
                 'real-arm-sequence.json','native-sequence.json','preparation-probe.json','device-path-imports.json','flags.json'):
        f=p/'evidence'/leaf;r=read(f);assert r['passed'] and r['device_executed'] is False,(name,leaf)
        checks[leaf]=sha(f)
    native=read(p/'evidence/native-sequence.json')
    assert native['target_resets_per_native_owner']==14 and native['sensor_streams_per_reset']==4
    assert native['peak_child_rss_bytes']<4*1024**3
    assert len(native['results'])==(1 if name=='one-card' else 2)
    for result in native['results']:
        assert result['returncode']==0 and len(result['sensor_checks'])==56
    for lane in lanes:
        stem=('one' if name=='one-card' else 'two')+'-'+lane
        report=P/'evidence'/('rehearse-'+stem+'.json');r=read(report)
        assert r['passed'] and len(r['jobs'])==2
        assert all(j['passed'] and j['report']['passed'] and not j['service_started'] for j in r['jobs'])
        checks['shared-report-'+lane]=sha(report)
        log=P/'evidence'/('plan-'+stem+'.log')
        rows=[json.loads(line) for line in log.read_text().splitlines() if line.startswith('{')]
        assert len(rows)==2 and all(r['plan']=='passed' for r in rows)
        checks['lanequeue-plan-'+lane]=sha(log)
        for attempt in ('a','b'):assert not (p/'evidence'/f'device-warm512-{lane}-{attempt}').exists()
    seal=read(p/'seal.json')
    for leaf,h in seal['files'].items():assert sha(p/leaf)==h,(name,leaf)
    identity=read(p/'identity.json');assert sha(p/'build/device/own-rt-iq3')==identity['binary_sha256']
    assert identity['native_arithmetic_unchanged_from_packet163'] and not identity['native_binary_unchanged_from_packet163']
    for rel,h in read(p/'inherited-native.json')['embedded_readonly_dependencies'].items():
        assert (ROOT/rel).is_relative_to(p) and sha(ROOT/rel)==h
    budget=read(p/'budget.json');assert budget['device_floor_bytes']==25_000_000_000 and budget['cpu_stop_bytes']==27_000_000_000
    ready.append((p,dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
        seal_sha256=sha(p/'seal.json'),checks=checks,scope='CPU preparation passed; warm512 speed and full-output quality remain unmeasured',
        oracle_cap=128,full_output_oracle_exact=False,execution_order='incident-retrospective once, reset, prefill512, remaining11 once',
        synthetic_report_scope='shared64/128 plus local512; synthetic CPU evidence is not performance or arithmetic qualification',
        native_probe_scope=native['scope'],draft_probe_scope=native['draft_scope'])))
    print(name,'final checks PASS',flush=True)
proposals=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
proposal_rows=[]
for name,lane in [('one-card','A'),('two-card','A'),('two-card','B')]:
    f=proposals/f'proposed-p165-{name}-{lane}.txt';proposal_rows.append(dict(path=str(f.relative_to(ROOT)),sha256=sha(f)))
    jobs=[json.loads(s) for s in f.read_text().splitlines() if s and not s.startswith('#')]
    assert len(jobs)==2 and all(j['name'].startswith('packet165-') for j in jobs)
if args.ready:
    for p,value in ready:save(p/'READY-FOR-DEVICE.json',value)
    save(P/'READY-FOR-DEVICE.json',dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
        packets={p.name:sha(p/'READY-FOR-DEVICE.json') for p,_ in ready},proposals=proposal_rows,checks=root_checks,
        warm512_measured=False,batched_prefill_implemented=False,full_output_oracle_exact=False,
        scope='CPU preparation only; select A or B two-card proposal; one-card A whole-host; no queue action'))
    print('READY written last; no GPU run or queue action')
