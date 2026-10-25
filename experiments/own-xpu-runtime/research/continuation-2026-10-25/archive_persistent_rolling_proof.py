#!/usr/bin/env python3
"""Archive only passed two-request persistent rolling parity; preserve raw bytes.

The existing mixed reuse/restore container remains unchanged. This admission
requires actual proposal consumption/provenance and honest observed survival,
without importing the scripted pending gate's fixed coverage requirements.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import json
import tarfile
from archive_ring_live_proof import (HERE, OWNRT, compare, identity, META, read,
    save, need, inventory, archive_identity)


def full(run,proof,archive_path,receipt_path):
    run,proof=Path(run).resolve(),Path(proof).resolve();summary=read(proof/'summary.json');terminal=read(run/'persistent-rolling-result.json')
    policy=summary.get('check_policy')
    need(summary.get('schema')=='ownrt.persistent-rolling-proof.v1' and summary.get('passed') is True
         and summary.get('source_run')==str(run) and type(summary.get('requests')) is int and summary['requests']==2
         and policy in ('qualification','measured')
         and all(summary.get(key) is True for key in ('target_state_exact','draft_state_exact',
             'output_tokens_exact','all_requests_full_state_parity','all_cold_resets_checked',
             'mandatory_restore_checks_passed','actual_provider','actual_proposals_consumed','provenance_passed'))
         and summary.get('scripted_oracle_assisted') is False and summary.get('speed_claim') is False,
         'PASSED explicit two-request persistent rolling parity required')
    enabled=policy=='qualification'
    need(summary.get('byte_verification_enabled') is enabled
         and summary.get('provider_survival_checks_enabled') is enabled,
         'persistent archive diagnostic policy differs')
    need(enabled or summary.get('qualified_reference_parity') is True,
         'measured archive requires qualified-policy parity')
    plan=read(run/'plan.json')
    need(plan.get('schema')=='ownrt.persistent-rolling-plan.v1'
         and plan.get('mode')=='persistent-rolling' and plan.get('check_policy')==policy
         and plan.get('suite_prompt_count')==2 and plan.get('dump_each') is True,
         'explicit two-request persistent rolling plan required')
    need(terminal.get('schema')=='ownrt.persistent-rolling-result.v1'
         and terminal.get('mode')=='persistent-rolling' and terminal.get('check_policy')==policy
         and terminal.get('scripted_oracle_assisted') is False and terminal.get('passed') is True
         and terminal.get('live_pids')==[] and terminal.get('returncodes')=={str(s['id']):0 for s in plan['stages']}
         and terminal['plan_sha256']==identity(run/'plan.json')['sha256']
         and terminal['lifecycle_result_sha256']==identity(run/'result.json')['sha256'],
         'clean hash-bound terminal persistent result required')
    qualified={str(Path(r['path']).resolve()):(r['bytes'],r['sha256']) for r in summary['raw_bundles']}
    need(len(qualified)==2*(len(plan['stages'])+1),'expected qualified target/draft bundles for both requests')
    raw=[];observed=set()
    for bundle in sorted(run.rglob('state.bundle')):
        need(not bundle.is_symlink(),'raw symlink refused');compare.BUNDLE.read_state(bundle.parent)
        seal=(bundle.parent/'state-seal.txt').read_text().splitlines();key=str(bundle.resolve());observed.add(key)
        if key in qualified:need(qualified[key]==(int(seal[1]),seal[2]),'qualified raw seal changed')
        raw.append(dict(original_path=key,archive_path=str(Path(run.name)/bundle.relative_to(run)),bytes=int(seal[1]),sha256=seal[2],
                        qualified=key in qualified,metadata_sha256={n:identity(bundle.parent/n)['sha256'] for n in META}))
    need(set(qualified)<=observed,'qualified raw state missing')
    need(len(raw)<=3*(len(plan['stages'])+1)+1,'unexpected persistent raw bundle inventory requires review')
    # FINISH currently emits an additional sealed draft. Preserve it even if it
    # differs; do not quietly promote it to the independently qualified DUMP.
    for row in raw:
        if not row['qualified']:need(Path(row['original_path']).parent.name in ('draft-final-state-sealed','state-2147483647','state-2147483647.draft'),'unregistered additional raw bundle')
    config=Path(plan['config']);config_data=read(config);build_receipt=Path(config_data['build_receipt'])
    sources=[(run,run.name),(proof,'proof/'+proof.name),(config,'proof/run-config.json'),(build_receipt,'proof/build-receipt.json'),(Path(plan['suite']),'proof/runtime-inputs.json')]
    for name in ('archive_persistent_rolling_proof.py','test_archive_persistent_rolling_proof.py',
                 'finalize_persistent_rolling_proof.py','test_finalize_persistent_rolling_proof.py',
                 'persistent_rolling_trace_audit.py','test_persistent_rolling_trace_audit.py',
                 'persistent_rolling_reset_audit.py',
                 'archive_rolling_provider_proof.py','test_archive_rolling_provider_proof.py',
                 'finalize_rolling_provider_proof.py','test_finalize_rolling_provider_proof.py',
                 'rolling_provider_trace_audit.py','test_rolling_provider_trace_audit.py',
                 'archive_pending_provider_proof.py','test_archive_pending_provider_proof.py',
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
                     'engine/tools/rolling_ring_driver.py','engine/tools/test_rolling_ring_driver.py',
                     'engine/tools/persistent_rolling_driver.py','engine/tools/persistent_rolling_suite.py',
                     'engine/tools/test_persistent_rolling.py','engine/tools/persistent_ring_policy.py',
                     'engine/tools/compare_persistent_provider_survival.py',
                     'engine/tools/test_compare_persistent_ring_state.py','engine/tools/test_persistent_ring_policy.py',
                     'engine/tools/test_rolling_ring_socket.py',
                     'engine/tools/compare_rolling_provider_survival.py','engine/tools/test_compare_rolling_provider_state.py',
                     'engine/tools/test_pending_ring_live_driver.py',
                     'engine/tools/test_ring_live_driver.py','engine/tools/test_ring_live_wire.py',
                     'engine/tools/compare_pipeline_state.py','engine/tools/compare_draft_state.py',
                     'engine/tools/compare_provider_survival.py','engine/tools/test_compare_pending_provider_state.py',
                     'engine/tools/test_compare_ring_live_state.py','gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((OWNRT/relative,'source/'+relative))
    for source in sorted((OWNRT/'engine/planning/rolling_provider').glob('*.py')):
        sources.append((source,'source/'+str(source.relative_to(OWNRT))))
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
        proof_kind='ownrt.persistent-rolling-proof.v1',check_policy=policy,proof_summary=identity(proof/'summary.json'),regular_members=len(contents),member_inventory=contents,
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
