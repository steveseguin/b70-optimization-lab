"""Capacity changes between views; maintenance stays fixed."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('18GB','max','smoke')
DEFAULT_MAINTENANCE='overlap'
MAX_BYTES=21552729600
def validate(view):
    if view not in VIEWS:raise ValueError('unsupported cache capacity view')
    row=json.loads((P/'selections/tile16.json').read_text())
    if row!=dict(schema='packet49d.selection.v1',decision=None,choices=dict(
        route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')):
        raise ValueError('immutable tile16 selection changed')
    return row
def selection(view):
    if view=='tile16':view='18GB'
    validate(view);return P/'selections/tile16.json'
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
def bracket(candidate):
    if candidate=='smoke':return [('S0','max')]
    if candidate!='max':raise ValueError('max candidate required')
    return [('A0','18GB'),('B0','max'),('A1','18GB'),('B1','max'),('A2','18GB')]
def write_table(path,candidate,maintenance=DEFAULT_MAINTENANCE):
    if maintenance not in ('serial','overlap'):raise ValueError('unsupported maintenance')
    rows=bracket(candidate)
    path.write_text(''.join(f'{label} {selection(view)} {digest(view)} {maintenance} {view}\n' for label,view in rows))
    return rows
