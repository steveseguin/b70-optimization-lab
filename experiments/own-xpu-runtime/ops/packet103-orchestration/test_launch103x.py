"""Fresh names and historical policy pins; all evidence here is synthetic."""
import json
from pathlib import Path
import pytest
import composite_jobs as c


def config():
    return json.loads((c.O/'decisions/1ad512f75aab3fce.json').read_text())


@pytest.mark.parametrize('lane', ('A', 'B'))
def test_fresh_suffix_preserves_every_selection(lane):
    decision = config()
    old = c.jobs(decision, lane)
    fresh = c.jobs(decision, lane, attempt='x')
    for before, after in zip(old, fresh):
        assert after == dict(before, out=before['out']+'-x')
    assert len({row['out'] for row in old+fresh}) == 6


@pytest.mark.parametrize('suffix', ('../x', 'x/y', '-x', 'x x', ''))
def test_suffix_names_are_closed(suffix):
    if not suffix:
        assert all(not row['out'].endswith('-') for row in c.jobs(config(), 'A'))
    else:
        with pytest.raises(AssertionError): c.jobs(config(), 'A', attempt=suffix)


def test_registered_attempts_keep_old_and_new(tmp_path, monkeypatch):
    decision = config()
    (tmp_path/'decisions').mkdir(); (tmp_path/'attempts').mkdir()
    path = tmp_path/'decisions'/(c.identity(decision)+'.json')
    path.write_text(json.dumps(decision))
    registration = tmp_path/'attempts'/(c.identity(decision)+'-x.json')
    row = dict(decision_sha256=c.sha(path), attempt='x', variants=['composite'])
    registration.write_text(json.dumps(row))
    monkeypatch.setattr(c, 'O', tmp_path)
    assert c.attempts(decision) == ['', 'x']
    assert c.attempts(decision, 'without-100') == ['']
    row['decision_sha256'] = 'changed'
    registration.write_text(json.dumps(row))
    with pytest.raises(AssertionError): c.attempts(decision)


def test_historical_projection_accepts_only_original_bytes(tmp_path, monkeypatch):
    import historical_pins as h
    monkeypatch.setattr(h, 'O', tmp_path)
    monkeypatch.setattr(h, 'ROOT', tmp_path)
    (tmp_path/'frozen103').mkdir()
    path = tmp_path/'read_screens.py'; path.write_text('current')
    archive = tmp_path/'frozen103/read_screens.py'; archive.write_text('original')
    pins = {'read_screens.py': c.sha(archive)}
    seal = tmp_path/'103x-policy-seal.json'
    seal.write_text(json.dumps(dict(schema='packet103x.orchestration-reseal.v1',
                    originals=pins, current={'read_screens.py': c.sha(path)})))
    assert h.preserved_pins(pins) == {'frozen103/read_screens.py': c.sha(archive),
                                     'read_screens.py': c.sha(path),
                                     '103x-policy-seal.json': c.sha(seal)}
    row = json.loads(seal.read_text())
    row['current']['native.cpp'] = 'cannot-repin-native'
    seal.write_text(json.dumps(row))
    with pytest.raises(AssertionError, match='scope differs'): h.preserved_pins(pins)
    del row['current']['native.cpp']
    seal.write_text(json.dumps(row))
    archive.write_text('wrong')
    with pytest.raises(AssertionError): h.preserved_pins(pins)


def test_readiness_counts_both_attempts_and_pins_registration(tmp_path, monkeypatch):
    import decision_readiness as d
    import compare
    decision = config()
    (tmp_path/'decisions').mkdir(); (tmp_path/'attempts').mkdir()
    path = tmp_path/'decisions'/(c.identity(decision)+'.json')
    path.write_text(json.dumps(decision))
    registration = tmp_path/'attempts'/(c.identity(decision)+'-x.json')
    registration.write_text(json.dumps(dict(decision_sha256=c.sha(path), attempt='x', variants=['composite'])))
    expected = {key: key for key in d.IDENTITY_FIELDS}
    for attempt in ('', 'x'):
        for lane in ('A', 'B'):
            for job in c.jobs(decision, lane, attempt=attempt):
                root = tmp_path/'evidence'/job['out']; root.mkdir(parents=True)
                (root/'window.json').write_text(json.dumps(dict(finished_utc_ns=1, child_still_running=False)))
                (root/'identity.json').write_text(json.dumps(expected))
    monkeypatch.setattr(c, 'O', tmp_path); monkeypatch.setattr(c, 'WRAPPER', tmp_path)
    monkeypatch.setattr(d.o, 'O', tmp_path); monkeypatch.setattr(d.o, 'ROOT', tmp_path)
    monkeypatch.setattr(d, 'validate', lambda config: None)
    monkeypatch.setattr(d, 'sealed_identity', lambda selection: expected)
    monkeypatch.setattr(compare, 'load', lambda job: dict(job))
    brackets, excluded, receipts = d.collect(decision)
    assert not excluded
    assert {(row['attempt'], row['lane']) for row in brackets} == {('', 'A'), ('', 'B'), ('x', 'A'), ('x', 'B')}
    assert receipts[str(registration.relative_to(tmp_path))] == c.sha(registration)
