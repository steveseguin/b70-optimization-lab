"""packet58asd CPU gate for the process-wide --wait-policy option (no GPU, no model).

1. Byte equality: GNU and Intel host builds with --wait-policy spin, poll and no
   flag reproduce the packet58aj parent's miniature step bytes and tokens.
2. Parser: every chain model window's real argv is accepted with spin; the same
   argv without the flag parses as poll (the default); an unknown value refuses.
3. The bracket binary refuses the same argv ("unknown option --wait-policy") and
   accepts it once the flag is removed: the flag is the only interface change.
4. A supplied policy that conflicts with a bracket view, or a draft-capture
   owner that bypasses the view loop, is refused before any request.
"""
import json,os,resource,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
from build_engine import P,ROOT,sha,save,limits
from launch_env import environment
import suite_driver as D

def run(cmd):
    return subprocess.run(['ionice','-c3',*map(str,cmd)],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment())

def main():
    limits();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    build=json.loads((P/'evidence/build.json').read_text())
    new={m:P/'build'/m/'own-rt-iq3' for m in ('gnu-host','intel-host')}
    old=P/'build/bracket/gnu-host/own-rt-iq3'
    for m,b in new.items():assert sha(b)==build['artifacts']['build/'+m+'/own-rt-iq3']
    bracket={r['name']:r['parent_digest'] for r in build['bracket_native']}
    assert sha(old)==bracket['build/gnu-host/own-rt-iq3']
    records=dict(exactness=[],parser=[],old_binary=[],refusals=[],help=[])
    for label,b in (*new.items(),('bracket-gnu-host',old)):
        cp=run([b,'--help']);assert cp.returncode==0
        has='--wait-policy' in cp.stdout.split()
        assert has==(label!='bracket-gnu-host'),(label,has)
        records['help'].append(dict(binary=label,binary_sha256=sha(b),lists_wait_policy=has,default_poll_documented='(default:poll)' in cp.stdout))
    with tempfile.TemporaryDirectory(dir=P/'build',prefix='wait-policy-') as d:
        d=Path(d)
        base=['--mini','--pipeline-mini','--memory','resident','--cache-maintenance','overlap','--context','32','--tokens','8','--retain-steps','1-8','--lookups','resident','--hc','p60fusion','--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground','--selection',P/'selection.json','--selection-sha256',sha(P/'selection.json')]
        parent=P.with_name('packet58aj-onecard-resident')/'build/gnu-host/own-rt-iq3'
        ref=d/'reference';cp=run([parent,*base,'--output',ref]);assert cp.returncode==0,cp.stderr[-2000:]
        result=json.loads((ref/'result.json').read_text())
        def files(o):return {str(f.relative_to(o)):sha(f) for f in o.glob('step*/*') if f.is_file()}
        expected=files(ref);assert expected
        for mode,b in new.items():
            for policy in ('spin','poll',None):
                out=d/f'{mode}-{policy or "default"}';extra=['--wait-policy',policy] if policy else []
                cp=run([b,*base,*extra,'--output',out]);assert cp.returncode==0,(mode,policy,cp.stderr[-2000:])
                assert files(out)==expected,(mode,policy)
                assert json.loads((out/'result.json').read_text())['tokens']==result['tokens']
                records['exactness'].append(dict(compiler=mode,binary_sha256=sha(b),wait_policy=policy or 'default',step_files=len(expected),all_step_bytes_equal_parent=True,tokens_equal_parent=True))
        manifest=D.oracle_inputs()
        for name in ('KD','W2m','WS','WS128x','WS128'):
            out=d/('parse-'+name);out.mkdir();table=out/'suite-inputs.tsv';table.write_text('')
            actual=D.native_command(SimpleNamespace(window=name,view='down-tile16',miss_mode='zerocopy',output=out),manifest,table)
            assert actual[actual.index('--wait-policy')+1]=='spin'
            argv=list(actual[3:]);argv.remove('--authorized-device-window');argv[argv.index('--native-nice')+1]='19'
            i=argv.index('--wait-policy');without=argv[:i]+argv[i+2:]
            seen={}
            for case,args,binary in (('spin',argv,new['gnu-host']),('default',without,new['gnu-host']),('intel-spin',argv,new['intel-host'])):
                o=out/case;a=list(args);a[a.index('--output')+1]=str(o)
                cp=subprocess.run([str(binary),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=environment() if binary==new['intel-host'] else dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
                assert cp.returncode==0,(name,case,cp.stderr)
                receipt=json.loads((o/'parser.json').read_text())
                assert receipt['passed'] and receipt['device_executed'] is False and receipt['model_reads'] is False and receipt['views']==1
                seen[case]=receipt['wait_policy']
            assert seen==dict(spin='spin',default='poll',**{'intel-spin':'spin'}),seen
            bad=list(argv);bad[bad.index('--wait-policy')+1]='bogus';bad[bad.index('--output')+1]=str(out/'bogus')
            cp=subprocess.run([str(new['gnu-host']),'--p58r-parse-test',*bad],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
            assert cp.returncode!=0 and 'wait policy dimension' in cp.stderr,cp.stderr
            records['parser'].append(dict(window=name,actual_native_argv=actual,parsed_wait_policy=seen,unknown_value_refused=True))
            # The bracket binary has the same parser except for the new option.
            o1,o2=out/'old-spin',out/'old-without'
            a=list(argv);a[a.index('--output')+1]=str(o1)
            cp=subprocess.run([str(old),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
            assert cp.returncode!=0 and 'unknown option --wait-policy' in cp.stderr,cp.stderr
            a=list(without);a[a.index('--output')+1]=str(o2)
            cp2=subprocess.run([str(old),'--p58r-parse-test',*a],stdin=subprocess.DEVNULL,capture_output=True,text=True,env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
            assert cp2.returncode==0 and json.loads((o2/'parser.json').read_text())['views']==1,cp2.stderr
            records['old_binary'].append(dict(window=name,binary_sha256=sha(old),wait_policy_spin_refused=True,error=cp.stderr.strip(),accepted_without_flag=True))
        tokens=d/'tokens';tokens.write_text('2 5 3 7 1\n');oracle=d/'oracle';oracle.write_text(' '.join(map(str,result['tokens']))+'\n')
        suite=d/'suite';suite.write_text(''.join(f'r{i} {tokens} {oracle}\n' for i in range(12)))
        table=d/'bracket';arms=[('A0','poll'),('B0','spin'),('A1','poll'),('B1','spin'),('A2','poll')]
        table.write_text(''.join(f'{label} {P/"selection.json"} {sha(P/"selection.json")} overlap max {arm}\n' for label,arm in arms))
        for policy in ('spin','poll'):
            out=d/('conflict-'+policy);cp=run([new['gnu-host'],*base,'--suite-inputs',suite,'--bracket-inputs',table,'--wait-policy',policy,'--output',out])
            assert cp.returncode!=0 and 'wait policy conflicts with bracket view' in cp.stderr and not (out/'A0').exists(),cp.stderr[-1000:]
            records['refusals'].append(dict(case='bracket-conflict-'+policy,refused=True,error=cp.stderr.strip()[-200:]))
        out=d/'draft';cp=run([new['gnu-host'],*base,'--wait-policy','spin','--draft-capture',d/'draft-capture','--output',out])
        assert cp.returncode!=0 and 'wait policy applies to single-owner request views' in cp.stderr,cp.stderr[-1000:]
        records['refusals'].append(dict(case='draft-capture-with-policy',refused=True,error=cp.stderr.strip()[-200:]))
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    save(P/'evidence/wait-policy.json',dict(passed=True,device_executed=False,model_reads=False,fullshape_reads=False,revision='packet58asd',
        parent_binary=dict(name='packet58aj gnu-host own-rt-iq3',parent_relpath=str(parent.relative_to(ROOT)),parent_digest=sha(parent)),
        default_wait_policy='poll',chain_windows=['KD','W2m','WS','WS128x','WS128'],k1_windows='unchanged inherited K1 fixture; no wait-policy flag',
        records=records,peak_child_rss_bytes=rss))
    print('PASS wait-policy: byte equality spin/poll/default (GNU+Intel), 5 window parsers, old-binary refusal, conflict/draft refusals')
if __name__=='__main__':main()
