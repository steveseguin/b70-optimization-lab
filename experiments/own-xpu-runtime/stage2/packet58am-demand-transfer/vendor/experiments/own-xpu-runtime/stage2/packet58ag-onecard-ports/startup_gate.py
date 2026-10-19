"""Replay the assembled native argv through the real parser, without weights."""
import json,os,resource,subprocess,tempfile
from pathlib import Path
from types import SimpleNamespace
import suite_driver as D
from views import P,VIEWS,write_table
from build_engine import limits,save,sha

def main():
    limits();manifest=D.oracle_inputs();rows=[];negative_rows=[]
    binary=P/'build/gnu-host/own-rt-iq3'
    with tempfile.TemporaryDirectory(prefix='parser-',dir=P/'build') as directory:
        tmp=Path(directory)
        for view in VIEWS[1:]:
            for miss in ('zerocopy',):
                out=tmp/(view+'-'+miss);out.mkdir()
                table=out/'suite-inputs.tsv';table.write_text('')
                write_table(out/'bracket-inputs.tsv',view)
                args=SimpleNamespace(window='WSCREEN',view=view,miss_mode=miss,output=out)
                actual=D.native_command(args,manifest,table)
                command=[str(binary),'--p58r-parse-test',*actual[3:]]
                command.remove('--authorized-device-window')
                command[command.index('--native-nice')+1]='19'
                result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,
                    env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'),timeout=60)
                assert result.returncode==0,result.stderr
                receipt=json.loads((out/'run/parser.json').read_text());assert receipt['passed']
                assert receipt['views']==(1 if view=='smoke' else 5) and receipt['cache_allocation_bytes']==21552729600
                rows.append(dict(view=view,miss_path=miss,passed=True,actual_native_argv=actual,cpu_parser_argv=command,
                    changes='host-only parse switch; device authorization removed; nice0 declaration changed to actual nice19; no Weights/Engine constructed'))
                # Same real parser refuses unknown flags before any allocation.
                negative=subprocess.run([*command,'--other-fusion','unknown'],stdin=subprocess.DEVNULL,capture_output=True,text=True,
                    env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'),timeout=60)
                assert negative.returncode!=0 and 'fusion dimension' in negative.stderr
                negative_rows.append(dict(view=view,miss_path=miss,case='unsupported-fusion',passed=True))
                original=(out/'bracket-inputs.tsv').read_text()
                lines=original.splitlines()
                invalid={
                    'truncated':'\n'.join(lines[:-1])+'\n',
                    'reordered':('\n'.join([lines[1],lines[0],*lines[2:]])+'\n') if len(lines)>1 else original.replace('S0','A0'),
                    'tampered-hash':original.replace(lines[0].split()[2],'0'*64),
                }
                for case,bad in invalid.items():
                    (out/'bracket-inputs.tsv').write_text(bad)
                    negative=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,
                        env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'),timeout=60)
                    assert negative.returncode!=0 and 'fresh parser output required' not in negative.stderr,(case,negative.stderr)
                    negative_rows.append(dict(view=view,miss_path=miss,case=case,passed=True,error=negative.stderr.strip()))
                (out/'bracket-inputs.tsv').write_text(original)
    save(P/'evidence/startup-cpu.json',dict(passed=True,device_executed=False,checks=len(rows),records=rows,
        binary_sha256=sha(binary),fullshape_receipt_sha256=sha(P/'evidence/fullshape-submit-cpu.json'),negative_records=negative_rows))
    print(len(rows),'real native parser paths and',len(negative_rows),'negative cases PASS')

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    main()
