"""Capacity changes between views; maintenance and kernel foreground I/O stay fixed (packet58-cache23)."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('resident','smoke')
CAPACITIES=('max','max23')
DEFAULT_MAINTENANCE='overlap'
FOREGROUND='spin-kio'
# One arena per load (every view keeps the maximum allocation; the cap limits use, packet58x design).
ALLOCATION_BYTES=23049601024
USABLE={'max':21552729600,'max23':23049601024}
MAX_BYTES=ALLOCATION_BYTES
def validate(view):
    if view not in VIEWS:raise ValueError('unsupported capacity bracket view')
    row=json.loads((P/'selections/tile16.json').read_text())
    if row!=dict(schema='packet49d.selection.v1',decision=None,choices=dict(
        route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')):
        raise ValueError('immutable tile16 selection changed')
    return row
def selection(view):
    if view in CAPACITIES or view=='tile16':view='resident'
    validate(view);return P/'selections/tile16.json'
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
def bracket(candidate):
    """(label, capacity) rows; the native bracket table also carries the fixed spin-kio arm."""
    if candidate=='smoke':return [('S0','max23')]
    if candidate!='resident':raise ValueError('max23 candidate required')
    # packet58-cache23: A = packet182c record line (max = 21,552,729,600 usable); B = max23 (the full 23,049,601,024-byte arena).
    return [('A0','max'),('B0','max23'),('A1','max'),('B1','max23'),('A2','max')]
def write_table(path,candidate,maintenance=DEFAULT_MAINTENANCE):
    if maintenance not in ('serial','overlap'):raise ValueError('unsupported maintenance')
    rows=bracket(candidate)
    path.write_text(''.join(f'{label} {selection(cap)} {digest(cap)} {maintenance} {cap} {FOREGROUND}\n' for label,cap in rows))
    return rows
