"""Independent CPU typed-event refusal checks; no native transport or GPU work."""
from dataclasses import replace
from pathlib import Path
import hashlib
import json

from test_coordinator import fixture, run


def check_provider(field, value):
    c, workers = fixture(4)
    original = c.complete_provider
    observed = []

    def complete(command, **kwargs):
        if not command.row.fixture:
            return original(command, **kwargs)
        before = (c.provider.serial, c.proposals.last_batch_ticket)
        kwargs[field] = value(kwargs[field])
        try:
            original(command, **kwargs)
        except ValueError:
            assert (c.provider.serial, c.proposals.last_batch_ticket) == before
            assert c.stages[0].busy is command and c.provider.job is not None
            assert c.failed and c.provider.failed
            observed.append(True)
            raise
        raise AssertionError('malformed provider result accepted')

    c.complete_provider = complete
    try:
        run(c, workers, random_seed=7)
    except ValueError:
        assert observed
    else:
        raise AssertionError('provider mutation was not reached')


def check_parent(field):
    c, workers = fixture(4)
    original = c.complete
    observed = []

    def complete(command, ack, *, final_parent=None):
        if final_parent is None:
            return original(command, ack, final_parent=final_parent)
        value = getattr(final_parent, field)
        value = replace(value, identity=value.identity+1) if field == 'row' else value+1
        before = c.stages[command.stage].committed
        try:
            original(command, ack, final_parent=replace(final_parent, **{field: value}))
        except ValueError:
            assert c.stages[command.stage].committed == before
            assert c.stages[command.stage].busy is command
            assert c.failed and c.provider.failed
            observed.append(True)
            raise
        raise AssertionError('malformed final parent accepted')

    c.complete = complete
    try:
        run(c, workers, random_seed=7)
    except ValueError:
        assert observed
    else:
        raise AssertionError('parent mutation was not reached')


def main():
    mutations = [
        ('provider_serial', lambda x: x+1),
        ('restored_position', lambda x: x+1),
        ('physical', lambda x: x+1),
        ('committed', lambda x: x+1),
        ('pending_rows', lambda x: tuple(x)+(999999,)),
        ('guesses', list),
        ('guesses', lambda x: (True,)),
        ('guesses', lambda x: (-1,)),
        ('guesses', lambda x: (97,)),
        ('guesses', lambda x: (1, 2, 3)),
        ('guesses', lambda x: ()),
    ]
    for field, value in mutations:
        check_provider(field, value)
    for field in ('row', 'final_row_ticket', 'final_commit_sequence'):
        check_parent(field)
    root = Path(__file__).resolve().parent
    sources = [root / name for name in (
        'arbiter.py', 'coordinator.py', 'test_coordinator.py', 'review_provenance.py')]
    sources += [root.parent / name for name in ('ring_contract.py', 'ring_coordinator.py', 'test_ring_coordinator.py')]
    print(json.dumps({'schema': 'ownrt.rolling-typed-provenance-review.v1',
        'passed': True, 'negative_cases': len(mutations)+3,
        'scope': 'CPU typed-event rejection only; native codecs and raw-record authentication remain external',
        'source_sha256': {str(p.relative_to(root.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sources}}, indent=2))


if __name__ == '__main__':
    main()
