import json,resource,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,sha,save,limits
from views import selection,digest,write_table
ENV=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2')
def run(cmd,**kwargs):
    result=subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,capture_output=True,text=True,env=ENV,timeout=180,**kwargs)
    if result.returncode:raise RuntimeError(result.stdout[-1000:]+result.stderr[-3000:])
    return result
def miniature():
    binary=P/'build/gnu-host/own-rt-iq3';rows=[]
    with tempfile.TemporaryDirectory(prefix='reset-',dir=P/'build') as directory:
        tmp=Path(directory);tokens=tmp/'input.tokens';tokens.write_text('2 5 3 7 1\n')
        other=tmp/'other.tokens';other.write_text('7 2 8 3 2\n')
        base=[binary,'--mini','--pipeline-mini','--memory','resident','--context','32','--tokens','8','--retain-steps','1-8','--cache-maintenance','overlap','--cache-cap','max','--hc','p60fusion']
        fresh=tmp/'fresh';run([P.parent/'packet58ad-onecard-record/build/gnu-host/own-rt-iq3',*base[1:],'--input',tokens,'--selection',selection('tile16'),'--selection-sha256',digest('tile16'),'--output',fresh])
        expected=json.loads((fresh/'result.json').read_text())['tokens']
        fixture=lambda out:{str(f.relative_to(out)):sha(f) for f in sorted(out.glob('step*/*')) if f.is_file()}
        reference=fixture(fresh);assert reference
        expected_file=tmp/'oracle.txt';expected_file.write_text(' '.join(map(str,expected))+'\n')
        other_out=tmp/'fresh-other';run([*base,'--input',other,'--output',other_out])
        other_expected=tmp/'other-oracle.txt';other_expected.write_text(' '.join(map(str,json.loads((other_out/'result.json').read_text())['tokens']))+'\n')
        suite=tmp/'suite.tsv';suite.write_text(f'other {other} {other_expected}\na {tokens} {expected_file}\n')
        for view in ('p60fusion',):
            table=tmp/'bracket.tsv';write_table(table,view)
            for repeat in range(2):
                out=tmp/f'{view}-{repeat}'
                run([*base,'--suite-inputs',suite,'--bracket-inputs',table,'--selection',selection('tile16'),'--selection-sha256',digest('tile16'),'--output',out])
                identities=set()
                for label in ('A0','B0','A1','B1','A2'):
                    assert fixture(out/label/'a')==reference
                    assert json.loads((out/label/'a/result.json').read_text())['tokens']==expected
                    boundary=json.loads((out/label/'boundary.json').read_text());identities.add(boundary['arena_descriptors_sha256'])
                assert len(identities)==1
                rows.append(dict(view=view,repeat=repeat,passed=True,all_layer_bytes_equal=True))
                shutil.rmtree(out)
            print('miniature',view,'PASS',flush=True)
        # S0 now enables the existing split diagnostic; verify its exact bytes too.
        smoke_table=tmp/'smoke.tsv';write_table(smoke_table,'smoke')
        smoke_out=tmp/'smoke'
        run([*base,'--suite-inputs',suite,'--bracket-inputs',smoke_table,
             '--selection',selection('tile16'),'--selection-sha256',digest('tile16'),
             '--output',smoke_out])
        assert fixture(smoke_out/'S0/a')==reference
        assert json.loads((smoke_out/'S0/a/result.json').read_text())['tokens']==expected
        rows.append(dict(view='smoke',passed=True,all_layer_bytes_equal=True))
        # Wrong oracle fails during A0; no B0 request is allowed to run.
        expected_file.write_text(str((expected[0]+1)%32)+'\n')
        out=tmp/'bad-oracle'
        result=subprocess.run(list(map(str,[*base,'--suite-inputs',suite,'--bracket-inputs',table,'--selection',selection('tile16'),'--selection-sha256',digest('tile16'),'--output',out])),stdin=subprocess.DEVNULL,capture_output=True,text=True,env=ENV,timeout=60)
        assert result.returncode!=0 and 'oracle token mismatch' in result.stderr and not (out/'B0').exists()
        proof=json.loads((out/'receipt.json').read_text());assert not proof['passed'] and proof['safe_to_exit']
    save(P/'evidence/reset-gate.json',dict(passed=True,device_executed=False,synthetic_only=True,records=rows,
        binary_sha256=sha(binary),parent_binary_sha256=sha(P.parent/'packet58ad-onecard-record/build/gnu-host/own-rt-iq3'),compared_files_per_request=len(reference),oracle_negative_passed=True))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));limits();miniature()
