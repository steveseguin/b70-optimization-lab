"""Exercise the bound host parser for every chain model window; no model load."""
import json,os,resource,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
import suite_driver as D
from seal import sha
P=Path(__file__).resolve().parent
R=P.parents[3]
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    binary=P/'build/gnu-host/own-rt-iq3';binding=json.loads((P/'parent-binding.json').read_text())
    assert sha(binary)==binding['native_artifacts']['build/gnu-host/own-rt-iq3']
    manifest=D.oracle_inputs();rows=[]
    with tempfile.TemporaryDirectory(prefix='parse-',dir=P/'build') as tmp:
        for name in ('KD','W2m','WS','WS128x','WS128'):
            out=Path(tmp)/name;out.mkdir()
            table=out/'suite-inputs.tsv';table.write_text('')
            actual=D.native_command(SimpleNamespace(window=name,view='down-tile16',miss_mode='zerocopy',output=out),manifest,table)
            command=[str(binary),'--p58r-parse-test',*actual[3:]]
            command.remove('--authorized-device-window')
            command[command.index('--native-nice')+1]='19'
            result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,
                env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
            assert result.returncode==0,(name,result.stderr)
            receipt=json.loads((out/'run/parser.json').read_text())
            assert receipt['passed'] and receipt['device_executed'] is False and receipt['model_reads'] is False
            assert receipt['views']==1 and receipt['cache_allocation_bytes']==21552729600
            from composition import FLAGS, check
            check(actual)
            refusals=[]
            for flag in FLAGS:
                invalid=list(command);invalid[invalid.index(flag)+1]='unknown'
                bad=subprocess.run(invalid,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,
                    env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
                assert bad.returncode!=0 and 'dimension' in bad.stderr or (bad.returncode!=0 and 'HC geometry' in bad.stderr),(flag,bad.stderr)
                refusals.append(flag)
            rows.append(dict(window=name,passed=True,invalid_hc_refused=True,invalid_composition_flags_refused=refusals,actual_native_argv=actual,parser_receipt=receipt))
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<4*1024**3
    row=dict(passed=True,device_executed=False,model_reads=False,fullshape_reads=False,records=rows,
        binary_sha256=sha(binary),peak_child_rss_bytes=rss,
        sources={str(f.relative_to(R)):sha(f) for f in (P/'native_parser_gate.py',P/'suite_driver.py',P/'views.py',P/'selection.json',P/'runtime-selection.json')})
    (P/'evidence/native-parser.json').write_text(json.dumps(row,indent=2)+'\n')
    print('5 real CPU native parsers pass; 25 invalid composition flags refused; no model read')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
