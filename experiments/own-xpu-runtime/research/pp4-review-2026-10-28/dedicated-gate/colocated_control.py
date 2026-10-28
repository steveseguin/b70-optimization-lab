#!/usr/bin/env python3
"""One bounded cold native-controller case; no server, reset, retry or oracle run.

The isolated adapter namespace deliberately replaces historical build-plan and
command hooks with validated current-build hooks. Transport/NativeController
methods remain the exact pinned adapter6 implementations.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys
import time
import types

ROOT = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime')
sys.path.insert(0, str(ROOT/'engine/tools'))
import pipeline_driver as base
import live_wavefront_driver as live
ADAPTER = ROOT/'gsq-rco-iq3s/serving/lan/adapter6.py'


def native_argv(argv, out, rank):
    # Legacy launch argument caps128; independent native-request count is512.
    # This is the incumbent service contract, not request truncation.
    a=base.replace_options(list(argv), {'--target-split':23,'--max-new':128,
        '--shared':Path(out)/'transport/shared.bin','--output':Path(out)/f'native/rank{rank}'},
        {'--pipeline-boundaries','--pipeline-stage'})
    a=[x for x in a if x not in ('--pipeline-wavefront','--pipeline-live-draft','--pipeline-wavefront-verify-restore')]
    base.require(not any(x.startswith('--pipeline-') or x.startswith('--provider-') for x in a),
        'no residual target-pipeline or separate-provider options in native control')
    return a


def make_plan(config_path):
    config_path = Path(config_path).resolve()
    c = json.loads(config_path.read_text())
    p = live.make_plan(config_path)
    base.require(p['context'] == 65536 and p['boundaries'] == [0,23,48]
                 and len(p['prompt_tokens']) == 1677 and p['max_new'] == 512,
                 'fixed bounded cold1677/512 control')
    expected = Path(c['expected_result']).resolve()
    expected_plan = Path(c['expected_plan']).resolve()
    e, ep = json.loads(expected.read_text()), json.loads(expected_plan.read_text())
    base.require(e['passed'] is True and len(e['output_ids']) == 512
                 and ep['prompt_tokens'] == p['prompt_tokens']
                 and ep['model_identity_sha256'] == p['model_identity_sha256']
                 and ep['eos_token_ids'] == p['eos_token_ids'], 'qualified expected output identity')
    receipt = json.loads(Path(c['build_receipt']).read_text())
    out = Path(p['output'])
    for stage in p['stages']:
        stage['argv'] = native_argv(stage['argv'],out,stage['id'])
        stage['native_output'] = str(out/f"native/rank{stage['id']}")
    p.update(schema='ownrt.colocated-native-control-plan.v1', mode='native-controller-colocated-depth1',
             speculative_depth=1, native_launch_max_new=128, native_request_max_new=512, check_policy='native-incumbent', expected_output_ids=e['output_ids'],
             expected_result=str(expected), expected_plan=str(expected_plan),
             binary_sha256=receipt['binary_sha256'], fresh_cold_request=True,
             limits='One prompt diagnostic; depth1 colocated vs depth3 separate provider is explicit treatment.')
    # Pin every actual dependency imported by adapter6, in addition to current build/plan pins.
    spec = importlib.util.spec_from_file_location('colocated_adapter_plan_dependencies',ADAPTER)
    adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
    for path in (ADAPTER, Path(__file__).resolve(), expected, expected_plan, Path(adapter.PARENT),
                 Path(adapter.ENV_SOURCE), adapter.LANE/'recurrent-f32/operating/candidate-ledger.json'):
        p['pins'][str(path)] = base.digest(path)
    for path, digest in adapter.source_pins().items():
        f = Path(path) if Path(path).is_absolute() else adapter.ROOT/path
        base.require(base.digest(f) == digest, 'adapter source pin identity')
        p['pins'][str(f)] = digest
    return p


def bind_adapter(plan, guard):
    spec = importlib.util.spec_from_file_location('colocated_current_build_adapter', ADAPTER)
    a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
    a.TARGET_SPLIT, a.ACTIVATIONS, a.PREFILL_ROWS = 23, 'f32', 0
    out = Path(plan['output'])
    transport_plan = dict(plan, output=str(out/'transport'), evidence_output=str(out/'native'),
        mini=False, wait_seconds=plan['seconds'], environment=[s['environment'] for s in plan['stages']],
        max_new=plan.get('max_new',512), context=plan.get('context',65536))
    receipt_path = Path(json.loads(Path(plan['config']).read_text())['build_receipt'])
    receipt = json.loads(receipt_path.read_text())
    transport_plan['binary'] = receipt['binary']
    transport_plan['storage'] = dict(root_floor_bytes=plan['root_floor_bytes'],external_floor_bytes=plan['evidence_floor_bytes'],
        control_cache_forecast_bytes=128*1024**2,evidence_forecast_bytes=128*1024**2)
    def validate(p):
        base.require(p == transport_plan, 'exact isolated transport plan')
        for path,digest in plan['pins'].items():
            base.require(base.digest(path)==digest,'source/input/build pin changed: '+path)
        base.require(base.digest(receipt['binary']) == receipt['binary_sha256'] == plan['binary_sha256'], 'current native binary')
        for path,digest in receipt['sources'].items():
            base.require(base.digest(ROOT/'engine/src'/path)==digest,'compiled native source changed: '+path)
        return receipt
    def command(p,rank,channel,stop):
        validate(p)
        base.require(rank in (0,1), 'two actual native ranks')
        return [str(channel) if x=='<channel-fd>' else str(stop) if x=='<stop-fd>' else x
                for x in plan['stages'][rank]['argv']]
    # These are explicit adapter hooks, replacing historical SERVICE_BUILD validation;
    # no imported method or global module shared with another lane is modified.
    a.validate_plan, a.command = validate, command
    real_popen = a.subprocess.Popen
    def popen(argv, **kwargs):
        rank = len(guard.tracked_processes)
        base.require(rank in (0,1),'at most two launches')
        with guard.lock:
            base.require(guard.failed is None and not guard.signal_stop.is_set()
                         and time.monotonic()<guard.deadline,'launch cancelled')
            p = real_popen(argv, **kwargs)
            # Register even if the original constructor subsequently fails.
            guard.tracked_processes.append((rank,p))
            identity = guard.obs.process_identity(p.pid)
            base.require(identity is not None,'new native process identity')
            guard.identities[p.pid]=(identity['start_ticks'],plan['stages'][rank]['bdf'])
        return p
    a.subprocess = types.SimpleNamespace(Popen=popen, STDOUT=a.subprocess.STDOUT)
    return a, transport_plan



def native_timing(result, expected, started, finished):
    rows=result['timing_rows']
    base.require(result['tokens']==expected and len(rows)==len(expected)==512
        and [r['generated_index'] for r in rows]==list(range(1,513))
        and [r['token_id'] for r in rows]==expected,'actual native timing row identity')
    stamps=[r['completed_monotonic'] for r in rows]
    base.require(all(type(t) in (int,float) and math.isfinite(t) and started<=t<=finished for t in stamps)
        and all(a<b for a,b in zip(stamps,stamps[1:])), 'strict native completion timestamps')
    span=stamps[-1]-stamps[0]
    base.require(result['decode_intervals']==511 and math.isclose(result['decode_wall_ms'],span*1000,rel_tol=1e-9,abs_tol=1e-6),
        'native aggregate timing matches actual512 event span')
    return dict(first99_decode_tokens_per_second=99/(stamps[99]-stamps[0]),
        decode_tokens_per_second=511/span,decode_intervals=511,
        timing_source='native-result timing_rows completed_monotonic seconds; first100 actual outputs and all512 actual outputs')


def execute(plan, admission, unit, *, request=None):
    base.require(admission.get('schema')=='ownrt.pipeline-admission.v1' and admission.get('owner_authorized') is True,
                 'owner admission required')
    base.require(datetime.fromisoformat(admission['expires_utc'])>datetime.now(timezone.utc),'admission expired')
    base.require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
    identity=base.validate_unit(unit)
    out=Path(plan['output']);out.mkdir(mode=0o700)
    base.save(out/'plan.json',plan);base.save(out/'admission.json',admission);base.save(out/'unit.json',identity)
    guard=base.Guard(plan,admission,None)
    prior={s:signal.getsignal(s) for s in (signal.SIGINT,signal.SIGTERM)}
    for s in prior:signal.signal(s,lambda *_:guard.signal_stop.set())
    transport=None;result={};failure=None
    try:
        guard.thread.start()
        a,tp=bind_adapter(plan,guard)
        transport=a.Transport.__new__(a.Transport)
        def check():
            if hasattr(transport,'stop_write'):
                with guard.lock:
                    if transport.stop_write not in guard.stoppers:guard.stoppers.append(transport.stop_write)
            guard.check()
        transport.__init__(tp,admit=lambda p:base.require(p==tp,'transport admission'),check=check,
                           launch_hook=lambda pid:base.require(pid in guard.identities,'guarded owner'))
        guard.validate_or_stop(guard.obs.observe(),phase='native-control-after-ready')
        transport.sequence_started=True;transport.request_output=transport.out
        began=time.monotonic()
        if request is not None:
            result=request(a,transport,plan,began)
        else:
            result=a.NativeController(transport,a.BASE.Draft('mtp'),True,False,prefill=0,start=0).run(
                plan['prompt_tokens'],512,plan['eos_token_ids'])
            ended=time.monotonic()
            base.require(result['tokens']==plan['expected_output_ids'],'exact512 qualified output IDs')
            base.require(result['decode_intervals']==511 and result['decode_wall_ms']>0,'native decode interval accounting')
            timing=native_timing(result,plan['expected_output_ids'],began,ended)
            result.update(actual_output_ids=result['tokens'],request_started_monotonic_s=began,
                request_finished_monotonic_s=ended,cached_tokens=0,
                cold_proof='single first native request on freshly loaded ranks; no reset/continuation',
                speculative_depth=1,evidence_label='single-prompt topology/depth diagnostic; no independent quality or record claim',**timing)
        guard.validate_or_stop(guard.obs.observe(),phase='native-control-before-finish')
        transport.close(True)
    except BaseException as error:
        failure=repr(error);guard.fail(failure)
        if transport is not None and hasattr(transport,'stop_write'):
            try:transport.stop(error);transport.close(False)
            except BaseException as cleanup:result['cleanup_error']=repr(cleanup)
    finally:
        end=time.monotonic()+plan['grace_seconds']
        while any(p.poll() is None for _,p in guard.tracked_processes) and time.monotonic()<end:time.sleep(.2)
        guard.done.set();guard.thread.join(timeout=35)
        if guard.thread.is_alive():guard.fail('passive observer did not quiesce')
        try:guard.validate_or_stop(guard.obs.observe(),phase='native-control-after-exit')
        except BaseException as error:failure=failure or repr(error)
        codes={str(i):p.poll() for i,p in guard.tracked_processes}
        alive=[p.pid for _,p in guard.tracked_processes if p.poll() is None]
        failure=failure or guard.failed
        if len(codes)!=2 or alive or any(v!=0 for v in codes.values()):failure=failure or 'native owners did not exit cleanly'
        for s,h in prior.items():signal.signal(s,h)
        base.save(out/'result.json',dict(result,passed=failure is None,error=failure,returncodes=codes,live_pids=alive,
            schema='ownrt.colocated-native-control-result.v1'))
        base.save(out/'terminal.json',dict(passed=failure is None,error=failure,returncodes=codes,live_pids=alive))
    base.require(failure is None,str(failure))


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');args=ap.parse_args()
    if not args.run:
        base.save(args.plan,make_plan(args.config));print(json.dumps({'plan':str(args.plan),'sha256':base.digest(args.plan),'device_execution_requested':False}));return
    p=json.loads(args.plan.read_text());base.require(p==make_plan(p['config']),'plan/source identity changed')
    base.require(args.admission and args.unit,'admission and owning unit')
    admission=json.loads(args.admission.read_text());base.require(admission['plan_sha256']==base.digest(args.plan),'admission plan SHA')
    execute(p,admission,args.unit)

if __name__=='__main__':main()
