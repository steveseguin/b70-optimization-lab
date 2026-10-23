"""packet176 CPU gate for the process-wide --foreground-io option (no GPU, no model).

1. Byte equality: GNU and Intel host builds with --foreground-io kernel, copy and no flag
   reproduce the packet58aj parent's miniature step bytes and tokens.
2. Parser: every engine chain window's real argv (KD, W2m, WS, WS128x, WS128) is
   accepted with --foreground-io kernel and parses as kernel; without the flag it
   parses as copy (default); an unknown value refuses. K1a/K1b run the unchanged inherited
   p58-cache-fixtures binary (no engine, no token I/O path, no engine flags).
3. Old code: the parent packet58as gnu-host binary refuses the same argv
   ("unknown option --foreground-io") and accepts it once the flag is removed.
4. Refusals: --foreground-io with a bracket table (the bracket selects per view),
   with a draft-capture owner, and the parent poll/spin, packet174 spin/spin-kick
   and packet171b spin/spin-cq bracket orders.
"""
import json,resource,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
from build_engine import P,ROOT,sha,save,limits
from launch_env import environment
import suite_driver as D

def run(cmd):
    return subprocess.run(['ionice','-c3',*map(str,cmd)],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment())
PLAIN=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2')

def main():
    limits();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    build=json.loads((P/'evidence/build.json').read_text())
    new={m:P/'build'/m/'own-rt-iq3' for m in ('gnu-host','intel-host')}
    old=P.parent/'packet58as-onecard-spinwait/build/gnu-host/own-rt-iq3'
    for m,b in new.items():assert sha(b)==build['artifacts']['build/'+m+'/own-rt-iq3']
    records=dict(exactness=[],parser=[],old_binary=[],refusals=[],help=[])
    for label,b in (*new.items(),('packet58as-gnu-host',old)):
        cp=run([b,'--help']);assert cp.returncode==0
        has='--foreground-io' in cp.stdout.split()
        assert has==(label!='packet58as-gnu-host'),(label,has)
        records['help'].append(dict(binary=label,binary_sha256=sha(b),lists_foreground_io=has,default_copy_documented='(default:copy)' in cp.stdout))
    with tempfile.TemporaryDirectory(dir=P/'build',prefix='kernel-io-') as d:
        d=Path(d)
        base=['--mini','--pipeline-mini','--memory','resident','--cache-maintenance','overlap','--context','32','--tokens','8','--retain-steps','1-8','--lookups','resident','--hc','p60fusion','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--selection',P/'selection.json','--selection-sha256',sha(P/'selection.json')]
        parent=P.with_name('packet58aj-onecard-resident')/'build/gnu-host/own-rt-iq3'
        ref=d/'reference';cp=run([parent,*base,'--output',ref]);assert cp.returncode==0,cp.stderr[-2000:]
        result=json.loads((ref/'result.json').read_text())
        def files(o):return {str(f.relative_to(o)):sha(f) for f in o.glob('step*/*') if f.is_file()}
        expected=files(ref);assert expected
        for mode,b in new.items():
            for kick in ('kernel','copy',None):
                out=d/f'{mode}-{kick or "default"}';extra=['--foreground-io',kick] if kick else []
                cp=run([b,*base,*extra,'--output',out]);assert cp.returncode==0,(mode,kick,cp.stderr[-2000:])
                assert files(out)==expected,(mode,kick)
                assert json.loads((out/'result.json').read_text())['tokens']==result['tokens']
                records['exactness'].append(dict(compiler=mode,binary_sha256=sha(b),foreground_io=kick or 'default',step_files=len(expected),all_step_bytes_equal_parent=True,tokens_equal_parent=True))
        manifest=D.oracle_inputs()
        for name in ('KD','W2m','WS','WS128x','WS128'):
            out=d/('parse-'+name);out.mkdir();table=out/'suite-inputs.tsv';table.write_text('')
            actual=D.native_command(SimpleNamespace(window=name,view='down-tile16',miss_mode='zerocopy',output=out),manifest,table)
            argv=list(actual[3:]);argv.remove('--authorized-device-window');argv[argv.index('--native-nice')+1]='19'
            assert '--foreground-io' not in argv
            on=argv+['--foreground-io','kernel']
            seen={}
            for case,args,binary in (('kernel',on,new['gnu-host']),('default',argv,new['gnu-host']),('intel-kernel',on,new['intel-host'])):
                o=out/case;a=list(args);a[a.index('--output')+1]=str(o)
                cp=subprocess.run([str(binary),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment() if binary==new['intel-host'] else PLAIN)
                assert cp.returncode==0,(name,case,cp.stderr)
                receipt=json.loads((o/'parser.json').read_text())
                assert receipt['passed'] and receipt['device_executed'] is False and receipt['model_reads'] is False and receipt['views']==1
                seen[case]=receipt['foreground_io']
            assert seen==dict(kernel='kernel',default='copy',**{'intel-kernel':'kernel'}),seen
            bad=argv+['--foreground-io','bogus'];bad[bad.index('--output')+1]=str(out/'bogus')
            cp=subprocess.run([str(new['gnu-host']),'--p58r-parse-test',*bad],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=PLAIN)
            assert cp.returncode!=0 and 'foreground io dimension' in cp.stderr,cp.stderr
            records['parser'].append(dict(window=name,actual_native_argv=actual,parsed_foreground_io=seen,unknown_value_refused=True))
            o1,o2=out/'old-on',out/'old-without'
            a=list(on);a[a.index('--output')+1]=str(o1)
            cp=subprocess.run([str(old),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=PLAIN)
            assert cp.returncode!=0 and 'unknown option --foreground-io' in cp.stderr,cp.stderr
            a=list(argv);a[a.index('--output')+1]=str(o2)
            cp2=subprocess.run([str(old),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=PLAIN)
            assert cp2.returncode==0 and json.loads((o2/'parser.json').read_text())['views']==1,cp2.stderr
            records['old_binary'].append(dict(window=name,binary_sha256=sha(old),foreground_io_kernel_refused=True,error=cp.stderr.strip(),accepted_without_flag=True))
        tokens=d/'tokens';tokens.write_text('2 5 3 7 1\n');oracle=d/'oracle';oracle.write_text(' '.join(map(str,result['tokens']))+'\n')
        suite=d/'suite';suite.write_text(''.join(f'r{i} {tokens} {oracle}\n' for i in range(12)))
        def table(arms,path):
            path.write_text(''.join(f'{label} {P/"selection.json"} {sha(P/"selection.json")} overlap max {arm}\n' for label,arm in arms));return path
        good=table([('A0','spin'),('B0','spin-kio'),('A1','spin'),('B1','spin-kio'),('A2','spin')],d/'bracket')
        for kick in ('kernel','copy'):
            out=d/('conflict-'+kick);cp=run([new['gnu-host'],*base,'--suite-inputs',suite,'--bracket-inputs',good,'--foreground-io',kick,'--output',out])
            assert cp.returncode!=0 and 'bracket selects foreground io per view' in cp.stderr and not (out/'A0').exists(),cp.stderr[-1000:]
            records['refusals'].append(dict(case='bracket-with-foreground-io-'+kick,refused=True,error=cp.stderr.strip()[-200:]))
        for tag,arms in (('parent-poll-spin',[('A0','poll'),('B0','spin'),('A1','poll'),('B1','spin'),('A2','poll')]),
                         ('p171b-spin-cq',[('A0','spin'),('B0','spin-cq'),('A1','spin'),('B1','spin-cq'),('A2','spin')]),
                         ('p174-spin-kick',[('A0','spin'),('B0','spin-kick'),('A1','spin'),('B1','spin-kick'),('A2','spin')])):
            out=d/('order-'+tag);cp=run([new['gnu-host'],*base,'--suite-inputs',suite,'--bracket-inputs',table(arms,d/('t-'+tag)),'--output',out])
            assert cp.returncode!=0 and not (out/'A0').exists(),cp.stderr[-1000:]
            records['refusals'].append(dict(case='bracket-order-'+tag,refused=True,error=cp.stderr.strip()[-200:]))
        out=d/'draft';cp=run([new['gnu-host'],*base,'--foreground-io','kernel','--draft-capture',d/'draft-capture','--output',out])
        assert cp.returncode!=0 and 'foreground io applies to single-owner one-card request views' in cp.stderr,cp.stderr[-1000:]
        records['refusals'].append(dict(case='draft-capture-with-foreground-io',refused=True,error=cp.stderr.strip()[-200:]))
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    save(P/'evidence/kernel-io.json',dict(passed=True,device_executed=False,model_reads=False,fullshape_reads=False,
        parent_binary=dict(name='packet58aj gnu-host own-rt-iq3',parent_relpath=str(parent.relative_to(ROOT)),parent_digest=sha(parent)),
        old_code_binary=dict(name='packet58as gnu-host own-rt-iq3',parent_relpath=str(old.relative_to(ROOT)),parent_digest=sha(old)),
        default_foreground_io='copy',chain_windows=['KD','W2m','WS','WS128x','WS128'],k1_windows='unchanged inherited p58-cache-fixtures binary; no engine and no token I/O path; no engine flags in its argv',
        fails_on_old_code=True,records=records,peak_child_rss_bytes=rss))
    print('PASS foreground-io: byte equality kernel/copy/default (GNU+Intel), 5 engine window parsers, old-binary refusal, conflict/order/draft refusals')
if __name__=='__main__':
    import sys;sys.path.insert(0,str(P));main()
