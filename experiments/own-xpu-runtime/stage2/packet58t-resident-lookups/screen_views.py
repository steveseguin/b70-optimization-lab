"""58r one-load view protocol, copied here because the parent is frozen."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('resident',)
def selection(view):
    if view not in ('tile16','resident'):raise ValueError('unknown lookup view')
    return P/'selections/tile16.json'
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
def validate(view):
    row=json.loads(selection(view).read_text())
    assert row['choices']==dict(route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')
    return row
def bracket(candidate):
    if candidate!='resident':raise ValueError('resident candidate required')
    return [('A0','tile16'),('B0','resident'),('A1','tile16')]
def write_table(path,candidate):
    rows=bracket(candidate)
    path.write_text(''.join(f'{label} {selection(view)} {digest(view)} {int(view=="resident")}\n' for label,view in rows))
    return rows
