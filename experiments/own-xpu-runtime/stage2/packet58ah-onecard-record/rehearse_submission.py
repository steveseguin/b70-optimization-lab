#!/usr/bin/env python3
"""CPU-only rehearsal on a private copy of 58ad chain-a's portable evidence.
All identity substitutions exist only in memory under unittest.mock. No payload
or measurement is written, no original evidence changed, no network available.
"""
import base64,copy,gzip,json,resource,shutil,socket,contextlib,io,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import packet58_submission as S
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
SOURCE=P.parent/'packet58ad-onecard-record/submission/prepared-a/evidence.json.gz'
def main():
    assert shutil.disk_usage('/').free-SOURCE.stat().st_size>=25_000_000_000
    # Independent in-memory copy of the frozen portable bundle: no disk duplicate.
    copied=io.BytesIO()
    with SOURCE.open('rb') as source:shutil.copyfileobj(source,copied)
    copied_bytes=copied.getvalue()
    copied_sha=S.sha(copied_bytes)
    assert copied_sha==S.file_hash(SOURCE)
    e=S.Evidence(json.loads(gzip.decompress(copied_bytes))['members'])
    original_seal=e.read('seal.json')
    try:S.derive(e)
    except (ValueError,KeyError) as error:rejection=str(error)
    else:raise AssertionError('predecessor accepted as new chain')
    def put(key,row):
        raw=row if isinstance(row,bytes) else S.encoded(row)
        e.members[key]=dict(sha256=S.sha(raw),raw_base64=base64.b64encode(raw).decode(),source_path='CPU-REHEARSAL-ONLY/'+key)
        return S.sha(raw)
    # Preserve all original timings, tokens, fixture hashes and fault counters.
    # Use the predecessor ledger only inside this fixture, because chain a
    # exactly equals (and cannot exceed) the current preparation-time record.
    policy=copy.deepcopy(S.POLICY)
    old_ledger=e.read('record-threshold.json')
    old_record=S.validate_threshold(old_ledger)
    policy['ledger_sha256']=S.sha(e.raw('record-threshold.json'))
    policy['supersedes']={k:old_record[k] for k in ('reference_submission','threshold_tok_s')}
    policy_hash=put('submission-policy.json',policy)
    seal=copy.deepcopy(original_seal)
    old_packet='experiments/own-xpu-runtime/stage2/packet58ad-onecard-record'
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
            # Synthetic composition allocation only; no original timing/token edits.
            census_key='run/run/census.json'
            census=e.read(name+'/'+census_key)
            census[0]['allocations'].append(dict(label='card0:exact-half-decode-table',category='weights',memory='device',bytes=262144,live=True))
            census_hash=put(name+'/'+census_key,census)
            w['native_files'][census_key]=census_hash
            w['postload_memory']['sources'][census_key]=census_hash
            w['postload_memory']['exact_half_decode_table_bytes']=262144
            driver=e.read(name+'/run/receipt.json')
            driver['command']+=['--hc-geometry','hc-wide','--experts','wide64+halfcache','--other-fusion','fused','--retirement','ordered-foreground']
            w['native_files']['run/receipt.json']=put(name+'/run/receipt.json',driver)
            for ref,key in [(w['previous'],S.ORDER[i-1]+'/window.json'),*[(r,n+'/window.json') for r,n in zip(w['k1_refs'],S.ORDER[:2])]]:
                ref['sha256']=e.members[key]['sha256']
                ref['path']=str(ROOT/S.CHAIN/key)
        put(name+'/window.json',w)
    with patch.object(S,'SEAL_SHA',seal_sha),patch.object(S,'POLICY',policy),patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
        derived=S.derive(e)
        notes=S.submission_notes(derived)
        assert derived['primary_metric']['value_tok_s']==30.395630964654867
        assert len(notes)<=2000 and '21.55 GB' in notes
        assert not derived['realistic_final_gate']['passed']
        assert not derived['fresh_timing_repeat_passed']
    # Test current predecessor and disclosure with the independently synthetic
    # >record fixture; never relabel the 58ad timing as a 58ah measurement.
    import test_submission as T
    fixture,fixture_seal=T.synthetic()
    with patch.object(S,'SEAL_SHA',fixture_seal):
        current=S.derive(fixture);current_notes=S.submission_notes(current)
        assert S.POLICY['supersedes']['reference_submission'] in current_notes
        assert S.POLICY['readiness_amendment'] in current_notes
        assert len(current_notes)<=2000
    # Exercise the real CLI from its final location with repository-relative
    # artifact paths. Only the synthetic seal is patched; REPO_ROOT is untouched.
    import submission_cli
    cli=submission_cli.load_submitter()
    assert cli.REPO_ROOT==ROOT
    (P/'submission').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.cpu-cli-',dir=P/'submission') as tmp:
        out=Path(tmp)/'prepared'
        with patch.object(S,'SEAL_SHA',fixture_seal),patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
            S.write_prepared(fixture,out)
            capture=io.StringIO()
            with patch.object(sys,'argv',[str(P/'submission_cli.py'),'--payloads',str(out/'payload-queue.json'),'--dry-run']),contextlib.redirect_stdout(capture):
                assert cli.main()==0
            assert json.loads(capture.getvalue())==json.loads((out/'payload-queue.json').read_text())
    assert not out.exists()
    report=dict(passed=True,device_executed=False,original_evidence_sha256=S.file_hash(SOURCE),
        copied_evidence_sha256=copied_sha,old_chain_rejected_by_production=rejection,
        actual_58ad_chain_a_replay_tok_s=derived['primary_metric']['value_tok_s'],
        composition_and_chain_identity_substitutions_synthetic=True,private_copy_storage="memory",predecessor_ledger_override_fixture_only=True,
        new_chain_measurement=False, original_packet='packet58ad-onecard-record',payload_written=False,temporary_synthetic_payload_removed=True,network_used=False,
        final_location_cli_passed=True,cli_repo_root=str(cli.REPO_ROOT),cli_root_overridden=False,
        current_predecessor=S.POLICY['supersedes'],notes_characters=len(current_notes),
        real_bundle_notes_characters=len(notes),fault_counters=derived['fault_counters'],
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    assert report['peak_rss_bytes']<4*1024**3
    (P/'evidence/submission-rehearsal.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    main()
