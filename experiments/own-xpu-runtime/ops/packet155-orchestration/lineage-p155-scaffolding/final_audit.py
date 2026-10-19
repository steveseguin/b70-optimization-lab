"""Final CPU audit; pending device evidence is a legitimate, explicit refusal."""
import json,shutil,resource
from source_decision import O,P,ROOT,sha,save

def main():
 from verify_cpu import verify
 verify()
 from argument_gate import verify as arguments
 argv=arguments()
 assert len(argv['windows'])==11 and sum(len(r['argv']) for r in argv['windows'])==31
 assert argv['queue']['queue_run_executed'] and len(argv['queue']['oracle_checks'])==6
 startup=json.loads((P/'startup103.json').read_text());assert startup['total_windows']==22
 shape=json.loads((P/'evidence/full-shape.json').read_text());assert len(shape['runs'])==4 and all(r['passed'] for r in shape['runs'])
 byte=json.loads((P/'evidence/cpu-byte-identity.json').read_text());assert len(byte['views'])==2
 for view in byte['views'].values():
  assert len(view['runs'])==4 and all(r['candidate_sha256']==r['expected_sha256']==r['packet118_output_sha256'] for r in view['runs'])
 from queue_gate import symlinks
 links=symlinks();assert len(links)==182
 from copy_bundle import links as find_links
 parent=find_links(P.with_name('packet124c-record-bundle'));actual=find_links(P)
 assert all(actual.get(k)==v for k,v in parent.items()),'a frozen parent symlink was lost'
 build=sum(f.stat().st_size for f in P.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts)
 free=shutil.disk_usage('/').free;assert build<=300_000_000 and free>=25_000_000_000
 assert not (P/'build/device-cards01-a').exists()
 from verify_ready import evaluate
 ready=evaluate();save(O/'ready.json',ready)
 assert ready.get('cpu_preparation_ready') is True,ready.get('reason')
 row=dict(passed=True,device_executed=False,services_started=False,live_queue_modified=False,
  sealed_compositions=2,all_startup_windows=22,all_python_windows=11,intercepted_native_arguments=31,
  queue_windows=11,queue_input_preflights=12,queue_oracle_checks=6,preserved_parent_symlinks=len(parent),
  build_bytes=build,root_free_bytes=free,chain_ready=ready['ready'],readiness_reason=ready.get('reason'),
  argument_gate_sha256=sha(O/'evidence/argument-gate.json'),cpu_tests_sha256=sha(O/'cpu-tests.json'),
  tests_log=(O/'tests.log').read_text().strip(),chain_seal_sha256=sha(P/'build-receipt.json'),
  native_identity='exact packet131b binaries and selections; rollback_state banks maps to native banks-batch')
 save(O/'cpu-final.json',row);print(json.dumps(row,indent=2))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
