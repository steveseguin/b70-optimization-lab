"""Verify every CPU gate and the current seal; READY is the final file mutation.

Order: CPU gates -> package_rows.py (seal + proposal) -> validate_flags.py -> check_queue_rows.py
(plan + rehearse) -> final_checks.py -> final_checks.py --ready. The pin guard follows READY's
hash links into the evidence receipts, so --ready writes READY, then re-runs the real pin guard
(pin_guard.check_job) on both proposal rows over the full closure, and withdraws READY on any
refusal. It also prints the closure's pin classification (every pin in-packet or immutable).
"""
import argparse,json,subprocess,sys,time
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
    for leaf in ('native-delta.json','build.json','identity-check.json','delta-check.json','analyzer-tests.json','report512-test.json',
                 'real-arm-sequence.json','native-sequence.json','preparation-probe.json','device-path-imports.json','flags.json',
                 'checkpoint-probe.json','lifecycle-test.json','p179-receipt-replay.json','p180-receipt-replay.json'):
        f=p/'evidence'/leaf;r=read(f);assert r['passed'] and r['device_executed'] is False,(name,leaf)
        checks[str(f.relative_to(p))]=sha(f)
    build=read(p/'evidence/build.json')
    assert build['reused_object_files'] is True and build['kernel_objects_unchanged'] is True and build['reused_object_count']==41
    assert build['arithmetic_qualified'] is False
    assert build['parent_binary_sha256']=='1364bb3de0e0742ea3c5419a3f6850cea3646466c19732ad5cf3fe9be2b1b7cf'
    assert build['previous_checkpoint_binary_sha256']=='f68714ce06c6318a6c7e9ea0b3aa39a58da684f872d6c10efe5f93b7ba143814'
    assert build['binary_sha256'] not in (build['parent_binary_sha256'],build['previous_checkpoint_binary_sha256'])
    native=read(p/'evidence/native-sequence.json')
    assert native['target_resets_per_native_owner']==14 and native['sensor_streams_per_reset']==4
    assert native['peak_child_rss_bytes']<4*1024**3 and len(native['results'])==1
    for result in native['results']:
        assert result['returncode']==0 and len(result['sensor_checks'])==56
    probe=read(p/'evidence/checkpoint-probe.json')
    assert probe['round_trip']['merged_equal_reference'] and probe['round_trip']['repeat_restore_identical']
    a=probe['append'];assert a['append_equals_reference'] and a['restore_then_save_chain_equals_reference'] and a['fresh_save_state_identical']
    assert probe['packet180_refusal_cases']==26 and probe['compat_refusal_cases']>=8 and probe['concurrent_delete_vs_restore']['delete_reason']=='in_use'
    assert probe['label']=='qualified-one-card' and probe['contract']=='v1.2+p181' and len(probe['append']['span_variants'])==3
    assert probe['prefill_path']['engine_mechanism']=='incremental' and probe['prefill_path']['chunked_path_exists'] is False
    assert set(probe['label_compatibility'])>={'inspect_experimental','resume_experimental','append_restore_then_save_experimental','experimental_refused_only_by_identity','pairing_refusals','delete_experimental'}
    for case in ('p179-as-experimental','p179-as-qualified','p180-real-s1','p180-real-s2'):
        assert probe['production_shape'][case]['real_control_blob_semantics_pass'] and probe['production_shape'][case]['blobs']==128,case
    assert probe['production_shape']['p180-real-s1']['device_fields_tsv_equals_reader_rendering']
    assert read(p/'evidence/p179-receipt-replay.json')['source_is_real_device_evidence']
    replay=read(p/'evidence/p180-receipt-replay.json');assert replay['source_is_real_device_evidence'] and replay['new_measurement'] is False
    assert replay['checks']['packet180_lifecycle_check_reproduces_device_receipt']['gates']==36
    assert round(replay['checks']['row_a_real']['class_balanced_median'],2)==31.78
    life=read(p/'evidence/lifecycle-test.json');assert life['gates_on_pass']==43
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
        assert not (p/'evidence'/f'device-p181-full512-{lane}-a').exists() and not (p/'evidence'/f'device-p181-lifecycle-{lane}-b').exists()
    seal=read(p/'seal.json')
    for leaf,h in seal['files'].items():assert sha(p/leaf)==h,(name,leaf)
    identity=read(p/'identity.json');assert sha(p/'build/device/own-rt-iq3')==identity['binary_sha256']==build['binary_sha256']
    assert identity['native_arithmetic_unchanged_from_packet163'] and not identity['native_binary_unchanged_from_packet163']
    assert identity['parent_binary_sha256']==build['parent_binary_sha256']
    for rel,h in read(p/'inherited-native.json')['embedded_readonly_dependencies'].items():
        assert (ROOT/rel).is_relative_to(p) and sha(ROOT/rel)==h
    budget=read(p/'budget.json');assert budget['device_floor_bytes']==25_000_000_000 and budget['cpu_stop_bytes']==27_000_000_000
    assert budget['host_required_available_bytes']==98990252032 and budget['planned_write_bytes']==400_000_000
    checks['seal.json']=sha(p/'seal.json')
    proposal=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'/f'proposed-p181-{name}-A.txt'
    ready.append((p,dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
        seal_sha256=sha(p/'seal.json'),checks=checks,
        scope='session checkpoint v3 (manifest label qualified-one-card + qualified_by, contract v1.2+p181, read compatibility with packet180 v1.2+p180 experimental manifests, prefill/append path record): entry-TU-only native delta over a packet165 byte-identical kernel relink passed every host-side gate including the CPU sessions, append-span variants, label-compatibility cases, refusals, concurrency, the production-shape inspect of packet179\'s and packet180\'s real checkpoints and the replay of packet180\'s real receipts; no chunked prefill exists or is added; device qualification of this binary is pending',
        oracle_cap=128,full_output_oracle_exact=False,
        execution_order='row a: incident-retrospective once, reset, prefill512, remaining 11 once; must equal packet179 row a (== packet180 row a). row b: save-s1, append-s2 (restore-then-save), resume-s2, reference, append-s2b, then host tools',
        synthetic_report_scope='shared64/128 plus local512 and the lifecycle arm; synthetic CPU evidence is not performance or arithmetic qualification',
        native_probe_scope=native['scope'],draft_probe_scope=native['draft_scope'],checkpoint_probe_scope=probe['scope'],
        experimental_checkpoint=False,checkpoint_label='qualified-one-card',checkpoint_contract='v1.2+p181',parent_binary_sha256=build['parent_binary_sha256'],
        kernel_objects_byte_identical_to_packet165=True,
        first_execution='rebuilt binary executed only host-side --help in capture_flags/rehearsal',
        proposal_sha256=sha(proposal))))
    print(name,'final checks PASS',flush=True)
proposals=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'
proposal_rows=[]
for name,lane in [('one-card','A')]:
    f=proposals/f'proposed-p181-{name}-{lane}.txt';proposal_rows.append(dict(path=str(f.relative_to(ROOT)),sha256=sha(f)))
    jobs=[json.loads(s) for s in f.read_text().splitlines() if s and not s.startswith('#')]
    assert len(jobs)==2 and all(j['name'].startswith('packet181-') for j in jobs)
    assert jobs[0]['name'].endswith('-full512-A-a') and jobs[1]['name'].endswith('-lifecycle-A-b')
if args.ready:
    for p,value in ready:save(p/'READY-FOR-DEVICE.json',value)
    save(P/'READY-FOR-DEVICE.json',dict(ready=True,device_executed=False,queued=False,created_utc_ns=time.time_ns(),
        packets={str((p/'READY-FOR-DEVICE.json').relative_to(P)):sha(p/'READY-FOR-DEVICE.json') for p,_ in ready},proposals=proposal_rows,checks=root_checks,
        experimental_checkpoint=False,checkpoint_label='qualified-one-card',device_qualification_pending=True,full_output_oracle_exact=False,
        scope='CPU preparation of the session-checkpoint v3 one-card packet only; one-card lane A whole-host; device qualification pending; no queue action'))
    sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops/lane-queue'));import pin_guard
    try:
        for row in proposal_rows:
            for s in (ROOT/row['path']).read_text().splitlines():
                if s and not s.startswith('#'):
                    job=json.loads(s);result=pin_guard.check_job(job,ROOT,pin_guard.STAGE)
                    packet=pin_guard.packet_for_job(job,ROOT,pin_guard.STAGE)
                    pins,manifests=pin_guard.collect_pins(packet,ROOT)
                    oracle={(t,h) for t,h,src in pins if src.name=='oracle-binding.json'}
                    classes={}
                    for target,digest,source in pins:
                        if target.is_relative_to(packet) and target.resolve().is_relative_to(packet.resolve()):kind='in-packet'
                        else:kind=pin_guard.immutable_reason(target,digest,packet,oracle,pin_guard.STAGE) or 'CROSS-PACKET MUTABLE'
                        classes[kind]=classes.get(kind,0)+1
                    assert 'CROSS-PACKET MUTABLE' not in classes,classes
                    print('pin guard PASS',job['name'],dict(pins=result['pins'],manifests=result['manifests'],classes=classes),flush=True)
    except (pin_guard.PinRefusal,AssertionError):
        for f in (P/'READY-FOR-DEVICE.json',*(p/'READY-FOR-DEVICE.json' for p,_ in ready)):f.unlink()
        raise
    print('READY written last and pin guard passed; no GPU run or queue action')
