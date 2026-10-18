"""Immutable view names and selection bytes, never mutable orchestration."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=tuple(json.loads((P/'views.json').read_text()))
def selection(view):
 if view not in VIEWS:raise ValueError('unknown packet58j view')
 return P/'selections'/(view+'.json')
def digest(view):return hashlib.sha256(selection(view).read_bytes()).hexdigest()
