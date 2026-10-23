"""P209 one-shot coordinator. Import and --plan never inspect/open a device.
Operational admission is supplied by the root coordinator, never synthesized.
"""
from pathlib import Path
import argparse, contextlib, hashlib, importlib.util, json, os, resource, signal, subprocess, sys, time
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
P181 = P.parent / 'packet181-session-swap-v3/one-card'
BDF = '0000:27:00.0'
UNIT = 'packet209-native-pair-a'
MANIFEST = P / 'READY-FOR-DEVICE.json'
OUTPUT = P / 'evidence/device-a'
BINARY = P / 'build/native/paired-qualification'
FLOOR = 27_000_000_000
WRITE_BYTES = 256 * 1024**2
HOST_BYTES = 3 * 1024**3
CPUS = {0, 1, 2, 3, 16, 17, 18, 19}
HELPER = ROOT / 'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py'
SCHEMA = 'packet209.native-admission.v1'
SAFE_UNIT = {'Restart':'no','SendSIGKILL':'no','KillMode':'process','TimeoutStopUSec':'infinity','ExitType':'cgroup','UMask':'0077'}

def require(value, message):
    if not value: raise RuntimeError('P209: ' + message)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def present(path): return os.path.lexists(path)
def no_duplicates(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, 'duplicate JSON key ' + k)
        result[k] = v
    return result

def read_json(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 1024*1024, 'JSON exceeds bound')
    return json.loads(raw, object_pairs_hook=no_duplicates)

def environment():
    # Pinned literal launch_env is imported without invoking a child/device.
    spec=importlib.util.spec_from_file_location('p209_launch_env', P181/'launch_env.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return dict(module.environment(), HOME='/home/steve', NEOReadDebugKeys='1',
                FilterBdfPath=BDF, ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0',
                ONEAPI_DEVICE_SELECTOR='level_zero:0', SYCL_CACHE_DIR=str(OUTPUT)+'.control/cache/sycl', NEO_CACHE_DIR=str(OUTPUT)+'.control/cache/neo', XDG_CACHE_HOME=str(OUTPUT)+'.control/cache/xdg')

def source_closure():
    files=[P/n for n in ('runner.py','live_ops.py','entry.cpp','native_guard.hpp','strict_json.hpp','build_entry.py','parent-pins.json')]
    files += [P181/n for n in ('lane_admission.py','drain_gate.py','chain_devices.py','launch_env.py','lineage/window_driver.py')]
    files.append(HELPER)
    build=P/'evidence/build-compile-only.json'
    require(build.is_file(), 'compiled entry receipt required')
    row=read_json(build);require(row.get('passed') is True and row.get('compile_only') is True, 'successful compile-only build')
    require(row['device_image_sha256']=='e90834e35401eceaa48d1cb9691b6b0bfa56d456e9d57464636140d0c2e3f4a5', 'compiled device image identity')
    for path,want in row['source_sha256'].items():require(sha(ROOT/path)==want,'entry build source changed')
    for path,want in row['plan']['objects'].items():require(sha(path)==want,'native linked object changed')
    require(sha(BINARY)==row['plan']['binary_sha256'], 'native ELF differs from compile receipt')
    files += [build] + [ROOT/p for p in row['plan']['repository_dependencies']]
    parent_pins=read_json(P/'parent-pins.json')
    for path,want in parent_pins.items():require(sha(ROOT/path)==want,'frozen parent pin changed')
    files += [ROOT/p for p in parent_pins]
    result={str(p.relative_to(ROOT)):sha(p) for p in files}
    for path,want in row['plan']['repository_dependencies'].items():require(result[path]==want,'compiler input changed')
    return result

def validate_manifest(m):
    keys={'schema','authorized','unit','bdf','lane','window','timing_claim','output','binary',
          'binary_sha256','boot_id','expires_unix','environment','source_sha256','fault_review',
          'fault_review_sha256','pause_sha256','queue_sha256','protected_units','allowed_holders',
          'target_nodes','topology','competitor_units','root_floor_bytes','write_bytes','host_available_bytes',
          'parent_device_image_sha256'}
    require(type(m) is dict and set(m)==keys, 'exact manifest schema')
    require(m['schema']==SCHEMA and m['authorized'] is True, 'explicit operational admission required')
    require((m['unit'],m['bdf'],m['lane'],m['window'],m['timing_claim'])==(UNIT,BDF,'A','screen',False), 'fixed target/scope')
    require(m['output']==str(OUTPUT) and m['binary']==str(BINARY), 'fixed artifact paths')
    require(m['environment']==environment(), 'closed native environment')
    require((m['root_floor_bytes'],m['write_bytes'],m['host_available_bytes'])==(FLOOR,WRITE_BYTES,HOST_BYTES), 'resource floors')
    require(type(m['expires_unix']) is int and len(m['boot_id'])==36, 'boot/expiry identity')
    for name in ('binary_sha256','fault_review_sha256','parent_device_image_sha256'):
        require(type(m[name]) is str and len(m[name])==64 and all(c in '0123456789abcdef' for c in m[name]), 'SHA256 '+name)
    require(m['parent_device_image_sha256']=='e90834e35401eceaa48d1cb9691b6b0bfa56d456e9d57464636140d0c2e3f4a5', 'unchanged P208 device image')
    require(type(m['source_sha256']) is dict and m['source_sha256'], 'source closure required')
    require(set(m['pause_sha256'])=={'A','B'} and set(m['queue_sha256'])=={'A','B'}, 'both latches and queues bound')
    require(len(m['protected_units'])==3 and len(set(m['protected_units']))==3, 'three protected applications')
    require(len(m['target_nodes'])==2 and all(x.startswith('/dev/dri/') for x in m['target_nodes']), 'target card/render pair')
    require(type(m['topology']) is dict and len(m['topology'])==8 and set(m['target_nodes'])=={p for p,r in m['topology'].items() if r['bdf']==BDF}, 'complete admitted topology')
    require(type(m['allowed_holders']) is list and m['allowed_holders'], 'protected holder inventory required')
    for h in m['allowed_holders']:
        require(set(h)=={'pid','start_ticks','nodes'} and type(h['pid']) is int and h['pid']>1 and type(h['start_ticks']) is int and h['start_ticks']>0, 'holder PID/start identity')
        require(h['nodes'] and not set(h['nodes']) & set(m['target_nodes']), 'daily holder cannot own target')
    require(type(m['competitor_units']) is list and m['competitor_units'], 'competitor unit census required')
    return m

def classify_inventory(raw, target_nodes, allowed_holders, identities, child=None):
    """Global passed=false is expected with daily apps. Every raw error is fatal."""
    require(set(raw)=={'passed','holders','errors','nodes','intel_devices','metadata_only','device_opens'}, 'raw inventory schema')
    require(raw['metadata_only'] is True and raw['device_opens']==0 and raw['errors']==[], 'passive inventory incomplete/errors')
    require(type(raw['holders']) is list and type(raw['nodes']) is dict and len(raw['intel_devices'])==4, 'raw inventory extent')
    require(raw['passed'] is (not raw['holders']), 'raw passed/holder contradiction')
    known={'/dev/dri/'+name for name in raw['nodes'].values()}
    require(len(known)==8 and set(target_nodes)<=known, 'complete DRM node inventory')
    normalized=[]
    for h in raw['holders']:
        require(set(h)=={'pid','fd','node'} and type(h['pid']) is int and h['pid']>1 and str(h['fd']).isdigit(), 'raw holder schema')
        node=h['node'] if h['node'].startswith('/dev/dri/') else '/dev/dri/'+h['node']
        require(node in known, 'holder unknown DRM node')
        normalized.append(dict(h,node=node))
    allow={h['pid']:h for h in allowed_holders}
    require(len(allow)==len(allowed_holders), 'duplicate allowed PID')
    observed=False
    for h in normalized:
        pid=h['pid'];node=h['node'];ticks=identities.get(pid)
        if child and pid==child['pid']:
            require(ticks==child['start_ticks'] and node in target_nodes, 'child PID reuse or wrong card')
            observed=True
        else:
            require(pid in allow and ticks==allow[pid]['start_ticks'] and node in allow[pid]['nodes'], 'foreign/changed device holder')
            require(node not in target_nodes, 'target occupied')
    for pid,h in allow.items():require(identities.get(pid)==h['start_ticks'], 'protected process gone/reused')
    return {'child_observed':observed,'target_empty':not any(h['node'] in target_nodes for h in normalized)}

def validate_snapshot(m, s):
    require(s['boot_id']==m['boot_id'] and s['now_unix']<=m['expires_unix'], 'stale boot/admission')
    require(s['pause_sha256']==m['pause_sha256'] and s['queue_sha256']==m['queue_sha256'] and s['queues_empty'], 'latch/queue changed')
    require(not s['stop_present'] and s['competitors_inactive'], 'STOP or competing experiment')
    require(s['protected_units']==m['protected_units'], 'daily application identity changed')
    require(s['target_bdf']==BDF and s['target_nodes']==m['target_nodes'] and s['topology']==m['topology'], 'passive card mapping changed')
    require(s['faults_clear'] is True, 'new kernel fault')
    require(s['free_bytes']-WRITE_BYTES>=FLOOR and s['mem_available_bytes']>=HOST_BYTES, 'resource headroom')
    require(s['unit_properties']==SAFE_UNIT, 'unsafe one-shot unit')
    return True

def finish_proof(result, returncode, observation, target_empty):
    require(returncode==0 and observation, 'child failed or was never observed on target')
    require(result.get('passed') is True and result.get('safe_to_exit') is True, 'native qualification did not pass')
    owner=result.get('teardown',{})
    if isinstance(owner,str): owner=json.loads(owner)
    require(owner.get('safe_to_exit') is True and owner.get('in_flight')==0 and owner.get('live_bytes')==0 and owner.get('exit_code')==0 and owner.get('idle_marker_complete') is True, 'unsafe owner receipt')
    require(target_empty, 'target DRM descriptors remain')
    require(result.get('schema')=='packet208.future-native-proof.v1', 'P208 proof schema')
    cases=result.get('cases',[])
    require([r.get('rows') for r in cases]==[10240,6144] and all(r.get('passed') is True and r.get('native_serial_cpu_exact') is True and r.get('live_input_weight_controls') is True for r in cases), 'both exact synthetic cases required')
    for row in cases:
        require((row.get('columns'),row.get('stride'),row.get('variant'),row.get('pair_commands'),row.get('serial_commands'))==(2560,3380,6,1,2), 'selected pair ABI receipt')
        require(type(row.get('output_sha256')) is list and len(row['output_sha256'])==2 and all(type(h) is str and len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in row['output_sha256']), 'both output digest receipts')

def run_once(m, ops):
    """Injected operations are the live adapter, not alternate safety decisions.
    Retention loop is INSIDE both actual flock contexts. No retry or restart.
    ops.diagnose is passive and must work after admission itself has failed.
    """
    validate_manifest(m); ops.preflight(m)
    first=None; child=None; observed=False; signalled=False; attempted=False
    def safe_report(row):
        try:ops.receipt(row)
        except BaseException as secondary:
            try:ops.secondary(secondary)
            except BaseException:pass
    def retained_sleep():
        try:ops.sleep(.5)
        except BaseException:
            try:time.sleep(.5)
            except BaseException:pass
    with ops.reservation(m) as reservation:
        with ops.drain(m, reservation) as drain:
            try:
                ops.check(m)
                attempted=True  # Popen may be interrupted after creating a child
                child=ops.launch(m)
                while True:
                    ops.check(m)
                    state=ops.observe(m,child)
                    observed=observed or state['child_observed']
                    if observed:ops.ack(m,child)
                    if child.poll() is not None:
                        result=ops.result(m)
                        finish_proof(result,child.returncode,observed,state['target_empty'])
                        ops.check(m)
                        ops.receipt({'phase':'pre-completion','passed':True,'child_pid':child.pid,'observed':observed,'native':result})
                        drain.complete();reservation.complete(drained=True)
                        ops.receipt({'phase':'completed','passed':True,'child_pid':child.pid,'observed':observed,'native':result})
                        return 0
                    ops.sleep(.1)
            except BaseException as error:
                first=error
                safe_report({'passed':False,'error':repr(first),'child_pid':getattr(child,'pid',None),'retained':attempted,'passive_evidence':getattr(first,'passive_evidence',None)})
                if attempted:
                    try:ops.stop(m)
                    except BaseException:pass
                    # Signal only a positively identified returned child. Unknown
                    # spawn state is retained for coordinator review, never guessed.
                    if child is not None:
                        try:
                            if child.poll() is None:
                                signalled=True  # count attempted signal even if interrupted
                                child.send_signal(signal.SIGTERM)
                        except BaseException:pass
                    while True:
                        try:
                            proof=ops.diagnose(m,child)
                            if proof['child_exited'] and proof['owner_safe'] and proof['target_empty']:
                                safe_report({'passed':False,'error':repr(first),'child_pid':getattr(child,'pid',None),'retained':False,'signalled':signalled,'drain':proof})
                                break
                        except BaseException as secondary:
                            try:ops.secondary(secondary)
                            except BaseException:pass
                        retained_sleep()  # BOTH flocks retained through every failure
                raise first

# Live adapter is supplied below; --plan does not construct it.
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',action='store_true');ap.add_argument('--run',action='store_true');a=ap.parse_args()
    if not a.run:
        print(json.dumps({'schema':SCHEMA,'operational_admission':False,'unit':UNIT,'manifest':str(MANIFEST),'bdf':BDF,'output':str(OUTPUT),'native_environment':environment(),'native_argv':[str(BINARY),'--authorized-device-window','--manifest',str(MANIFEST),'--manifest-sha256','ROOT_SUPPLIED_SHA256'],'resource':{'root_floor_bytes':FLOOR,'write_bytes':WRITE_BYTES,'host_available_bytes':HOST_BYTES},'safe_unit':SAFE_UNIT},indent=2));return 0
    raise RuntimeError('P209 live adapter not finalized; no operational action')
if __name__=='__main__':raise SystemExit(main())
