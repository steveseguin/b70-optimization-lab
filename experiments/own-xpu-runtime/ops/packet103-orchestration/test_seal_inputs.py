"""Filesystem admission regressions; no native binary or model executes."""
import json
from pathlib import Path
import pytest
import seal_inputs as s


def fixture(tmp_path, monkeypatch):
    root = tmp_path/'repo'; root.mkdir()
    outside = tmp_path/'original.json'; outside.write_text('{"identity":"original"}')
    original = root/'manifest.json'; original.symlink_to(outside)
    snapshot = root/'snapshot.json'; snapshot.write_bytes(outside.read_bytes())
    receipt = root/'receipt.json'; receipt.write_text('{}')
    helper = root/'helper.py'; helper.write_text('fixture only')
    monkeypatch.setattr(s.o, 'ROOT', root)
    for name, path in [('MANIFEST',original),('SNAPSHOT',snapshot),('RECEIPT',receipt),('__file__',str(helper))]:
        monkeypatch.setattr(s,name,path)
    return root, outside, original, snapshot


def test_snapshot_keeps_original_digest_and_does_not_mutate_proof(tmp_path, monkeypatch):
    root, outside, original, snapshot = fixture(tmp_path, monkeypatch)
    sources = {'manifest.json':s.o.sha(original)}
    projected = s.project(sources)
    assert sources == {'manifest.json':s.o.sha(original)}
    assert projected['snapshot.json'] == s.o.sha(outside)
    assert 'manifest.json' not in projected
    assert all((root/name).resolve().is_relative_to(root) for name in projected)


@pytest.mark.parametrize('changed', ['original','snapshot'])
def test_changed_original_or_snapshot_refuses(tmp_path, monkeypatch, changed):
    root, outside, original, snapshot = fixture(tmp_path, monkeypatch)
    sources = {'manifest.json':s.o.sha(original)}
    (outside if changed == 'original' else snapshot).write_text('changed')
    with pytest.raises(AssertionError):s.project(sources)


def test_unregistered_external_dependency_refuses(tmp_path, monkeypatch):
    root, outside, original, snapshot = fixture(tmp_path, monkeypatch)
    other = root/'other'; other.symlink_to(outside)
    with pytest.raises(AssertionError, match='other'):
        s.project({'manifest.json':s.o.sha(original),'other':s.o.sha(other)})


def test_every_composite_validation_checks_original_startup(monkeypatch):
    import composite_jobs
    def changed():raise ValueError('original startup input changed')
    monkeypatch.setattr(s,'verify',changed)
    with pytest.raises(ValueError,match='original startup input changed'):
        composite_jobs.validate({})


def test_failed_temporary_plan_publishes_no_proposal(tmp_path, monkeypatch):
    import composite_jobs as c
    from types import SimpleNamespace
    queue=tmp_path/'queue';queue.mkdir()
    ops=tmp_path/'ops';ops.mkdir()
    monkeypatch.setattr(c,'O',ops);monkeypatch.setattr(c,'ROOT',tmp_path)
    monkeypatch.setattr(c,'QUEUE',queue);monkeypatch.setattr(c,'WRAPPER',tmp_path)
    monkeypatch.setattr(c,'validate',lambda config:None)
    monkeypatch.setattr(c,'variants',lambda *a:{'composite':{}})
    monkeypatch.setattr(c,'jobs',lambda config,lane,variant:[dict(out='test-'+lane,index=0)])
    def plan(*args,**kwargs):
        assert not list(queue.glob('proposed-p103-*'))
        return SimpleNamespace(returncode=1,stdout='',stderr='synthetic refusal')
    monkeypatch.setattr(c.subprocess,'run',plan)
    with pytest.raises(AssertionError):c.generate({})
    assert not list(queue.glob('proposed-p103-*'))
