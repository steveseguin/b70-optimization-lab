"""Real device-define entry preparation on a bounded CPU transport, never a GPU."""
import json,os,resource,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,compiler_turn,sha,save,limits

def main():
    limits()
    work=B/'preparation';work.mkdir(exist_ok=True)
    text=(P/'native/generated/main.cpp').read_text()
    old='static constexpr bool allocation_probe=false, legacy_pointer_probe=false;'
    assert text.count(old)==1
    text=text.replace(old,'bool allocation_probe=false, legacy_pointer_probe=false;')
    old='getpriority(PRIO_PROCESS, 0) == a.native_nice'
    assert text.count(old)==1
    text=text.replace(old,'getpriority(PRIO_PROCESS, 0) == 19 /* CPU probe: observed priority only */')
    # packet176: the probe compiled inside build_engine's single compile turn is reused when its
    # generated source is byte-identical (resume after a non-compile failure); never a second compile.
    reuse=os.environ.get('P176_REUSE_PROBE')=='1' and (work/'prepare-probe').is_file() and (work/'probe-main.cpp').is_file() and (work/'probe-main.cpp').read_text()==text
    (work/'probe-main.cpp').write_text(text)
    original=json.loads((P/'lineage/58ag-build-commands.json').read_text())
    oldroot=str(P.parent/'packet58ag-onecard-ports');commands=[]
    for name in ('device-entry-main','device-own-rt-iq3'):
        command=[s.replace(oldroot,str(P)) for s in next(r['command'] for r in original if r['name']==name)]
        if name.endswith('entry-main'):
            command[-1]=str(P/'native/preparation_probe.cpp')
            command.insert(1,'-I'+str(work));command[command.index('-o')+1]=str(work/'probe.o');command[command.index('-MF')+1]=str(work/'probe.d')
        else:
            command=[s for s in command if not s.endswith('/single_device.o') and not s.endswith('/own-rt-iq3-entry.cpp.o')]
            command=[str(work/'probe.o') if s==str(B/'device/entry-main.o') else s for s in command]
            command[command.index('-o')+1]=str(work/'prepare-probe')
        if not reuse:
         with compiler_turn(),(work/(name+'.log')).open('w') as log:
            subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
        commands.append(command)
    sys_path=str(P/'screen');import sys
    sys.path.insert(0,sys_path)
    import suite_driver as D, views as V
    from types import SimpleNamespace
    manifest=D.oracle_inputs();inputroot=B/'preparation/inputs';inputroot.mkdir(exist_ok=True)
    V.write_table(inputroot/'bracket-inputs.tsv','resident')
    table=inputroot/'suite-inputs.tsv';table.write_text('')
    args=SimpleNamespace(view='resident',miss_mode='zerocopy',window='WSCREEN',output=inputroot,cache_maintenance='overlap')
    argv=D.native_command(args,manifest,table)[2:]
    output=P/'evidence/preparation-sequence';assert not output.exists()
    command=[str(work/'prepare-probe'),*argv[1:]]
    from launch_env import environment
    env=environment();env['ENTRY_PREPARE_OUTPUT']=str(output)
    # Full-shape CPU transport work also honors the coordinator's timing hold.
    with compiler_turn():
        cp=subprocess.run(['ionice','-c3',*command],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env)
    (P/'evidence/preparation-sequence.log').write_text(cp.stdout+cp.stderr)
    assert cp.returncode==0,cp.stderr[-2500:]
    row=json.loads((output/'preparation.json').read_text())
    row.update(command=command,real_device_argv=argv,build_commands=commands,binary_sha256=sha(work/'prepare-probe'),target_binary_sha256=sha(P/'build/device/own-rt-iq3'),native_source_sha256=sha(P/'native/generated/main.cpp'),probe_source_sha256=sha(P/'native/preparation_probe.cpp'),
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        substitutions=['CPU transport; no SYCL device creation','opaque large allocations; actual small controls/staging','synthetic embedding bytes and 272 PLE rows with production packed widths','nice19 observation in parser; original nice0 argv retained','output redirected through ENTRY_PREPARE_OUTPUT'],
        shared_probe_unavailable='rehearse_entry requires --rank in argv, but this one-card real argv has no --rank; sandbox also cannot admit the private 4 MiB RoPE table. Do not fabricate rank argv or bypass the sandbox.')
    sensors=list(output.glob('*/*/host-memory.jsonl'))
    assert len(sensors)==60
    for f in sensors:
        values=[json.loads(x) for x in f.read_text().splitlines()]
        assert [v['phase'] for v in values]==['before_reset','after_reset'] and all(v['MemAvailable']>0 for v in values)
    view_sensors=list(output.glob('*/host-memory.jsonl'))
    assert len(view_sensors)==5
    for f in view_sensors:
        assert [json.loads(x)['phase'] for x in f.read_text().splitlines()]==['before_view_reset','after_view_reset']
    row.update(real_arm_sequence=True,real_reset_sensors=130,view_resets=5,requests=60,probe_reused_from_single_compile_turn=bool(reuse))
    assert row['peak_child_rss_bytes']<4*1024**3
    save(P/'evidence/preparation.json',row)
    print('CPU device-define preparation PASS',row['prepared'],row['issued'],row['peak_child_rss_bytes'],flush=True)
if __name__=='__main__':
    main() # Probe reserves disjoint virtual extents; only bounded small buffers are touched.
