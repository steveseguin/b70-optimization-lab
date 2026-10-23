"""Gate/up kernel changes between views; capacity (max23), maintenance and kernel foreground I/O stay fixed (packet58-onecard-diet-engine)."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('resident','smoke')
CAPACITIES=('max','max23')
GATEUPS=('production','diet')
DEFAULT_MAINTENANCE='overlap'
FOREGROUND='spin-kio'
CAPACITY='max23'   # every view of this screen runs the record capacity (packet58-onecard-cache23-chain, 36.602512 tok/s)
# One arena per load (every view keeps the maximum allocation; the cap limits use, packet58x design).
ALLOCATION_BYTES=23049601024
USABLE={'max':21552729600,'max23':23049601024}
MAX_BYTES=ALLOCATION_BYTES
def view_name(cap,gateup):
    if cap not in CAPACITIES or gateup not in GATEUPS:raise ValueError('unknown capacity/gate-up view')
    return cap if gateup=='production' else cap+'+diet'
def validate(view):
    if view not in VIEWS:raise ValueError('unsupported gate-up bracket view')
    row=json.loads((P/'selections/tile16.json').read_text())
    if row!=dict(schema='packet49d.selection.v1',decision=None,choices=dict(
        route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')):
        raise ValueError('immutable tile16 selection changed')
    return row
def selection(view):
    if view in CAPACITIES or view=='tile16' or view in ('max23+diet',):view='resident'
    validate(view);return P/'selections/tile16.json'
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
def bracket(candidate):
    """(label, capacity, expert_gateup) rows; the native bracket table also carries the fixed spin-kio arm."""
    if candidate=='smoke':return [('S0',CAPACITY,'diet')]
    if candidate!='resident':raise ValueError('diet candidate required')
    # packet58-onecard-diet-engine: A = the record line (max23, production gate/up kernel p58ag_exp); B = max23 + the exact
    # instruction diet p58ag_diet::GateUp selected by expert_gateup=diet at the drained view boundary.
    return [('A0',CAPACITY,'production'),('B0',CAPACITY,'diet'),('A1',CAPACITY,'production'),('B1',CAPACITY,'diet'),('A2',CAPACITY,'production')]
def write_table(path,candidate,maintenance=DEFAULT_MAINTENANCE):
    if maintenance not in ('serial','overlap'):raise ValueError('unsupported maintenance')
    rows=bracket(candidate)
    path.write_text(''.join(f'{label} {selection(cap)} {digest(cap)} {maintenance} {cap} {FOREGROUND} {gateup}\n' for label,cap,gateup in rows))
    return rows
