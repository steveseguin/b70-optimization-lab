"""Narrow model-evidence reuse for the fixture repair and named fix6 amendment.

Historical execution receipts keep their original binaries and source hashes.
The seal labels historical mini and model evidence honestly. The owner directed
device-oracle authority for the exact pinned fix6 grouping repair. Every other
production change refuses reuse.
"""
import base64,gzip,json
from pathlib import Path
from storage import digest
from build import compiled_sources
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
FIXTURE_ONLY={'gemv_timing.cpp','p39_fixture.cpp'}
def baseline_builds(archive):
 result={};name=None;raw=bytearray()
 with gzip.open(P/archive['path'],'rt') as stream:
  for line in stream:
   item=json.loads(line)
   if item.get('kind')=='file':name=Path(item['path']).name;raw=bytearray()
   elif item.get('kind')=='chunk' and name in ('build-gnu-host-receipt.json','build-icpx-host-receipt.json'):raw.extend(base64.b64decode(item['base64']))
   elif item.get('kind')=='end' and raw:result[name]=json.loads(raw);name=None;raw=bytearray()
 assert len(result)==2
 return result
def verify_sources(old,current):
 assert set(old)==set(current),'compiled source closure changed'
 changed={n for n in current if old[n]!=current[n]}
 expected={str((P/n).relative_to(ROOT)) for n in FIXTURE_ONLY}
 main=str((P/'main.cpp').relative_to(ROOT))
 if main in changed:
  from seal6_amendment import NEW_MAIN,OLD_MAIN,baseline
  assert old[main]==OLD_MAIN and current[main]==NEW_MAIN,'change outside fixture/fix6 repair'
  assert all(current[n]==baseline()['sources'][n] for n in expected),'change outside fixture/fix6 repair'
  expected.add(main)
 assert changed==expected,'change outside fixture-only repair'
 # Both are translation units, never included by production decode sources.
 for n in set(current)-expected:
  f=ROOT/n
  if f.suffix in ('.cpp','.hpp'):
   assert all(('#include "'+name+'"') not in f.read_text() for name in FIXTURE_ONLY),'fixture included by decode'
 return sorted(changed)
def verify(artifacts):
 from seal45 import bound_sources,archive_bound
 from copy_adoption_gate import verify as copy_verify
 copy_verify()
 before=json.loads((P/'evidence/copy-extent-fix/before-build-receipt.json').read_text())
 retained=json.loads((P/'evidence/copy-extent-fix/prior-seal-retention.json').read_text())
 assert digest(P/'evidence/copy-extent-fix/before-build-receipt.json')==retained['original_paths_sha256']['build-receipt.json'],'baseline seal changed'
 archive_bound(retained['archive'])
 previous_builds=baseline_builds(retained['archive'])
 real=json.loads((P/'cpu-real-gates.json').read_text())
 assert before['passed'] and real['passed'] and real['completed'] and real['cases']==6
 assert before['gate_receipts']['cpu-real-gates.json']==digest(P/'cpu-real-gates.json'),'historical real receipt changed'
 current=compiled_sources();changed=verify_sources(real['build']['compiled_sources_sha256'],current)
 assert real['build']['binary_sha256']==before['artifacts_sha256']['gnu-host/own-rt-iq3']
 for mode in ('gnu-host','icpx-host'):
  build=json.loads((P/('build-'+mode+'-receipt.json')).read_text())
  from seal6_amendment import maps_match
  assert build['compiled_sources_sha256']==current or (mode=='icpx-host' and maps_match(build['compiled_sources_sha256'],current))
  assert build['artifacts_sha256'][mode+'/own-rt-iq3']==artifacts[mode+'/own-rt-iq3']
  previous=previous_builds['build-'+mode+'-receipt.json']
  assert previous['compile_commands_sha256']==build['compile_commands_sha256'],'model compile commands changed'
  assert previous['link_files_sha256']==build['link_files_sha256'],'model link commands changed'
  assert verify_sources(previous['compiled_sources_sha256'],current)==changed
 # Frozen capture receipts remain bound to the preceding seal, with explicit
 # provenance instead of pretending they executed under the current binary.
 for n in ('capacity-draft-gates.json',):assert digest(P/n)==before['gate_receipts'][n]
 return dict(passed=True,device_executed=False,changed_translation_units=changed,
  linked_into_model_binary=True,called_by_production_decode=True,
  seal_amendment=__import__('seal6_amendment').verify(),
  historical_real_cases=6,fresh_real_cases=0,
  reuse_authorization='SEAL6 owner directive 2026-10-15: exact fix6 grouping change; device suite oracle is real-model authority; no pre-device real-model CPU rerun',
  historical_model_artifacts_sha256={n:h for n,h in before['artifacts_sha256'].items() if n.endswith('/own-rt-iq3')},
  baseline_seal_sha256=digest(P/'evidence/copy-extent-fix/before-build-receipt.json'))
