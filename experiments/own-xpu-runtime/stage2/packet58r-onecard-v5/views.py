"""Four kernel selections on one immutable tile16 storage layout."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
VIEWS = ('tile16', 'route-fast', 'rec-both-plus', 'route-rec')


def validate(view):
    if view not in VIEWS:
        raise ValueError('unsupported one-card view; other_fusion is unavailable')
    row = json.loads((P/'selections'/f'{view}.json').read_text())
    expected = dict(route='route-fast' if view in ('route-fast', 'route-rec') else 'route-exp32-rank4',
                    recurrence='rec-both-plus' if view in ('rec-both-plus', 'route-rec') else 'rows4-shared',
                    hc='production', down='down-tile16')
    if row != dict(schema='packet49d.selection.v1', choices=expected, decision=None):
        raise ValueError('view must preserve the exact tile16 selection')
    return row


def selection(view):
    validate(view)
    return P/'selections'/f'{view}.json'


def digest(view):
    return hashlib.sha256(selection(view).read_bytes()).hexdigest()


def bracket(candidate):
    if candidate not in VIEWS[1:]:
        raise ValueError('candidate must change a registered kernel')
    return [('A0', 'tile16'), ('B0', candidate), ('A1', 'tile16'),
            ('B1', candidate), ('A2', 'tile16')]


def write_table(path, candidate):
    rows = bracket(candidate)
    path.write_text(''.join(f'{label} {selection(view)} {digest(view)}\n' for label, view in rows))
    return rows
