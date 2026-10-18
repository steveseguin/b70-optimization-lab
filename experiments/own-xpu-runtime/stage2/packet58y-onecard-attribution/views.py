"""Only maintenance changes; every arm retains the exact tile16 selection."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('serial','overlap','smoke','attrib')
def validate(view):
    if view not in VIEWS:raise ValueError('unsupported cache maintenance view')
    row=json.loads((P/'selections/tile16.json').read_text())
    if row!=dict(schema='packet49d.selection.v1',decision=None,choices=dict(
        route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')):
        raise ValueError('immutable tile16 selection changed')
    return row
def selection(view):
    if view=='tile16':view='serial'
    validate(view);return P/'selections/tile16.json'
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
def bracket(candidate):
    if candidate=='attrib':return [('D0','overlap')]
    if candidate=='smoke':return [('S0','overlap')]
    if candidate!='overlap':raise ValueError('overlap candidate required')
    return [('A0','serial'),('B0','overlap'),('A1','serial'),('B1','overlap'),('A2','serial')]
def write_table(path,candidate):
    rows=bracket(candidate)
    path.write_text(''.join(f'{label} {selection(view)} {digest(view)} {view}\n' for label,view in rows))
    return rows
