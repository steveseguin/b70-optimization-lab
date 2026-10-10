#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU fake Runtime: matched145 and169 pairs; ten mocked client preflights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

LANE = Path(__file__).resolve().parents[2]
HERE = LANE / 'recovery/20261010-continuation134-stream'
OUT = Path(__file__).resolve().parent / 'continuation134-tests'
PYTHON = '/home/steve/.venvs/ltx25-baseline/bin/python'
assert sys.executable == PYTHON
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--label', default='final')
args = ap.parse_args()

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def hashes():
    return {str(p.relative_to(LANE.parents[1])): sha(p) for p in sorted(HERE.glob('*.py'))}

before = hashes()
rows = []
cases = [('145-control',145,'legacy','0','off','off','legacy','sampler-a'),
         ('145-split36',145,'split36','1','text-shift','off','legacy','eager-display'),
         ('169-control',169,'legacy','0','off','off','xpu2','sampler-a'),
         ('169-split36',169,'split36','0','off','split36-169','legacy','eager-display')]
for label, frames, text, dg, cone, arm, aux, schedule in cases:
    env = {k:v for k,v in os.environ.items() if not k.startswith('LTX_')}
    env.update(OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
        LTX_TEXT_RESIDENCY=text, LTX_CHUNK_ARM=arm, LTX_AUDIO_RESIDENCY='legacy',
        LTX_CONE_CAPTURE_RESERVE='parent', LTX_CONE_GRAPH_MEMORY=cone,
        LTX_DISPLAY_ALLOCATOR_RELEASE='off', LTX_DISPLAY_WORKER='serial',
        LTX_RUN_WRITE_ALLOWANCE_GIB='16')
    if label != '169-control':
        env.update(LTX_GC_INTERVAL_SECONDS='60', LTX_SNAPSHOT_DIGEST_CACHE='1',
                   LTX_STORAGE_SCAN_MODE='background', LTX_MAINTENANCE_MODE='idle')
    command = [PYTHON,'-B',str(HERE/'run_tests_134.py'),'--child',str(HERE/'harness_runtime.py'),
        '--frames',str(frames),'--anchor','frame','--decoder-graph',dg,'--anchor-decode','cone',
        '--bencode-overlap','1','--prep-ahead','1','--snapshot-mode','fingerprint',
        '--snapshot-schedule','full','--anchor-read-ahead','0','--display-schedule',schedule,
        '--display-device','xpu:3','--audio-residency','legacy','--aux-residency',aux,
        '--stream-chunks','2','--audio-delay','0.01','--decode-delay','0.01']
    ref = OUT/('cpu-reference-%d-%s.json' % (frames,args.label))
    if text == 'split36': command += ['--cpu-reference-json',str(ref)]
    log = OUT/(label+'-runtime-'+args.label+'.log')
    with log.open('x') as stream:
        result = subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT)
    try: data=json.loads(log.read_text().splitlines()[-1])
    except (IndexError,json.JSONDecodeError): data={'error':'Missing final JSON'}
    good=(result.returncode==0 and not data.get('error') and not data.get('halted')
          and data.get('verdict',{}).get('passed') and data.get('xpu_initialized') is False
          and data.get('decoder_drained') and data.get('preview_drained') and len(data.get('chunks',[]))==11)
    if text=='legacy' and data.get('cpu_reference_document'):
        with ref.open('x') as stream: json.dump(data['cpu_reference_document'],stream,indent=2)
    row=dict(label=label,frames=frames,passed=bool(good),returncode=result.returncode,command=command,
        environment={k:v for k,v in env.items() if k.startswith('LTX_')},
        log=str(log.relative_to(LANE.parents[1])),sha256=sha(log),chunks=data.get('chunks'),error=data.get('error'),
        qualification_chunks=9,stream_chunks=2,xpu_initialized=data.get('xpu_initialized'))
    rows.append(row)
    print(json.dumps({k:v for k,v in row.items() if k not in ('chunks','command','environment')}),flush=True)
    if not good: break

comparisons=[]
if len(rows)==4 and all(r['passed'] for r in rows):
    for i in (0,2):
        for a,b in zip(rows[i]['chunks'],rows[i+1]['chunks']):
            comparisons.append(dict(frames=rows[i]['frames'],name=a['name'],names_equal=a['name']==b['name'],
                decoded_tensors_equal=a['decoded_tensors']==b['decoded_tensors'],
                last_frame_equal=a['last_frame_sha256']==b['last_frame_sha256']))
preflight=LANE/'stream/tests/test_client_preflight_118b.py'
code=('import runpy,unittest; n=runpy.run_path('+repr(str(preflight))+'); '
      's=unittest.defaultTestLoader.loadTestsFromTestCase(n["Preflight118b"]); '
      'r=unittest.TextTestRunner(verbosity=2).run(s); raise SystemExit(not(r.wasSuccessful() and r.testsRun==10))')
command=[PYTHON,'-B',str(HERE/'run_tests_134.py'),'--child','-c',code]
log=OUT/('preflight10-'+args.label+'.log')
with log.open('x') as stream:
    result=subprocess.run(command,env=dict(os.environ,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1'),
                          stdout=stream,stderr=subprocess.STDOUT)
out=dict(schema='ltx.stream134.cpu-runtime.v1',cases=rows,off_on_exact_cpu_outputs=comparisons,
    preflight=dict(passed=result.returncode==0,returncode=result.returncode,tests=10,command=command,
                   log=str(log.relative_to(LANE.parents[1])),sha256=sha(log)),
    source_sha256=before,source_unchanged_during_cases=before==hashes(),
    scope='Real Runtime with CPU fake devices and synthetic outputs; not native qualification or performance.')
out['passed']=(len(comparisons)==22 and all(r['passed'] for r in rows)
    and all(r['names_equal'] and r['decoded_tensors_equal'] and r['last_frame_equal'] for r in comparisons)
    and out['preflight']['passed'] and out['source_unchanged_during_cases'])
with (OUT/('candidate-runtime-summary-'+args.label+'.json')).open('x') as stream:
    json.dump(out,stream,indent=2);stream.write('\n')
raise SystemExit(not out['passed'])
