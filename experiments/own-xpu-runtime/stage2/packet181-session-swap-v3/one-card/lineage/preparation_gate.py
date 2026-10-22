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
        with compiler_turn(),(work/(name+'.log')).open('w') as log:
            subprocess.run(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3)))
        commands.append(command)
    failed=P/'screen/evidence/card0-58aj-screen-a/smoke/WSCREEN/run/receipt.json'
    argv=json.loads(failed.read_text())['command'][2:]+['--wait-seconds','300']
    output=P/'evidence/packet58ajb-preparation-d';assert not output.exists()
    command=[str(work/'prepare-probe'),*argv[1:]]
    env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib',ENTRY_PREPARE_OUTPUT=str(output))
    cp=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env)
    (P/'evidence/packet58ajb-preparation.log').write_text(cp.stdout+cp.stderr)
    assert cp.returncode==0,cp.stderr[-2500:]
    row=json.loads((output/'preparation.json').read_text())
    row.update(command=command,real_device_argv=argv,build_commands=commands,binary_sha256=sha(work/'prepare-probe'),
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        substitutions=['CPU transport; no SYCL device creation','opaque large allocations; actual small controls/staging','synthetic embedding bytes and 272 PLE rows with production packed widths','nice19 observation in parser; original nice0 argv retained','output redirected through ENTRY_PREPARE_OUTPUT'],
        shared_probe_unavailable='rehearse_entry requires --rank in argv, but this one-card real argv has no --rank; sandbox also cannot admit the private 4 MiB RoPE table. Do not fabricate rank argv or bypass the sandbox.')
    assert row['peak_child_rss_bytes']<4*1024**3
    save(P/'evidence/packet58ajb-preparation.json',row)
    print('CPU device-define preparation PASS',row['prepared'],row['issued'],row['peak_child_rss_bytes'],flush=True)
if __name__=='__main__':
    main() # Probe reserves disjoint virtual extents; only bounded small buffers are touched.
