"""Keep the real oracle authority while sealing a local manifest snapshot.

Screen views already have immutable seals. This chain-only adapter does not
change their sources. It verifies copied oracle helpers and manifest against
the actual packet49 authority, then uses the unchanged authority validator.
"""
import hashlib,json,runpy,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet187-record-bundle-v3'
sys.path.insert(0,str(P))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def install():
 from reuse_build import verify_native
 verify_native()
 # Import search order must not select the frozen shared wrapper's unfixed copy.
 import importlib.util
 sys.path.insert(0,str(P))
 assert sha(P/'drain_gate.py')==sha(O/'drain_gate.py'),'drain copies differ'
 current=sys.modules.get('drain_gate')
 if current is None or Path(current.__file__).resolve()!=P/'drain_gate.py':
  spec=importlib.util.spec_from_file_location('drain_gate',P/'drain_gate.py')
  current=importlib.util.module_from_spec(spec);sys.modules['drain_gate']=current;spec.loader.exec_module(current)
 import shared_oracle
 authority=shared_oracle.AUTHORITY
 local=O/'oracle-authority'
 assert (local/'oracle').is_symlink() and (local/'oracle').resolve()==authority.resolve()
 assert sha(local/'oracle-binding.json')==sha(P/'oracle-binding.json')
 for name in ('oracle_job.py','suite_check.py','arithmetic.json','build-receipt.json','cpu-proof.json','unit-receipt.json','results/suite-manifest.json'):
  assert sha(P/'oracle'/name)==sha(authority/name),'copied oracle changed: '+name
 shared_oracle.P=P
 shared_oracle.static_binding()
 from seal_view import verify as verify_external
 verify_external()
 import chain_seal
 if not getattr(chain_seal.checked,'_p124_adapter',False):
  original=chain_seal.checked
  def checked():
   row=original()
   names=('proposal-spec.json','lanequeue.py','verify_cpu.py','evidence_reader.py','proposal_plan.py','chain_adapter.py','chain_entry.py','submission.py','submission_evidence.py','prepare_submission.py','device-entry.sh','source_decision.py','composite_jobs.py','composite_screen.py','verify_ready.py','policy_seal.py','drain_gate.py','drain_check.py','argument_gate.py','queue_gate.py','seal_view.py','inputs/external-source-bindings.json','copy_bundle.py','inputs/symlink-audit.json','inputs/packet124-native-identity.json','oracle-authority/oracle-binding.json')
   row['sources'].update({str((O/n).relative_to(ROOT)):sha(O/n) for n in names})
   row['sources'].update({str(f.relative_to(ROOT)):sha(f) for f in P.glob('v5/*.py')})
   row['oracle_snapshot_authority']=dict(local_manifest_sha256=sha(P/'oracle/results/suite-manifest.json'),authority_manifest_sha256=sha(authority/'results/suite-manifest.json'))
   from source_gate136 import verify_sources
   row['sources']={n:h for n,h in row['sources'].items() if '/oracle/' not in n}
   verify_sources(row['sources'])
   return row
  checked._p124_adapter=True;chain_seal.checked=checked
 return shared_oracle
if __name__=='__main__':
 script=sys.argv.pop(1);assert script in ('fast_reseal.py','check_inputs.py','chain103.py')
 install();sys.argv[0]=str(P/script);runpy.run_path(str(P/script),run_name='__main__')
