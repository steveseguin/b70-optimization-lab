#!/usr/bin/env python3
"""Archive only a passed pending-provider gate; no engines, deletions or retries.

The full/reuse container format is shared with the prior live proof, but proof
admission is distinct and requires both newer-provider survival observations.
Old quiescent archive admission and restoration semantics remain unchanged.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import json
import tarfile
from archive_ring_live_proof import (HERE, OWNRT, compare, identity, META, read,
    save, need, inventory, archive_identity)


def full(run,proof,archive_path,receipt_path):
    run,proof=Path(run).resolve(),Path(proof).resolve();summary=read(proof/'summary.json');terminal=read(run/'pending-ring-live-result.json')
    need(summary.get('schema')=='ownrt.pending-provider-proof.v1' and summary.get('passed') is True
         and summary.get('source_run')==str(run) and summary.get('target_state_exact') is True
         and summary.get('draft_state_exact') is True
         and summary.get('output_tokens_exact') is True
         and summary.get('actual_provider') is True
         and summary.get('scripted_tentative_inputs') is True
         and summary.get('provider_survival_passed') is True
         and summary.get('provider_survival_checks')==2
         and summary.get('provider_survival_discarded_rows')==3
         and summary.get('provider_survival_advanced_checks')==2
         and summary.get('pending_borrows')=={'1':1,'2':2}
         and summary.get('recursive_proposals_consumed') is False
         and summary.get('speed_claim') is False,'PASSED explicit pending-provider survival proof required')
    plan=read(run/'plan.json')
    need(plan.get('schema')=='ownrt.pending-ring-live-driver-plan.v1'
         and plan.get('mode')=='pending-ring-live-depth2','explicit pending-provider plan required')
    need(terminal.get('schema')=='ownrt.pending-ring-live-driver-result.v1'
         and terminal.get('mode')=='pending-ring-live-depth2'
         and terminal.get('scripted_tentative_inputs') is True and terminal.get('passed') is True
         and terminal.get('live_pids')==[] and terminal.get('returncodes')=={str(s['id']):0 for s in plan['stages']}
         and terminal['plan_sha256']==identity(run/'plan.json')['sha256']
         and terminal['lifecycle_result_sha256']==identity(run/'result.json')['sha256'],'clean hash-bound terminal pending-provider result required')
    qualified={str(Path(r['path']).resolve()):(r['bytes'],r['sha256']) for r in summary['raw_bundles']}
    need(len(qualified)==len(plan['stages'])+1,'expected one qualified target per stage plus canonical draft')
    raw=[];observed=set()
    for bundle in sorted(run.rglob('state.bundle')):
        need(not bundle.is_symlink(),'raw symlink refused');compare.BUNDLE.read_state(bundle.parent)
        seal=(bundle.parent/'state-seal.txt').read_text().splitlines();key=str(bundle.resolve());observed.add(key)
        if key in qualified:need(qualified[key]==(int(seal[1]),seal[2]),'qualified raw seal changed')
        raw.append(dict(original_path=key,archive_path=str(Path(run.name)/bundle.relative_to(run)),bytes=int(seal[1]),sha256=seal[2],
                        qualified=key in qualified,metadata_sha256={n:identity(bundle.parent/n)['sha256'] for n in META}))
    need(set(qualified)<=observed,'qualified raw state missing')
    need(len(raw)<=len(plan['stages'])+2,'unexpected raw bundle inventory requires review')
    # FINISH currently emits an additional sealed draft. Preserve it even if it
    # differs; do not quietly promote it to the independently qualified DUMP.
    for row in raw:
        if not row['qualified']:need(Path(row['original_path']).parent.name=='draft-final-state-sealed','unregistered additional raw bundle')
    config=Path(plan['config']);config_data=read(config);build_receipt=Path(config_data['build_receipt'])
    sources=[(run,run.name),(proof,'proof/'+proof.name),(config,'proof/run-config.json'),(build_receipt,'proof/build-receipt.json')]
    for name in ('archive_pending_provider_proof.py','test_archive_pending_provider_proof.py',
                 'finalize_pending_provider_proof.py','test_finalize_pending_provider_proof.py',
                 'pending_provider_trace_audit.py','test_pending_provider_trace_audit.py',
                 'archive_ring_live_proof.py','restore_ring_live_archive.py','restore_reused_state.py',
                 'test_archive_ring_live_proof.py','finalize_ring_live_proof.py','test_finalize_ring_live_proof.py',
                 'finalize_ring_proof.py','finalize_live_proof.py','finalize_wavefront_proof.py','live-draft-legacy-prefix.json'):
        sources.append((HERE/name,'proof/'+name))
    for relative in ('engine/src/pipeline/recursive_provider','engine/src/pipeline/ring','engine/src/pipeline/operator_state.hpp',
                     'engine/src/pipeline/checkpoint.hpp','engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp',
                     'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp',
                     'engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp',
                     'engine/tools/ring_live_driver.py','engine/tools/ring_live_wire.py',
                     'engine/tools/pending_ring_live_driver.py','engine/tools/pending_ring_live_wire.py',
                     'engine/tools/test_pending_ring_live_driver.py',
                     'engine/tools/test_ring_live_driver.py','engine/tools/test_ring_live_wire.py',
                     'engine/tools/compare_pipeline_state.py','engine/tools/compare_draft_state.py',
                     'engine/tools/compare_provider_survival.py','engine/tools/test_compare_pending_provider_state.py',
                     'engine/tools/test_compare_ring_live_state.py','gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((OWNRT/relative,'source/'+relative))
    def regular(member):
        need(member.isfile() or member.isdir(),'only regular evidence files/directories permitted');return member
    with tarfile.open(archive_path,'x:gz',compresslevel=1) as archive:
        for path,name in sources:archive.add(path,arcname=name,filter=regular)
    contents=inventory(archive_path)
    need({name for name in contents if PurePosixPath(name).name=='state.bundle'}=={r['archive_path'] for r in raw},'archive raw inventory differs')
    for row in raw:
        need(contents[row['archive_path']]==dict(bytes=row['bytes'],sha256=row['sha256']),'archived raw differs from sealed source')
        for name,sha in row['metadata_sha256'].items():need(contents[str(PurePosixPath(row['archive_path']).parent/name)]['sha256']==sha,'archived metadata differs')
    result=dict(schema='ownrt.ring-live-full-archive.v1',passed=True,archive=archive_identity(archive_path),bundles=raw,
        proof_kind='ownrt.pending-provider-proof.v1',proof_summary=identity(proof/'summary.json'),regular_members=len(contents),member_inventory=contents,
        raw_bytes=sum(r['bytes'] for r in raw),qualified_bundles=len(qualified),originals_preserved=True,
        script=identity(Path(__file__)),verified_utc=datetime.now(timezone.utc).isoformat())
    save(receipt_path,result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('run','proof','archive','receipt'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    result=full(args.run,args.proof,args.archive,args.receipt)
    print(json.dumps({k:result[k] for k in ('passed','archive','regular_members')}))
