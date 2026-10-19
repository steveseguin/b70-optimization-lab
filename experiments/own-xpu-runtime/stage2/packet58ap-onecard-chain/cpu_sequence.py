"""Execute each real native argv on CPU; actual parsers, preparation and sensors."""
import argparse,io,json,os,resource,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import queue_runner as Q
import suite_driver as D
import window as W
import stream_sensor as SENSOR
from launch_env import environment
from seal import sha,save
P=Path(__file__).resolve().parent
def run(cmd,log,trace=None,limit=False):
    if trace:cmd=['/usr/bin/strace','-f','-e','trace=openat,ioctl','-o',str(trace),*cmd]
    with log.open('w') as out:
        cp=subprocess.run(cmd,env=environment(),stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,
            preexec_fn=(lambda:resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))) if limit else None)
    assert cp.returncode==0,(cmd[:3],log.read_text()[-3000:])
    if trace:
        text=trace.read_text();assert not any(s in text for s in ('/dev/dri','/dev/accel','.gguf','/mnt/usb-models','/mnt/raid-models')),'device/model path opened'
def sensors(out,manifest,cap):
    # These are synthetic streams, never speed evidence. Timing values deliberately
    # have no meaningful duration: in-run sensors must not impose a speed verdict.
    for entry in manifest['prompts']:
        folder=out/'run'/entry['prompt_id'];folder.mkdir(parents=True)
        tokens=D.CHECK.token_record(D.ORACLE/'results'/entry['prompt_id'])[:cap]
        result=dict(arithmetic=D.ARITHMETIC,passed=True,cached_tokens=0,gpu_count=1,decode_mode='plain',context=4096,tokens=tokens,requested_max_new=cap,prompt_tokens=entry['prompt_tokens'],prefill_ms=-123,timing_rows=[dict(completed_monotonic=0) for _ in tokens])
        save(folder/'result.json',result);save(folder/'reset.json',dict(passed=True,cached_tokens=0,allocation_ids_preserved=True))
        def stream(leaf,rows):(folder/leaf).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        stream('timings.jsonl',[dict(kind='generated_token',generated_index=i+1,token_id=t,wall_ms=-999,prepare_ms=-1,wait_ms=-1) for i,t in enumerate(tokens)])
        stream('prefill-timings.jsonl',[dict(kind='prefill_token',token_index=i,wall_ms=-999,prepare_ms=-1,wait_ms=-1) for i in range(entry['prompt_tokens']-1)])
        save(folder/'lookup-request-complete.json',dict(passed=True))
    checked=set();r=SENSOR.partial(out,manifest,checked,cap,final=True)
    assert len(checked)==len(manifest['prompts'])
    folder=out/'run'/manifest['prompts'][0]['prompt_id'];path=folder/'timings.jsonl';original=path.read_text()
    path.write_text(original.rstrip('\n'))
    try:SENSOR.partial(out,manifest,set(),cap,final=True)
    except ValueError:pass
    else:raise AssertionError('truncated stream accepted')
    path.write_text(original)
    result=json.loads((folder/'result.json').read_text());result['tokens'][0]=-1;save(folder/'result.json',result)
    try:SENSOR.partial(out,manifest,set(),cap,final=True)
    except ValueError:pass
    else:raise AssertionError('wrong exact token accepted')
    return dict(r,synthetic=True,truncated_stream_refused=True,wrong_token_refused=True)
def memory_sensors(work,name):
    budget=W.M.window_plan(name);full=not name.startswith('K1')
    tracker=W.PinnedExpertProgress(work/'synthetic-progress.jsonl',budget) if full else None
    pinned=0
    if tracker:
        (work/'synthetic-progress.jsonl').write_text(''.join(json.dumps(dict(phase='pinned-expert',name=k,bytes=v))+'\n' for k,v in tracker.expected.items()))
        pinned=tracker.read()
    observations=[]
    for available,shadow,expected in ((W.M.HOST_RESERVE,0,True),(W.M.HOST_RESERVE-1,0,False),(W.M.HOST_RESERVE,4*1024**3+1,False)):
        log=io.StringIO()
        with patch.object(W.SUPPORT,'process_tree_anon',return_value=dict(root_seen=True,anonymous_bytes=0)),patch.object(W.M,'meminfo',return_value=dict(MemAvailable=available,GPUActive=pinned+shadow)):
            try:W.live_memory_sensor(999999,budget=budget,full_model=full,pinned_progress=tracker,sample_log=log);passed=True
            except ValueError:passed=False
        assert passed==expected
        observations.append(dict(accepted=passed,expected=expected,sample=json.loads(log.getvalue())))
    return dict(passed=True,synthetic=True,real_progress_reader=full,real_live_memory_sensor=True,observations=observations)
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    ap=argparse.ArgumentParser();ap.add_argument('--revision',default='final');a=ap.parse_args()
    assert a.revision.isalnum(),'simple revision suffix required'
    manifest=D.oracle_inputs();records=[];root=P/('evidence/cpu-sequence-'+a.revision);root.mkdir()
    for name in Q.ORDER:
        work=root/name;work.mkdir();cap=8 if name in ('KD','W2m') else 128
        subset=dict(manifest,prompts=manifest['prompts'][:1] if cap==8 else manifest['prompts'])
        table=work/'suite.tsv';table.write_text(''.join(f"{e['prompt_id']} {D.ROOT/e['input_bundle']/'tokens.txt'}\n" for e in subset['prompts']))
        if name.startswith('K1'):
            cmd=W.native_command(SimpleNamespace(window='K1',view='down-tile16'),work,'zero-copy')
        else:cmd=D.native_command(SimpleNamespace(window=name,view='down-tile16',miss_mode='zerocopy',output=work),manifest,table)[2:]
        help_run=subprocess.run([cmd[0],'--help'],env=environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True)
        assert help_run.returncode==0
        flags=[s for s in cmd[1:] if s.startswith('--')];assert all(f in help_run.stdout.split() for f in flags),(name,flags,help_run.stdout)
        probe=[*cmd,'--cpu-preparation-probe'];trace=work/'probe.strace'
        run(probe,work/'probe.log',trace,limit=name.startswith('K1'))
        report=json.loads((work/'run'/('k1.json' if name.startswith('K1') else 'preparation.json')).read_text())
        assert report['passed'] and not report['device_executed']
        reset=None
        if name.startswith('K1'):
            assert report['exact_output_sha256']==json.loads((P/'k1-cpu.json').read_text())['exact_output_sha256']
            assert report['iterations']==20
            synthetic=dict(report,device_executed=True)
            W.k1_summary(synthetic)  # real sensor, explicitly synthetic device envelope
        else:
            assert int(cmd[cmd.index('--wait-seconds')+1])>=300
            # The inherited probe selects demand only for named B0/B1 views.
            # Exercise both candidate resets separately, with the same native
            # arguments plus the explicitly labeled CPU-only five-view table.
            bracket=work/'candidate-reset.tsv'
            sel=cmd[cmd.index('--selection')+1];digest=cmd[cmd.index('--selection-sha256')+1]
            bracket.write_text(''.join(f'{label} {sel} {digest} overlap max p60fusion\n' for label in ('A0','B0','A1','B1','A2')))
            reset_cmd=list(probe);reset_cmd[reset_cmd.index('--max-new')+1]='128';reset_cmd[reset_cmd.index('--retain-steps')+1]='none';reset_cmd+=['--bracket-inputs',str(bracket)];reset_cmd[reset_cmd.index('--output')+1]=str(work/'demand-reset')
            run(reset_cmd,work/'reset.log',work/'reset.strace')
            reset=json.loads((work/'demand-reset/preparation.json').read_text());assert reset['passed'] and reset['views']==5 and reset['router_hooks']==480
            sensor=sensors(work/'synthetic',subset,cap)
        records.append(dict(window=name,passed=True,real_native_argv=cmd,probe_argv=probe,environment=environment(),binary_sha256=sha(Path(cmd[0])),all_flags_in_binary_help=True,real_native_parser=True,preparation=report,demand_reset=reset,sensors=dict(k1_summary_passed=True,synthetic_device_envelope=True) if name.startswith('K1') else sensor,memory_sensors=memory_sensors(work,name),no_model_or_device_open=True,trace_sha256=sha(trace)))
        print(name,'CPU real parser/preparation and sensors PASS',flush=True)
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    save(P/'evidence/cpu-sequence.json',dict(passed=True,device_executed=False,order=list(Q.ORDER),records=records,peak_child_rss_bytes=rss,model_payload_reads=False,services_started=False,probe_limitations='CPU transport/storage/kernel execution substituted; supplemental candidate resets use the fixed five-view table at cap128/retain-none because the inherited single-view probe internally selects off. Actual seven window argv also run unchanged with only the CPU preparation switch. No GPU correctness or speed claim.',sources={str(f.relative_to(P)):sha(f) for f in (Path(__file__),P/'stream_sensor.py',P/'demand_analyze.py',P/'suite_driver.py',P/'window.py',P/'composition.py')}))
if __name__=='__main__':main()
