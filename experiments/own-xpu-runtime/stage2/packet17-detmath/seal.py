"""Freeze hashes and host evidence for later coordinator windows (no discovery)."""
import gzip,hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/'build'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
g=json.loads((P/'gnu-host.json').read_text());i=json.loads((P/'icpx-host.json').read_text())
fresh=[json.loads((P/(tag+'-fresh.json')).read_text()) for tag in ('gnu','icpx')]
assert all(r['passed_cases']==72 and r['checks']==72 and r['passed'] for r in (g,i,*fresh))
assert g==fresh[0] and i==fresh[1]
assert all(x['packet4_core_vs_gnu_differing_bytes']==0 for x in i['cases'])
assert json.loads((B/'host-hashes.txt.sanity.json').read_text())['complete']
assert json.loads((P/'accuracy-results.json').read_text())
for tag in ('gnu','native'):
 deps=subprocess.check_output(['readelf','-d',str(B/tag/'host-test')],text=True)
 assert not any(x in deps for x in ('libsycl','ze_loader','OpenCL'))
protocol=subprocess.run([sys.executable,'-B',str(P/'test_window.py')],text=True,capture_output=True,check=True,timeout=60)
fixture_hashes=[]
for name in (B/'fixtures/cases.txt').read_text().split():
    v1=B/'v1fixtures'/(name+'.core');v2=B/'fixtures'/(name+'.core');intel=B/'fixtures'/(name+'.core.icpx')
    assert sha(v2)==sha(intel)
    fixture_hashes.append(dict(name=name,input_sha256=sha(B/'fixtures'/name),output_bytes=v2.stat().st_size,v1_gnu_sha256=sha(v1),v2_gnu_sha256=sha(v2),v2_intel_sha256=sha(intel)))
(P/'fixture-hashes.json').write_text(json.dumps(fixture_hashes,indent=2)+'\n')
sourcefiles=sorted(q for q in P.iterdir() if q.suffix in ('.hpp','.cpp','.py') or q.name=='CMakeLists.txt')
binaries=[B/'gnu/host-test',B/'native/host-test',B/'native/census-device',B/'native/device-test',B/'oracle/oracle',B/'host-hashes-generator']
receipt=dict(schema='own-runtime.packet17.build.v2',compiled=True,device_executed=False,arithmetic='iq3-p17-detmath-v2',parallel_vs_core_gnu=72,parallel_vs_core_intel=72,core_gnu_vs_intel=72,host_fresh_repeats_passed=True,compared_bytes_per_suite=g['compared_bytes'],host_cases=i['cases'],hashes={str(q.relative_to(ROOT)):sha(q) for q in sourcefiles},binaries={str(q.relative_to(P)):sha(q) for q in binaries},fixture_hashes_sha256=sha(P/'fixture-hashes.json'),rope_sha256=sha(P/'rope.bf16'),host_hashes_receipt_sha256=sha(P/'host-hashes-receipt.json'),host_hashes_sha256=sha(B/'host-hashes.txt'),fixture_trace_receipt_sha256=sha(P/'fixture-trace-receipt.json'),accuracy_receipt_sha256=sha(P/'accuracy-receipt.json'),protocol_tests=protocol.stderr,native_compiler='/opt/intel/oneapi/compiler/2026.0/bin/icpx',native_flags=['-O2','-fsycl','-fno-fast-math','-ffp-contract=off','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'],cpu_threads=2,max_compile_jobs=2)
(P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
subprocess.run([sys.executable,'-B',str(P/'prepare_windows.py'),'--census-binary',str(B/'native/census-device'),'--fixture-binary',str(B/'native/device-test'),'--fixtures',str(B/'fixtures'),'--fixture-trace',str(B/'fixture-inputs.bin'),'--trace-receipt',str(P/'fixture-trace-receipt.json'),'--host-hashes',str(B/'host-hashes.txt'),'--cpu-receipt',str(P/'build-receipt.json'),'--authority','iq3-p17-detmath-v2'],check=True,timeout=180)
