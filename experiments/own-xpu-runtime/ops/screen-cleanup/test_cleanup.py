"""Entirely temporary filesystem: no real archive, queue or device writes."""
import hashlib
import json
import os
from pathlib import Path
import tarfile
import pytest
import cleanup as c


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(tmp_path, version='v4-lanes', number='76', view='production'):
    root=tmp_path/'repo'
    runtime=root/c.RUNTIME
    run=runtime/f'stage2/screen/{version}/evidence/p{number}-A-0-{view}'
    queue=runtime/'ops/lane-queue'
    queue.mkdir(parents=True)
    review=runtime/'stage2/screen'/version/'evidence/review.json'
    review_data=dict(boot_id='boot',through='now',fault_count=2)
    save(review,review_data)
    save(run/'window.json',dict(finished_utc_ns=20,lane='A',coordinator_fault_review=review_data))
    save(run/'identity.json',dict(binary_sha256='a'*64))
    job=dict(name='packet76-grid-A',lane='A',argv=['runner.py','--output',str(run)])
    done=dict(job=job,outcome='DONE',rc=0,Result='success',ExecMainStatus='0',review=str(review))
    ledger=queue/'done-A-reviewed-20261018.txt'
    ledger.write_text(json.dumps(done)+'\n')
    config=runtime/'ops/screen-cleanup/closed.json'
    save(config,dict(packets={number:dict(status='CLOSED',reason='review 15')}))
    for directory in c.BULK:
        (run/directory).mkdir(parents=True)
    first=run/c.BULK[0]/'cache.bin'
    first.write_bytes(b'cached kernel\x00'*100)
    second=run/c.BULK[1]/'input.bin'
    second.write_bytes(b'input bytes\xff'*100)
    save(run/c.BULK[1]/'receipt.json',dict(keep=True))
    (run/c.BULK[1]/'events.jsonl').write_text('{}\n')
    return root,config,run,tmp_path/'archive',ledger


@pytest.mark.parametrize('version',['v4-lanes','v5-bracket'])
def test_archive_roundtrip_hardlinks_receipts_and_repeat(tmp_path,version):
    root,config,run,archive,_=fixture(tmp_path,version)
    link=run/c.BULK[1]/'hardlink.bin'
    os.link(run/c.BULK[0]/'cache.bin',link)
    before={str(p.relative_to(run)):p.read_bytes() for p in run.rglob('*') if p.is_file()}
    plan=c.plan(root,config)
    assert plan['runs'][0]['status']=='ARCHIVE' and len(plan['runs'][0]['files'])==3
    assert not archive.exists() and all((run/name).read_bytes()==data for name,data in before.items())
    result=c.execute(root,config,archive)
    tarpath=Path(result['runs'][0]['archive'])
    assert len(list(archive.glob('*.tar.gz')))==1
    with tarfile.open(tarpath,'r:gz') as tar:
        assert any(m.islnk() for m in tar.getmembers())
        for name in [f['path'] for f in plan['runs'][0]['files']]:
            assert tar.extractfile(name).read()==before[name]
            assert not (run/name).exists()
    for name,data in before.items():
        if name.endswith(('.json','.jsonl')):
            assert (run/name).read_bytes()==data
    assert c.execute(root,config,archive)['runs'][0]['status']=='DONE'


def test_every_live_packet_hash_and_explicit_path_protect_bulk(tmp_path):
    root,config,run,archive,_=fixture(tmp_path)
    cache=run/c.BULK[0]/'cache.bin'
    bundle=run/c.BULK[1]/'input.bin'
    # Anonymous digest in identity, named path even with an out-of-date hash.
    save(root/c.RUNTIME/'stage2/packet101-live/build/window.json',
         dict(files={str(bundle.relative_to(root)):'f'*64}))
    save(root/c.RUNTIME/'stage2/packet82-keep/identity.json',dict(any_hash=c.digest(cache)))
    plan=c.plan(root,config)
    assert len(plan['live_documents'])==2 and plan['bytes']==0
    assert len(plan['runs'][0]['retained'])==4
    c.execute(root,config,archive)
    assert cache.exists() and bundle.exists() and not list(archive.glob('*.tar.gz'))


def test_external_linked_live_window_is_read(tmp_path):
    root,config,run,_,_=fixture(tmp_path)
    external=tmp_path/'results'
    save(external/'window.json',dict(files={'anonymous':c.digest(run/c.BULK[0]/'cache.bin')}))
    link=root/c.RUNTIME/'stage2/packet101-live/build'
    link.parent.mkdir()
    link.symlink_to(external,target_is_directory=True)
    row=c.plan(root,config)['runs'][0]
    assert not any(f['path'].endswith('cache.bin') for f in row['files'])


def test_shared_wrapper_alias_does_not_make_closed_screens_live(tmp_path):
    root,config,run,_,_=fixture(tmp_path)
    shared=run.parents[1]
    alias=root/c.RUNTIME/'stage2/packet75-live/screen'
    alias.parent.mkdir()
    alias.symlink_to(shared,target_is_directory=True)
    value=c.read(run/'window.json')
    value['files']={str((run/c.BULK[0]/'cache.bin').relative_to(run)):c.digest(run/c.BULK[0]/'cache.bin')}
    save(run/'window.json',value)
    assert c.plan(root,config)['runs'][0]['status']=='ARCHIVE'


def test_same_bytes_at_a_different_named_path_are_not_live_inputs(tmp_path):
    root,config,run,_,_=fixture(tmp_path)
    save(root/c.RUNTIME/'stage2/packet101-live/window.json',
         dict(files={'run/another-cache.bin':c.digest(run/c.BULK[0]/'cache.bin')}))
    assert any(f['path'].endswith('cache.bin') for f in c.plan(root,config)['runs'][0]['files'])


@pytest.mark.parametrize('outcome,reviewed,expected',[('DONE',True,'ARCHIVE'),('DONE',False,'SKIP'),
    ('FAILED',True,'SKIP'),('REPORT-FAILED',True,'SKIP')])
def test_done_and_postscreen_review_both_required(tmp_path,outcome,reviewed,expected):
    root,config,_,_,ledger=fixture(tmp_path)
    row=json.loads(ledger.read_text());row['outcome']=outcome
    ledger.write_text(json.dumps(row)+'\n')
    if not reviewed:
        ledger.rename(ledger.with_name('done-A.txt'))
    assert c.plan(root,config)['runs'][0]['status']==expected


def test_coordinator_review_list_does_not_edit_live_queue(tmp_path):
    root,config,_,archive,ledger=fixture(tmp_path)
    ledger.rename(ledger.with_name('done-A.txt'))
    live=ledger.with_name('queue-A.txt');live.write_text('running job\n')
    value=c.read(config);value['reviewed_jobs']=['packet76-grid-A'];save(config,value)
    assert c.execute(root,config,archive)['runs'][0]['status']=='ARCHIVED'
    assert live.read_text()=='running job\n'


def test_partial_packet90_closure_keeps_e1_and_production(tmp_path):
    root,config,run,_,_=fixture(tmp_path,number='90',view='exp-halfcache')
    value=c.read(config);value['packets']['90']['views']=['hc-weightcache'];save(config,value)
    assert c.plan(root,config)['runs']==[]
    assert not c.closed(Path('stage2/screen/v4-lanes/evidence/p90-B-grid-B-0-production'),value)
    assert c.closed(Path('stage2/screen/v4-lanes/evidence/p90-B-grid-B-2-hc-weightcache'),value)
    assert (run/c.BULK[0]/'cache.bin').exists()


def test_previously_removed_bulk_is_done(tmp_path):
    root,config,run,archive,_=fixture(tmp_path)
    for leaf in ('cache.bin','input.bin'):
        for p in run.rglob(leaf):p.unlink()
    assert c.plan(root,config)['runs'][0]['status']=='DONE'
    c.execute(root,config,archive)
    assert not list(archive.glob('*.tar.gz'))


def test_completed_reviewed_diagnostic_need_not_pass_quality(tmp_path):
    root,config,run,_,_=fixture(tmp_path,number='86')
    value=c.read(run/'window.json');value.pop('finished_utc_ns')
    value.update(passed=False,device_complete=True,lease_released=True,returncode=0)
    save(run/'window.json',value)
    assert c.plan(root,config)['runs'][0]['status']=='ARCHIVE'


def test_bad_archive_verification_never_deletes(tmp_path,monkeypatch):
    root,config,run,archive,_=fixture(tmp_path)
    def fail(*args):raise ValueError('archive corrupt')
    monkeypatch.setattr(c,'verify_archive',fail)
    with pytest.raises(ValueError,match='corrupt'):c.execute(root,config,archive)
    assert (run/c.BULK[0]/'cache.bin').exists() and (run/c.BULK[1]/'input.bin').exists()


def test_new_live_hash_after_archive_prevents_deletion(tmp_path,monkeypatch):
    root,config,run,archive,_=fixture(tmp_path)
    original=c.archive_run
    def archive_and_new_reference(*args):
        result=original(*args)
        save(root/c.RUNTIME/'stage2/packet101-live/window.json',
             dict(hash=c.digest(run/c.BULK[0]/'cache.bin')))
        return result
    monkeypatch.setattr(c,'archive_run',archive_and_new_reference)
    with pytest.raises(ValueError,match='eligibility'):c.execute(root,config,archive)
    assert (run/c.BULK[0]/'cache.bin').exists()


def test_source_changed_during_archive_prevents_deletion(tmp_path,monkeypatch):
    root,config,run,archive,_=fixture(tmp_path)
    original=c.archive_run
    def archive_and_mutate(*args):
        result=original(*args)
        (run/c.BULK[0]/'cache.bin').write_bytes(b'changed')
        return result
    monkeypatch.setattr(c,'archive_run',archive_and_mutate)
    with pytest.raises(ValueError,match='eligibility'):c.execute(root,config,archive)
    assert (run/c.BULK[0]/'cache.bin').read_bytes()==b'changed'


def test_partial_unlink_resume_verifies_original_full_archive(tmp_path):
    root,config,run,archive,_=fixture(tmp_path)
    row=c.plan(root,config)['runs'][0]
    path=c.archive_run(root,row,archive)
    (run/row['files'][0]['path']).unlink()
    assert c.execute(root,config,archive)['runs'][0]['status']=='ARCHIVED'
    assert len(list(archive.glob('*.tar.gz')))==1 and path.exists()


def test_corrupt_existing_archive_refuses_resume(tmp_path):
    root,config,run,archive,_=fixture(tmp_path)
    path=c.archive_run(root,c.plan(root,config)['runs'][0],archive)
    path.write_bytes(b'not an archive')
    with pytest.raises(tarfile.ReadError):c.execute(root,config,archive)
    assert (run/c.BULK[0]/'cache.bin').exists()


def test_hardlinks_across_runs_archived_before_any_unlink(tmp_path):
    root,config,run,archive,ledger=fixture(tmp_path)
    other=run.with_name('p76-A-1-ordered')
    for bulk in c.BULK:(other/bulk).mkdir(parents=True)
    os.link(run/c.BULK[0]/'cache.bin',other/c.BULK[0]/'cache.bin')
    window=c.read(run/'window.json')
    save(other/'window.json',window)
    row=json.loads(ledger.read_text());row['job']['argv']=['grouped-runner.py']
    ledger.write_text(json.dumps(row)+'\n')
    result=c.execute(root,config,archive)
    assert all(r['status']=='ARCHIVED' for r in result['runs'])
    assert len(list(archive.glob('*.tar.gz')))==2
    assert not (other/c.BULK[0]/'cache.bin').exists()


@pytest.mark.parametrize('where',['file','directory'])
def test_candidate_symlink_refused(tmp_path,where):
    root,config,run,_,_=fixture(tmp_path)
    target=tmp_path/'other';target.mkdir()
    (target/'secret').write_bytes(b'must remain')
    link=run/c.BULK[0]/'link'
    link.symlink_to(target if where=='directory' else target/'secret',target_is_directory=where=='directory')
    with pytest.raises(ValueError):c.plan(root,config)
    assert (target/'secret').read_bytes()==b'must remain'


def test_malformed_live_window_fails_closed(tmp_path):
    root,config,_,_,_=fixture(tmp_path)
    path=root/c.RUNTIME/'stage2/packet101/window.json'
    path.parent.mkdir();path.write_text('{broken')
    with pytest.raises(ValueError):c.plan(root,config)
