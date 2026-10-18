"""Every sealed view, every real chain window: CPU startup, never a device.

Shared K fixtures execute once (their argv has no selection). Native model
startup uses production parse/Engine/DraftRuntime and real dimensions; only
weight payloads/backend are mocked, exactly as full_shape.py. KD uses its
actual launcher command and selection projection. The old E1 command must fail.
"""
import json, os, subprocess, time, shutil, resource, gzip, textwrap, sys
from pathlib import Path
from types import SimpleNamespace
from build_engine import P, ROOT, B, sha, save, limits
from compile_turn import turn
from bundle_selection import views, selection
import full_shape
S=B/'startup103'
WINDOWS=('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128')

def build():
    full_shape.S=S
    generated=full_shape.generate()
    entry=r'''#include <cxxabi.h>
#define main unexecuted_model_main
#include "main.cpp"
#undef main
int main(int argc,char**argv){std::unique_ptr<Engine> e;std::unique_ptr<mtp36::DraftRuntime> draft;try{
 Options a=parse(argc,argv);fs::create_directories(a.output);
 if(a.pipeline_canary){require(a.mini&&a.pipeline_mini&&a.rank>=0,"canary startup flags");save(a.output/"result.json","{\"passed\":true,\"canary_pre_engine\":true}");return 0;}
 packet26::dispatch.load(a.dispatch.string());Weights w(a);
 auto p=pipeline::split(plan(w,a),a.rank,false,a.draft_rank,a.target_split);
 require(p.g.h==2560&&p.g.context==4096&&p.g.vocab==248320,"real production dimensions");
 e=std::make_unique<Engine>(w,a,p);e->initialize();
 std::unique_ptr<p105::Runtime> head_runtime;if(e->split_head())head_runtime=std::make_unique<p105::Runtime>(*e);
 if(!a.draft_capture.empty()){e->prepare_plan();draft=std::make_unique<mtp36::DraftRuntime>(*e);}
 else{if(a.rank==0)pipeline::banks(*e);else{e->prepare_plan();e->prepare_commands();}
  {pipeline::SpeculativeImage image(*e);if(a.mtp)draft=std::make_unique<mtp36::DraftRuntime>(*e);}}
 save(a.output/"census.json",e->dev(0).arena.census());
 save(a.output/"result.json","{\"passed\":true,\"device_executed\":false,\"context\":4096,\"hidden\":2560,\"vocab\":248320,\"prepared\":"+std::string(e->prepared_path?"true":"false")+"}");
 draft.reset();e->shutdown();e.reset();return 0;
 }catch(const std::exception& x){std::cerr<<x.what()<<'\n';draft.reset();if(e){try{e->shutdown();}catch(...){}e.reset();}return 1;}}
'''
    (S/'entry.cpp').write_text(entry)
    commands=json.loads((P/'engine-commands.json').read_text())
    base=next(r['command'] for r in commands if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
    base=[x for x in base if not x.startswith('-O')]+['-O0','-I'+str(P)]
    compile=[*base,'-c',str(S/'entry.cpp'),'-o',str(S/'entry.o')]
    link=list(next(r['command'] for r in commands if r['name']=='gnu-host-link'))
    link=[x for x in link if not x.endswith('/entry-main.o') and not x.endswith('own-rt-iq3-entry.cpp.o')]
    link.insert(link.index('-o'),str(S/'entry.o'));link[link.index('-o')+1]=str(S/'fixture')
    for label,cmd in [('compile',compile),('link',link)]:
        with turn(),(S/(label+'.log')).open('w') as log:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    return generated,[compile,link]

def native(cmd, *, old=False):
    # Only backend/payload mock binary, never a device binary.
    cmd=list(map(str,cmd));cmd[0]=str(S/'fixture')
    if '--authorized-device-window' in cmd:cmd.remove('--authorized-device-window')
    dest=Path(cmd[cmd.index('--output')+1])
    r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
    if old:
        assert r.returncode and any(message in r.stderr for message in ('p90 cached layout requires', 'p100 locality requires sealed')), r.stderr
        shutil.rmtree(dest,ignore_errors=True)
        return dict(returncode=r.returncode,error=r.stderr.strip(),command=cmd)
    assert r.returncode==0,r.stderr
    result=json.loads((dest/'result.json').read_text())
    artifacts={f.name:sha(f) for f in dest.iterdir() if f.is_file()}
    if (dest/'draft-kernel-choices.json').exists():
        draft=json.loads((dest/'draft-kernel-choices.json').read_text());draft.pop('selection_sha256')
        result['draft_kernel_identity']=draft
    if (dest/'census.json').exists():
        census=json.loads((dest/'census.json').read_text())
        result['allocation_bytes']=census['totals']['device']
        if '--draft-capture' in cmd:assert result['allocation_bytes']<4*1024**3
    shutil.rmtree(dest)
    return dict(command=cmd,result=result,artifacts=artifacts)

def shared_fixtures():
    import window as w
    watch=SimpleNamespace(check=lambda:None,mark_launched=lambda pid:None,latch=lambda e:None)
    rows={}
    # These are original CPU startup paths. No model mini-fixture substitutes
    # for KD or model ranks; K0's CPU branch explicitly has no host JIT analogue.
    w.admit_output=lambda *args:None  # scratch bounded below, no chain storage write
    for name in ('K0','K1a','K1b','K2'):
        dest=S/('shared-'+name)
        if dest.exists():
            archive=S/('prior-'+name+'-'+str(time.time_ns()));dest.rename(archive)
        dest.mkdir()
        a=SimpleNamespace(window=name,card=0,context=4096,seconds=14400 if name=='K2' else None,
                          dispatch=P/'dispatch-p45.json',cpu_rehearsal=True)
        started=time.monotonic()
        from unittest.mock import patch
        popen=subprocess.Popen
        def cpu_popen(cmd,**kwargs):
            cmd=list(cmd)
            # p49d's CPU entry explicitly refuses device timing. Exercise its
            # same exact full-shape startup without requesting a device timer.
            if '--timing' in cmd:cmd.remove('--timing')
            return popen(cmd,**kwargs)
        with patch.object(subprocess,'Popen',cpu_popen):
            receipts=w.run_fixtures(a,dest,dict(os.environ,OMP_NUM_THREADS='2'),watch)
        rows[name]=dict(receipts=receipts,seconds=time.monotonic()-started,
                        children=json.loads((dest/'children.json').read_text()))
        save(S/(name+'-startup.json'),rows[name]);shutil.rmtree(dest)
        print(name,'shared CPU fixture startup PASS',flush=True)
    return rows

def planned_commands(out):
    from unittest.mock import patch
    import bundle_selection
    from queue_runner import commands
    with patch.object(bundle_selection,'selected',return_value=dict(draft_rank=1,target_split=0)):
        return commands(out)

def window_options(name):
    """Execute the frozen window parser and native configuration statements.

    Operational leases/oracle receipts are verified by readiness, not mocked
    into a device claim here. The exact parser, suite-cap/retention guards and
    native argument construction below are read from the sealed window source.
    """
    import window as w
    from queue_runner import commands
    from unittest.mock import patch
    cmd=planned_commands(S/'chain')[name];cmd=cmd[cmd.index(str(P/'window.py'))+1:]
    source=(P/'window.py').read_text()
    namespace=dict(vars(w),cpu_rehearsal=False)
    begin=source.index('    p=argparse.ArgumentParser',source.index('def main('))
    end=source.index('    if a.plan:',begin)
    with patch.object(sys,'argv',['window.py',*cmd]):
        exec(textwrap.dedent(source[begin:end]),namespace)
    a=namespace['a']
    begin=source.index('    if a.window in SUITE_WINDOWS:',end)
    end=source.index('    environment=environment_gate()',begin)
    exec(textwrap.dedent(source[begin:end]),namespace)
    a.dispatch=P/'dispatch-speed6.json'
    return a,namespace

def model_args(name,target,out):
    import window as w
    a,namespace=window_options(name)
    namespace.update(out=out,build={'selection':{'selection_sha256':sha(target)}},
                     admission=None,seconds=w.watchdog(name,a.seconds or w.CONFIG[name][1],a.context))
    source=(P/'window.py').read_text()
    begin=source.index("            args=pp.parser().parse_args")
    end=source.index("            record['ldd_preflight']",begin)
    exec(textwrap.dedent(source[begin:end]),namespace)
    args=namespace['args'];args.native_nice=19  # CPU helper priority, only timing policy differs.
    if name=='W0p':args.canary=True;args.mini=True
    elif name in w.SUITE_WINDOWS:
        begin=source.index('                args.suite_manifest=a.suite_manifest')
        end=source.index('                r=pp.run',begin)
        exec(textwrap.dedent(source[begin:end]),namespace)
        manifest=json.loads(a.suite_manifest.read_text())
        args.input=ROOT/manifest['prompts'][0]['input_bundle']
    else:args.draft='mtp'  # W2m is the sole non-suite model window in this chain.
    return args

def rank_commands(name,target):
    """Capture real Transport argv, stopping before owner rendezvous/device work."""
    import chain_pipeline as pp
    from unittest.mock import patch
    out=S/'command-capture';out.mkdir()
    args=model_args(name,target,out)
    rows=[]
    def capture(cmd,**kwargs):
        assert cmd[:3]==['ionice','-c','3']
        cmd=cmd[3:];cmd[cmd.index('--selection')+1]=str(target)
        cmd[cmd.index('--output')+1]=str(S/'scratch')
        rows.append(cmd)
        return SimpleNamespace(pid=900000+len(rows))
    class Captured(Exception):pass
    transport=pp.Transport.__new__(pp.Transport)
    def done(*args,**kwargs):raise Captured()
    transport.receive=done
    try:
        with patch.object(subprocess,'Popen',capture):
            try:transport.__init__(args,out,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
            except Captured:pass
        assert len(rows)==2
        return rows
    finally:
        for stream in transport.logs:stream.close()
        for sock in transport.sockets:sock.close()
        transport.mapping.close();os.close(transport.stop_read);os.close(transport.stop_write)
        shutil.rmtree(out)

def main():
    limits();os.environ['OMP_NUM_THREADS']='2';started=time.monotonic()
    initial_sources={str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.py')}
    initial_sources.update({str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.hpp')})
    generated,commands=build()
    shared=shared_fixtures()
    # Exercise the actual W0p shared-memory handshake. The real run_rank returns
    # through run_pipe_canary before loading any selected Engine, for every view.
    import window as w
    target=S/'canary-selection.json';save(target,selection(next(iter(views().values()))))
    dest=S/'canary';dest.mkdir(exist_ok=True)
    args=model_args('W0p',target,dest);args.device=False;args.binary=B/'gnu-host/own-rt-iq3'
    watch=SimpleNamespace(check=lambda:None,mark_launched=lambda pid:None,latch=lambda error:None)
    w.concurrency_canary(args,dest,{'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'},watch)
    shared['W0p-protocol']=dict(files={str(f.relative_to(dest)):sha(f) for f in dest.rglob('*') if f.is_file()})
    shutil.rmtree(dest)
    print('W0p actual CPU canary handshake PASS',flush=True)
    from kd_reference import prepare,command
    from queue_runner import commands as windows
    from memory_plans import plan
    from memory_gate import configuration
    report=dict(passed=False,device_executed=False,model_payload_read=False,commands=commands,
                shared_fixtures=shared,runs=[],sources={})
    negative=None
    for label,v in views().items():
        target=S/'target.json';save(target,selection(v))
        ref,binding=prepare(target,sha(target),S)
        inp=json.loads((B/'input/input.json').read_text())
        a=SimpleNamespace(card=0,draft_rank=1,context=4096,input=B/'input',dispatch=P/'dispatch-speed6.json')
        root=S/'scratch'
        window_commands=planned_commands(S/'chain')
        for name in WINDOWS:
            configuration(plan(v),4096,1,0)
            window_options(name)
            row=dict(view=label,window=name,window_command=window_commands[name])
            if name in shared:row['shared_fixture']=name
            elif name=='KD':
                cmd=command(S/'fixture',a,P/'oracle/results/capture-incident-retrospective.tsv',inp,root,ref,binding['reference_selection_sha256'], -1)
                if negative is None and 'halfcache' in v[2]:
                    old=list(cmd);old[old.index('--selection')+1]=str(target);old[old.index('--selection-sha256')+1]=sha(target)
                    for flag in ('--draft-rank','--target-split','--memory'):
                        index=old.index(flag);del old[index:index+2]
                    negative=native(old,old=True)
                row['host']=native(cmd)
                row['device_startup_on_cpu']=native(command(S/'fixture',a,P/'oracle/results/capture-incident-retrospective.tsv',inp,root,ref,binding['reference_selection_sha256'],-1,device=True))
            else:
                row['ranks']=[native(cmd) for cmd in rank_commands(name,target)]
            report['runs'].append(row)
        current=[r for r in report['runs'] if r['view']==label]
        kd=next(r for r in current if r['window']=='KD')['host']['result']['draft_kernel_identity']
        for row in current:
            for rank in row.get('ranks',[]):
                if 'draft_kernel_identity' in rank['result']:
                    assert rank['result']['draft_kernel_identity']==kd, 'KD draft choices differ from selected resident draft'
        print(label,'all 11 windows PASS',flush=True)
    assert negative is not None
    files=[P/'startup103.py',P/'kd_reference.py',P/'kd_window103.py',P/'chain103.py',P/'full_shape.py',P/'window.py',P/'draft_window.py',P/'chain_pipeline.py',P/'queue_runner.py',P/'bundle_selection.py',P/'engine-commands.json',*generated,S/'fixture']
    from math_gate import closure
    files+=closure()
    files+=[B/'gnu-host'/entry['binary'] for shared_row in shared.values() for entry in shared_row.get('children',{}).get('entries',[])]
    files+=[P/'startup_receipt103.py',P/'oracle/results/suite-manifest.json',B/'gnu-host/own-rt-iq3']
    assert all(sha(ROOT/n)==h for n,h in initial_sources.items()), 'startup sources changed during gate'
    report['sources']={**initial_sources,**{str(f.relative_to(ROOT)):sha(f) for f in files}}
    report.update(passed=True,old_code_refusal=negative,seconds=time.monotonic()-started,
                  max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                  compositions=len(views()),windows_per_composition=11,total_windows=len(report['runs']))
    raw=json.dumps(report,sort_keys=True).encode()
    archive=P/'evidence/startup103-runs.json.gz';archive.write_bytes(gzip.compress(raw,mtime=0))
    summary={k:v for k,v in report.items() if k not in ('runs','shared_fixtures','commands')}
    summary['archive']=dict(path=str(archive.relative_to(ROOT)),sha256=sha(archive),uncompressed_sha256=__import__('hashlib').sha256(raw).hexdigest())
    save(P/'startup103.json',summary)
    print(json.dumps({k:report[k] for k in ('passed','seconds','max_rss_kib','total_windows')}),flush=True)
if __name__=='__main__':main()
