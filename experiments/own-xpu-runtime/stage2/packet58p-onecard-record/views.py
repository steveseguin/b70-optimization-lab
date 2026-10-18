"""Immutable view names and selection bytes, never mutable orchestration."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=tuple(json.loads((P/'views.json').read_text()))
def selection(view):
 if view not in VIEWS:raise ValueError('unknown packet58j view')
 return P/'selections'/(view+'.json')
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()

def validate(view):
 row=json.loads(selection(view).read_text())
 expected=dict(route='route-exp32-rank4',recurrence='rows4-shared',hc='production',down='down-tile16')
 if row.get('schema')!='packet49d.selection.v1' or row.get('choices')!=expected or row.get('decision') is not None:
  raise ValueError('tile16-only selection must name exactly route/recurrence/hc/down with production route/recurrence/hc')
 return row
