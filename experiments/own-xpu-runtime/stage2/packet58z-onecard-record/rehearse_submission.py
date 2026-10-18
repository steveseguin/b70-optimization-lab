#!/usr/bin/env python3
"""CPU-only rehearsal on a private copy of 58w chain-b's portable evidence.
All identity substitutions exist only in memory under unittest.mock. No payload
or measurement is written, no original evidence changed, no network available.
"""
import base64,copy,gzip,json,resource,shutil,socket
from pathlib import Path
from unittest.mock import patch
import packet58_submission as S
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
SOURCE=P.parent/'packet58w-onecard-record/submission/prepared-b/evidence.json.gz'
def main():
    assert shutil.disk_usage('/').free-SOURCE.stat().st_size>=25_000_000_000
    copied=P/'lineage/58w-chain-b-rehearsal.json.gz'
    if not copied.exists():shutil.copy2(SOURCE,copied)
    assert S.file_hash(copied)==S.file_hash(SOURCE)
    e=S.Evidence(json.loads(gzip.decompress(copied.read_bytes()))['members'])
    original_seal=e.read('seal.json')
    try:S.derive(e)
    except ValueError as error:rejection=str(error)
    else:raise AssertionError('18 GB predecessor accepted as new chain')
    def put(key,row):
        raw=row if isinstance(row,bytes) else S.encoded(row)
        e.members[key]=dict(sha256=S.sha(raw),raw_base64=base64.b64encode(raw).decode(),source_path='CPU-REHEARSAL-ONLY/'+key)
        return S.sha(raw)
    # Preserve all original timings, tokens, fixture hashes and fault counters.
    # Use the predecessor ledger only inside this fixture, because chain b
    # exactly equals (and cannot exceed) the current preparation-time record.
    policy=copy.deepcopy(S.POLICY)
    old_ledger=e.read('record-threshold.json')
    old_record=S.validate_threshold(old_ledger)
    policy['ledger_sha256']=S.sha(e.raw('record-threshold.json'))
    policy['supersedes']={k:old_record[k] for k in ('reference_submission','threshold_tok_s')}
    policy_hash=put('submission-policy.json',policy)
    seal=copy.deepcopy(original_seal)
    old_packet='experiments/own-xpu-runtime/stage2/packet58w-onecard-record'
    for leaf in ('selection.json','oracle-binding.json'):
        raw=e.raw('sources/'+old_packet+'/'+leaf)
        key=str(S.PACKET/leaf)
        seal['sources'][key]=put('sources/'+key,raw)
    key=str(S.PACKET/'submission-policy.json')
    seal['sources'][key]=put('sources/'+key,policy)
    seal_sha=put('seal.json',seal)
    for i,name in enumerate(S.ORDER):
        w=e.read(name+'/window.json')
        w['build_receipt_sha256']=seal_sha
        if not name.startswith('K1'):
            w['postload_memory']['full_cache_bytes']=21552729600
            driver=e.read(name+'/run/receipt.json')
            driver['command']+=['--cache-cap','max','--cache-bytes','21552729600']
            w['native_files']['run/receipt.json']=put(name+'/run/receipt.json',driver)
            for ref,key in [(w['previous'],S.ORDER[i-1]+'/window.json'),*[(r,n+'/window.json') for r,n in zip(w['k1_refs'],S.ORDER[:2])]]:
                ref['sha256']=e.members[key]['sha256']
                ref['path']=str(ROOT/S.CHAIN/key)
        put(name+'/window.json',w)
    with patch.object(S,'SEAL_SHA',seal_sha),patch.object(S,'POLICY',policy),patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
        derived=S.derive(e)
        notes=S.submission_notes(derived)
        assert derived['primary_metric']['value_tok_s']==28.0429892090105
        assert len(notes)<=2000 and '21.55 GB' in notes
        assert not derived['realistic_final_gate']['passed']
        assert not derived['fresh_timing_repeat_passed']
    # Test current predecessor and disclosure with the independently synthetic
    # >record fixture; never relabel the chain-b timing as a 58z measurement.
    import test_submission as T
    fixture,fixture_seal=T.synthetic()
    with patch.object(S,'SEAL_SHA',fixture_seal):
        current=S.derive(fixture);current_notes=S.submission_notes(current)
        assert S.POLICY['supersedes']['reference_submission'] in current_notes
        assert S.POLICY['readiness_amendment'] in current_notes
        assert len(current_notes)<=2000
    report=dict(passed=True,device_executed=False,original_evidence_sha256=S.file_hash(SOURCE),
        copied_evidence_sha256=S.file_hash(copied),old_chain_rejected_by_production=rejection,
        actual_chain_b_replay_tok_s=derived['primary_metric']['value_tok_s'],
        capacity_and_chain_identity_substitutions_synthetic=True,predecessor_ledger_override_fixture_only=True,
        new_chain_measurement=False,payload_written=False,network_used=False,
        current_predecessor=S.POLICY['supersedes'],notes_characters=len(current_notes),
        real_bundle_notes_characters=len(notes),fault_counters=derived['fault_counters'],
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    assert report['peak_rss_bytes']<4*1024**3
    (P/'evidence/submission-rehearsal.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    main()
