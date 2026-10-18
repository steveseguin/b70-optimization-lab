"""Refresh only orchestration bindings; preserve native/startup/selection bytes."""
import json
import time
import orchestrate as o


def main():
    o.limits()  # Explicit CPU-only CLI; never used by a device entry.
    started = time.monotonic()
    from startup_receipt103 import verify as startup
    from bundle_selection import selected
    from composite_jobs import validate
    from decision_readiness import preparation_config
    decision = o.O/'decisions/1ad512f75aab3fce.json'
    config = json.loads(decision.read_text())
    before = json.loads((o.O/'evidence/103x-before.json').read_text())
    preserved = {name: digest for name, digest in before.items()
                 if name.endswith(('startup103.json', 'build-device-receipt.json', '/screen-seal.json',
                                   '/decisions/1ad512f75aab3fce.json'))}
    for name, digest in preserved.items():
        assert o.sha(o.ROOT/name) == digest, name
    startup()
    from historical_pins import ARCHIVED
    originals = {str((o.O/leaf).relative_to(o.ROOT)): o.sha(o.O/'frozen103'/leaf)
                 for leaf in ARCHIVED}
    for key, digest in originals.items():
        if key in config['evidence_pins']:
            assert config['evidence_pins'][key] == digest, key
    o.save(o.O/'103x-policy-seal.json', dict(schema='packet103x.orchestration-reseal.v1',
        device_executed=False, decision_sha256=o.sha(decision), originals=originals,
        current={str(path.relative_to(o.ROOT)): o.sha(path) for path in o.O.glob('*.py')}))
    validate(config)
    choice = selected()
    assert all(choice[k] == value for k, value in config['candidate'].items())
    o.save(o.P/'composition-selection.json', preparation_config(config, decision))
    from screen_jobs import seal_jobs
    seal_jobs()
    from chain_seal import checked, verify
    o.save(o.P/'build-receipt.json', checked())
    from packet56_submission import pin_resealed_packet56
    pin_resealed_packet56()
    verify()
    startup()
    for name, digest in preserved.items():
        assert o.sha(o.ROOT/name) == digest, name
    o.save(o.O/'evidence/103x-reseal.json', dict(passed=True, device_executed=False,
        seconds=time.monotonic()-started, preserved=preserved,
        changed={str((o.P/leaf).relative_to(o.ROOT)): o.sha(o.P/leaf) for leaf in
                 ('composition-selection.json', 'screen-jobs-seal.json', 'build-receipt.json', 'submission-pins.json')}))
    print('Minimal orchestration reseal PASS; 5632 startup receipts and native bytes unchanged', flush=True)


if __name__ == '__main__':
    main()
