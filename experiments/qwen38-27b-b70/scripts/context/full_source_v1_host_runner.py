#!/usr/bin/env python3
"""Separate one-shot full-source screen; reuse the frozen qualified owner lifecycle.

Prepare is passive. Execute owns exactly one cold server and two fixed requests.
No retries, replacement trials, service restoration or automatic continuation.
"""
import argparse
from contextlib import ExitStack, nullcontext
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('full_source_qualified_lifecycle', HERE/'history_study_v1_host_runner.py')
qualified = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qualified)
LANE = qualified.LANE
CLIENT = HERE/'full_source_v1/client.py'
AUDITOR = HERE/'audit_full_source_v1.py'
PRIOR_AUDITOR = HERE/'audit_history_study_v1.py'
DATA = LANE/'data/2026-10-07-full-source-screen'
PRIOR_PACKET = LANE/'data/2026-10-07-history-study'
PRESERVATION = LANE/'data/2026-10-07-history-study-result/preservation.json'
FEASIBILITY = LANE/'data/2026-10-07-full-source-feasibility'
PREREG = LANE/'notes/2026-10-07-full-source-screen-plan.md'
DEFAULT_PREVIOUS = Path('/mnt/fast-ai/bench-results/context-history-study-v1-20261007')
PROTOCOL = 'direct-full-source-screen-v1'
QUEUE_SCHEMA = 'full-source-host-queue.v1'
MODEL = 'qwen38-27b-fp8'
ORDER = ['t01-clinic','t02-theatre']
CACHE_POLICY = {'prefix_cache':'off','every_request_cached_tokens':0,'cache_metadata_required':True}
POLICY = {'message_limit_bytes':32768,'request_deadline_seconds':600,'max_requests_per_trial':1,
          'temperature':0,'answer_generation':{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192}}


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise RuntimeError(message)


def strict_passed(result):
    comparison=result.get('comparison',{})
    return (all(type(comparison.get(k)) is int and comparison[k]==12
                for k in ('exact_prompts','total_prompts')) and qualified.strict_passed(result))


def validate_packet(packet):
    """CPU-only validation in an isolated interpreter, never a client execution."""
    code = ('import json,sys;sys.path.insert(0,sys.argv[1]);import client;'
            'print(json.dumps(client.validate_packet(sys.argv[2])))')
    result = subprocess.run([sys.executable,'-B','-c',code,str(CLIENT.parent),str(Path(packet).resolve())],
        capture_output=True,text=True,timeout=180,
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'))
    require(result.returncode==0,'full-source packet validation failed: '+result.stderr[-2000:])
    value=json.loads(result.stdout)
    require(isinstance(value,dict) and set(value)=={'plan','tasks','requests'},'invalid full-source packet receipt')
    expected_trials(value)
    return value


def expected_trials(packet):
    plan,tasks=packet['plan'],packet['tasks']
    rows=plan.get('trials')
    require(plan.get('schema')=='full-source-plan.v1' and plan.get('protocol')==PROTOCOL,
            'unexpected full-source plan protocol')
    require(type(plan.get('expected_trials')) is int and plan['expected_trials']==2,
            'full-source plan must contain exactly two requests')
    require(all(qualified.same_json(plan.get(k),v) for k,v in POLICY.items()),'full-source generation or request limits differ')
    require(isinstance(rows,list) and [r.get('case_id') for r in rows]==ORDER,
            'full-source request order differs')
    for row in rows:
        case=row['case_id'];task=tasks[case]
        require(task.get('document_id')==case and len(task.get('batches',[]))==12
                and len(task.get('questions',[]))==24 and row.get('task_sha256')==task.get('task_sha256'),
                'full-source task binding differs')
        require(row.get('result_path')==case+'/result.json', 'unsafe full-source result path')
        for key in ('request_path','task_path'):
            path=Path(row.get(key,''))
            require(str(path) not in ('','.') and not path.is_absolute() and '..' not in path.parts,
                    'unsafe full-source packet path')
        require(isinstance(row.get('request_sha256'),str) and
                qualified.re.fullmatch('[0-9a-f]{64}',row['request_sha256']) is not None,
                'full-source request hash missing')
        request=packet['requests'][case]
        require(request.get('model')==MODEL,'candidate model differs from pinned server')
        require(row.get('timing_path')==case+'/timing.json','unsafe timing path')
    return rows


def normalized(value,root,key=None):
    if isinstance(value,dict):return {k:normalized(v,root,k) for k,v in value.items()}
    if isinstance(value,list):return [normalized(v,root) for v in value]
    if key in ('output','directory') and isinstance(value,str) and (value==str(root) or value.startswith(str(root)+'/')):
        return '<restored-root>'+value[len(str(root)):]
    return value


def safe_member(root,name):
    p=Path(name)
    require(isinstance(name,str) and name and not p.is_absolute() and '..' not in p.parts,
            'unsafe preservation member')
    result=root/p
    require(result.resolve().is_relative_to(root.resolve()) and not result.is_symlink(),
            'preservation path escapes its root')
    return result


def preservation_receipt(path, previous, audit_path):
    path=Path(path).resolve();previous=Path(previous).resolve();root=path.parent
    receipt=read(path)
    require(receipt.get('schema')=='context-history-preservation.v1'
            and receipt.get('output')==str(previous)
            and receipt.get('complete') is True and receipt.get('restored_audit_matches') is True
            and receipt.get('normalization')==['output','directory'],
            'history preservation and restored-audit receipt incomplete')
    inventory_path=root/'inventory.json'
    require(qualified.sha(inventory_path)==receipt.get('inventory_sha256'),'preservation inventory hash differs')
    inventory=read(inventory_path)
    require(inventory.get('schema')=='history-study-preservation.v1'
            and inventory.get('source_output')==str(previous)
            and type(inventory.get('sqlite_members_verified')) is int and inventory['sqlite_members_verified']==8,
            'preservation inventory must cover all eight SQLite stores')
    archive=safe_member(root,receipt['archive_path']);saved_audit=safe_member(root,receipt['audit_path'])
    require(archive.is_file() and qualified.sha(archive)==receipt.get('archive_sha256'),
            'preserved history archive identity differs')
    require(qualified.sha(saved_audit)==receipt.get('audit_sha256')
            and qualified.same_json(read(saved_audit),read(audit_path)), 'preserved independent audit differs')
    files=inventory.get('files_sha256')
    require(isinstance(files,dict) and receipt['archive_path'] in files and receipt['audit_path'] in files,
            'preservation inventory lacks archive/audit')
    bindings={str(path):qualified.sha(path),str(inventory_path):qualified.sha(inventory_path)}
    for name,digest in files.items():
        source=safe_member(root,name)
        require(source.is_file() and qualified.sha(source)==digest,'preserved file identity differs: '+name)
        if (previous/name).is_file():
            require(qualified.sha(previous/name)==digest,'preserved file differs from original: '+name)
        bindings[str(source)]=digest
    wanted={f"diagnostic/{r['case_id']}-{r['condition']}/native/canonical.sqlite"
            for r in read(audit_path)['trials']}
    require(len(wanted)==8,'preserved audit must identify eight distinct stores')
    with tempfile.TemporaryDirectory(prefix='full-source-prior-restore-') as temp:
        restored=Path(temp)/'result';restored.mkdir()
        for name in files:
            if name==receipt['archive_path']:continue
            destination=safe_member(restored,name);destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(safe_member(root,name).read_bytes())
        with tarfile.open(archive,'r:gz') as tar:
            members=tar.getmembers()
            require(len(members)==8 and {m.name for m in members}==wanted and all(m.isfile() for m in members),
                    'archive must contain exactly eight regular canonical stores')
            for member in members:
                data=tar.extractfile(member).read()
                require(data==(previous/member.name).read_bytes(),'preserved SQLite differs from original')
                destination=safe_member(restored,member.name);destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(data)
        replay=qualified.run_evidence_audit(PRIOR_AUDITOR,restored,PRIOR_PACKET)
        require(qualified.same_json(normalized(replay,restored),normalized(read(audit_path),previous)),
                'restored history audit differs beyond output/directory prefixes')
    return bindings


def previous_receipts(previous, preservation=PRESERVATION):
    """Never inspect an unfinished history campaign for scientific admission."""
    previous=Path(previous).resolve()
    terminal=read(previous/'status.json')
    require(terminal.get('phase')=='completed' and terminal.get('cards_released') is True,
            'all eight history outcomes and owner cleanup must finish first')
    queue=read(previous/'queue.json')
    require(queue.get('schema')=='history-study-host-queue.v1'
            and queue.get('protocol')=='context-history-study-live-v1','unexpected previous campaign identity')
    packet=qualified.validate_study_packet(PRIOR_PACKET)
    expected=qualified.expected_trials(packet)
    launch=previous/'server/launch.json'
    identity={'endpoint':f"http://127.0.0.1:{queue['port']}/v1",'model':queue['model'],'launch_sha256':qualified.sha(launch)}
    summary=qualified.verify_diagnostic(previous/'diagnostic',expected,server_identity=identity,
        source_code_sha256=packet['plan']['engine_source_sha256'])
    audit_path=previous/'diagnostic-independent-audit.json'
    saved=read(audit_path)
    audit=qualified.run_evidence_audit(PRIOR_AUDITOR,previous,PRIOR_PACKET)
    require(qualified.same_json(saved,audit),'saved history audit differs from independent reconstruction')
    qualified.verify_independent_study(audit,previous/'diagnostic',expected,summary,PRIOR_PACKET)
    continuation=audit.get('continuation',{})
    require(continuation.get('evidence_complete') is True
            and continuation.get('continuation_signal') is False
            and continuation.get('extension_admitted') is False,
            'history continuation has priority, or prior evidence is not interpretable')
    rows=audit['trials']
    decisive_quality=any(row.get('quality_passed') is False for row in rows)
    evaluable_cost=(len(rows)==8 and all(row.get('quality_passed') is True
        and row.get('cold_cost_interpretation') is True
        and type(row.get('total_trial_wall_seconds')) in (int,float)
        and qualified.math.isfinite(row['total_trial_wall_seconds']) and row['total_trial_wall_seconds']>0 for row in rows))
    require(decisive_quality or evaluable_cost,'unknown or nonzero cache cannot manufacture a negative cost signal')
    required=('queue.json','status.json','lifecycle.jsonl','server-stop.json','cards-released.json',
              'server/state.json','server/launch.json','diagnostic-independent-audit.json',
              'diagnostic-host-audit.json','postflight-health.command.json','postflight-health.log','strict-comparison.json')
    frozen={str(previous/name):qualified.sha(previous/name) for name in required}
    require((previous/'postflight-health.log').stat().st_size>0,'previous health evidence is empty')
    health_command=read(previous/'postflight-health.command.json')
    require(health_command.get('argv')==['bash',str(qualified.HEALTH)],'previous postflight command differs')
    if 'exit_code' in health_command:
        require(type(health_command['exit_code']) is int and health_command['exit_code']==0,
                'previous postflight recorded unsuccessful exit')
    # The immutable legacy helper writes no exit-code receipt; its completed status
    # is reachable only after monitored_command observed postflight exit 0.
    helper_path=str(Path(qualified.__file__).resolve())
    require(queue.get('dependency_sha256',{}).get(helper_path)==qualified.sha(helper_path)
            and queue['dependency_sha256'].get(str(qualified.HEALTH))==qualified.sha(qualified.HEALTH),
            'previous completed-postflight control flow is not bound to the frozen helper')
    lifecycle=[json.loads(line) for line in (previous/'lifecycle.jsonl').read_text().splitlines()]
    require(lifecycle and lifecycle[-1].get('phase')=='completed','previous lifecycle did not complete postflight')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    stop,state,cards=(read(previous/name) for name in ('server-stop.json','server/state.json','cards-released.json'))
    require(queue.get('hostname')==socket.gethostname()
            and all(v.get('boot_id')==boot for v in (queue,stop,state)), 'prior handoff belongs to another host or boot')
    require(stop.get('stop_confirmed') is True and state.get('stop_confirmed') is True
            and cards.get('verified') is True
            and all(stop.get(k)==state.get(k) for k in ('owner_pid','container_id','image_id')),
            'prior STOP/card-release receipts disagree')
    require(strict_passed(read(previous/'strict-comparison.json')),'prior strict qualification incomplete')
    qualified.verify_cold_emission(read(launch))
    for path in (previous/'diagnostic').rglob('*'):
        if path.is_file():
            frozen[str(path)]=qualified.sha(path)
    frozen.update(preservation_receipt(preservation,previous,audit_path))
    return {**queue,'full_source_admission':{**continuation,
            'negative_reason':'quality' if decisive_quality else 'exact_cold_cost',
            'prior_health_exit_zero_evidence':'explicit' if 'exit_code' in health_command else 'pinned-helper-completed-control-flow'}},frozen


def dependencies(launch_path, launch, packet=DATA):
    # Includes the complete immutable helper/qualified-launch transitive closure.
    hashes=qualified.dependencies(launch_path,launch,PRIOR_PACKET)
    files={Path(__file__).resolve(),AUDITOR,PREREG}
    for directory in (CLIENT.parent,Path(packet),FEASIBILITY):
        files.update(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and not p.name.startswith('test_'))
    require(CLIENT.is_file() and AUDITOR.is_file(),'full-source client or independent auditor missing')
    receipt=read(FEASIBILITY/'receipt.json')
    files.update(Path(v['path']) for v in receipt['inputs'].values())
    files.add(Path(receipt['runtime']['executable']))
    hashes.update({str(p.resolve()):qualified.sha(p) for p in sorted(files)})
    return hashes


def verify_dependencies(config):
    require(config['hostname']==socket.gethostname(),'prepared host changed')
    require(config['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'host rebooted; no queue resume')
    for path,digest in config['previous_revision']['artifacts'].items():
        require(Path(path).is_file() and qualified.sha(path)==digest,'preserved prior evidence changed: '+path)
    require(dependencies(config['protected_launch'],read(config['protected_launch']),config['packet'])==config['dependency_sha256'],
            'frozen dependency content or inventory changed')


def release_reason(config):
    reason=qualified.release_reason(config)
    if reason:
        return reason
    result=qualified.read_command(['systemctl','--user','list-units','--all','--plain','--no-legend','--no-pager',
                                   'ctx-history-study-v1.service'])
    for line in result.stdout.splitlines():
        cols=line.split()
        if len(cols)>=4 and cols[2] in {'active','activating','deactivating','reloading'}:
            return 'protected history study remains active'
    return None


def prepare(out,previous=DEFAULT_PREVIOUS,launch_path=qualified.DEFAULT_LAUNCH,packet=DATA,preservation=PRESERVATION):
    require(socket.gethostname()=='steve-TURIND8-2L2T','qualified lifecycle is restricted to the two-card host')
    with qualified.file_lock(qualified.HOST_LOCK),qualified.file_lock(qualified.MODEL_LOCK),qualified.file_lock(qualified.STAGE_LOCK):
        prior,artifacts=previous_receipts(previous,preservation)
        verified=validate_packet(packet)
        launch=read(launch_path);cold=qualified.derive_cold_launch(launch)
        require(qualified.effective_profile(read(Path(previous)/'server/launch.json'))==qualified.effective_profile(cold)
                and prior.get('model')==MODEL,'preserve previous exact cold profile and model')
        config={'schema':QUEUE_SCHEMA,'protocol':PROTOCOL,'packet':str(Path(packet).resolve()),
            'expected_trials':expected_trials(verified),'cache_policy':CACHE_POLICY,
            'prepared_at':qualified.now(),'hostname':socket.gethostname(),
            'fault_baseline_at':prior.get('fault_baseline_at',prior['prepared_at']),
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'protected_launch':str(Path(launch_path).resolve()),
            'previous_revision':{'directory':str(Path(previous).resolve()),'artifacts':artifacts},
            'admission':prior['full_source_admission'],'effective_profile':qualified.effective_profile(cold),
            'server_args':qualified.profile_args(cold),'port':18196,'model':MODEL,
            'expected_launch_identity':{k:launch[k] for k in ('overlay_sha256','reference_sha256','guard_sha256')},
            'guard_min_available_gib':1.6,'prelaunch_available_gib':11,'min_disk_free_gib':5,'max_wait_seconds':180,
            'dependency_sha256':dependencies(launch_path,launch,packet)}
        require(release_reason(config) is None,'protected work has not released the host')
        out.mkdir(parents=True,exist_ok=False)
        qualified.atomic(out/'queue.json',config)
        try:
            qualified.resource_check(config,out,qualified.load_helper())
            qualified.fault_check(config,out)
        except BaseException as error:
            qualified.status(out,'prepare-failed',error=str(error),device_actions=False)
            raise
        qualified.status(out,'prepared',protocol=PROTOCOL,device_actions=False)
        return config


def verify_results(out,config,launch):
    diagnostic=out/'diagnostic';summary=read(diagnostic/'summary.json')
    plan=read(Path(config['packet'])/'plan.json')
    identity={'endpoint':f"http://127.0.0.1:{config['port']}/v1",'model':config['model'],'launch_sha256':qualified.sha(launch)}
    require(summary.get('schema')=='full-source-summary.v1' and summary.get('protocol')==PROTOCOL
            and summary.get('measurement_kind')=='model' and summary.get('infrastructure_abort') is False,
            'full-source summary identity or infrastructure failure')
    require(type(summary.get('expected_trials')) is int and summary['expected_trials']==2
            and summary.get('unstarted_trials')==[]
            and qualified.same_json(summary.get('server_identity'),identity)
            and qualified.same_json(summary.get('source_code_sha256'),plan['source_code_sha256'])
            and summary.get('plan_sha256')==qualified.sha(Path(config['packet'])/'plan.json'),
            'full-source execution identity or plan binding differs')
    require(summary.get('speed_gate_passed') is False and summary.get('holdout_admitted') is False,
            'full-source screen cannot promote a speed or holdout claim')
    rows=summary.get('trials');expected=config['expected_trials']
    require(isinstance(rows,list) and len(rows)==2,'both planned outcomes must be retained')
    for row,planned in zip(rows,expected):
        require(all(row.get(k)==planned[k] for k in ('case_id','task_sha256','request_sha256','result_path')),
                'full-source summary row identity/order changed')
        require(row.get('status') in ('completed','failed'),'full-source trial did not terminate')
        native=read(diagnostic/planned['result_path'])
        require(native.get('schema')=='full-source-trial.v1' and native.get('protocol')==PROTOCOL
                and native.get('measurement_kind')=='model' and native.get('resumed') is False
                and native.get('status')==row['status'] and native.get('failure_kind')!='infrastructure'
                and qualified.same_json(native.get('server_identity'),identity)
                and qualified.same_json(native.get('source_code_sha256'),plan['source_code_sha256'])
                and all(qualified.same_json(native.get(k),v) for k,v in POLICY.items())
                and all(native.get(k)==planned[k] for k in planned),
                'full-source native identity/generation differs')
        require(row.get('result_sha256')==qualified.sha(diagnostic/planned['result_path'])
                and row.get('timing_sha256')==qualified.sha(diagnostic/planned['timing_path']),
                'full-source native/timing artifact binding differs')
    for state in ('completed','failed'):
        require(type(summary.get(state+'_trials')) is int and summary[state+'_trials']==sum(r['status']==state for r in rows),
                'full-source terminal counts are malformed')
    audit=qualified.run_evidence_audit(AUDITOR,out,config['packet'])
    require(audit.get('schema')=='full-source-native-audit.v1' and audit.get('protocol')==PROTOCOL
            and audit.get('output')==str(out.resolve()) and audit.get('measurement_kind')=='model'
            and audit.get('packet_plan_sha256')==qualified.sha(Path(config['packet'])/'plan.json')
            and audit.get('infrastructure_abort') is False,'independent full-source audit identity differs')
    for key,value in {'planned_trials':2,'incomplete_trials':0,'unstarted_trials':0,
                      'completed_trials':summary['completed_trials'],'failed_trials':summary['failed_trials']}.items():
        require(type(audit.get(key)) is int and audit[key]==value,'independent full-source outcome counts differ')
    require(audit.get('speed_gate_passed') is False and audit.get('holdout_admitted') is False,
            'independent full-source audit cannot promote claims')
    require(isinstance(audit.get('trials'),list) and len(audit['trials'])==2,'independent full-source rows missing')
    for row,planned,observed in zip(audit['trials'],expected,rows):
        require(all(row.get(k)==planned[k] for k in ('case_id','task_sha256','request_sha256','result_path'))
                and row.get('status')==observed['status']
                and row.get('result_sha256')==qualified.sha(diagnostic/planned['result_path'])
                and row.get('timing_sha256')==qualified.sha(diagnostic/planned['timing_path']),
                'independent full-source native binding differs')
        require(row.get('checkpoint_quality') is None and row.get('event_quality') is None,
                'direct answers have no intermediate-state quality measurement')
    qualified.atomic(out/'diagnostic-independent-audit.json',audit)
    return summary


def stop_owned(server,out,config,*,model_lease_held=False):
    attempted=False
    try:
        with nullcontext() if model_lease_held else qualified.file_lock(qualified.MODEL_LOCK):
            attempted=True
            qualified.atomic(out/'server-stop.json',server.stop())
            with qualified.file_lock(qualified.STAGE_LOCK):
                qualified.wait_available(config,out,qualified.load_helper(),monitor_faults=False)
            qualified.atomic(out/'cards-released.json',{'at':qualified.now(),'verified':True})
    except BaseException:
        if not attempted:
            qualified.atomic(out/'server-stop.json',server.stop())
        raise


def execute(out):
    config=read(out/'queue.json')
    require(config.get('schema')==QUEUE_SCHEMA and config.get('protocol')==PROTOCOL
            and qualified.same_json(config.get('cache_policy'),CACHE_POLICY),'wrong frozen full-source queue')
    with qualified.file_lock(qualified.HOST_LOCK),qualified.file_lock(out/'coordinator.lock'):
        require(not (out/'execution-started.json').exists(),'one-shot execution already started; no retry')
        require(read(out/'status.json').get('phase')=='prepared','preparation did not complete')
        qualified.atomic(out/'execution-started.json',{'at':qualified.now(),'pid':os.getpid()})
        server=None;failure=None;released=False;lease_held=False
        lease=ExitStack()
        try:
            verify_dependencies(config)
            require(qualified.same_json(expected_trials(validate_packet(config['packet'])),config['expected_trials']),
                    'frozen two-request packet changed')
            deadline=time.monotonic()+config['max_wait_seconds']
            while True:
                require(not qualified.STOP_REQUESTED,'stop requested while waiting')
                qualified.fault_check(config,out);reason=release_reason(config)
                if reason is None:break
                qualified.status(out,'waiting',reason=reason)
                require(time.monotonic()<deadline,'protected host did not release before deadline')
                time.sleep(3)
            # Keep the model lease continuous until the owned server is stopped.
            lease.enter_context(qualified.file_lock(qualified.MODEL_LOCK));lease_held=True
            with qualified.file_lock(qualified.STAGE_LOCK):
                qualified.resource_check(config,out,qualified.load_helper())
                qualified.status(out,'preflight')
                qualified.monitored_command(['bash',qualified.HEALTH],'preflight-health',out,config,
                                            env=qualified.health_env(),timeout=180)
                qualified.resource_check(config,out,qualified.load_helper())
            verify_dependencies(config)
            qualified.status(out,'launching-one-server')
            server=qualified.OwnedServer(out,config);server.wait_ready(out)
            launch=server.out/'launch.json';identity=read(launch)
            qualified.verify_cold_emission(identity)
            require(qualified.same_json(qualified.effective_profile(identity),config['effective_profile'])
                    and qualified.profile_args(identity)==config['server_args']
                    and all(identity.get(k)==v for k,v in config['expected_launch_identity'].items()),
                    'emitted server profile differs from frozen identity')
            base=f'http://127.0.0.1:{config["port"]}'
            qualified.status(out,'strict-quality-gate')
            qualified.monitored_command(['bash',qualified.STRICT],'strict',out,config,server=server,timeout=2400,
                env={'BASE_URL':base,'MODEL_NAME':config['model'],'OUT_DIR':str(out/'strict'),
                     'PROFILE_LABEL':'full-source-v1-cold-profile','ATTEMPT_LABEL':'full-source-one-server'})
            comparison=out/'strict-comparison.json'
            qualified.monitored_command([sys.executable,qualified.COMPARE,out/'strict',qualified.REFERENCE,'--output',comparison],
                'strict-compare',out,config,server=server,timeout=120)
            require(strict_passed(read(comparison)),'strict qualification failed; two-request client untouched')
            verify_dependencies(config)
            qualified.status(out,'full-source-screen',expected_trials=2)
            qualified.monitored_command([sys.executable,'-B',CLIENT,'--execute','--packet',config['packet'],
                '--out',out/'diagnostic','--endpoint',base+'/v1','--model',config['model'],'--identity',launch],
                'diagnostic',out,config,server=server,timeout=1500)
            verify_dependencies(config)
            summary=verify_results(out,config,launch)
            verify_dependencies(config)
            qualified.status(out,'client-complete',completed_trials=summary['completed_trials'],failed_trials=summary['failed_trials'])
        except BaseException as error:
            failure=error
            qualified.status(out,'failed',error=f'{type(error).__name__}: {error}')
        finally:
            if server is not None:
                try:
                    stop_owned(server,out,config,model_lease_held=lease_held)
                    released=True
                except BaseException as cleanup_error:
                    qualified.status(out,'cleanup-failed',error=str(cleanup_error),original_error=str(failure))
                    if failure is None:failure=cleanup_error
            # A client/transport failure still gets a postflight after safe release.
            # fault_check precedes the probe, so known GPU faults never trigger it.
            if released:
                try:
                    qualified.fault_check(config,out)
                    with qualified.file_lock(qualified.STAGE_LOCK):
                        qualified.resource_check(config,out,qualified.load_helper())
                        qualified.monitored_command(['bash',qualified.HEALTH],'postflight-health',out,config,
                            env=qualified.health_env(),timeout=180)
                    qualified.atomic(out/'postflight-health.exit.json',{'at':qualified.now(),'exit_code':0,
                        'command_sha256':qualified.sha(out/'postflight-health.command.json')})
                except BaseException as postflight_error:
                    qualified.status(out,'failed',error='postflight: '+str(postflight_error),original_error=str(failure))
                    if failure is None:failure=postflight_error
            lease.close()
        if failure is not None:
            if released and (out/'postflight-health.exit.json').is_file():
                qualified.status(out,'failed',error=f'{type(failure).__name__}: {failure}',cards_released=True,postflight_passed=True)
            raise failure
        qualified.status(out,'completed',cards_released=True,server_restarts=0,
            diagnostic_summary=str(out/'diagnostic/summary.json'),completed_trials=summary['completed_trials'],
            failed_trials=summary['failed_trials'],speed_gate_passed=False,holdout_admitted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--execute',action='store_true')
    parser.add_argument('--previous-run',type=Path,default=DEFAULT_PREVIOUS)
    parser.add_argument('--packet',type=Path,default=DATA)
    parser.add_argument('--qualified-launch',type=Path,default=qualified.DEFAULT_LAUNCH)
    parser.add_argument('--preservation',type=Path,default=PRESERVATION)
    args=parser.parse_args()
    def stop(*_):qualified.STOP_REQUESTED=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    if args.prepare:prepare(args.out.resolve(),args.previous_run,args.qualified_launch,args.packet,args.preservation)
    else:execute(args.out.resolve())


if __name__=='__main__':main()
