"""Read-only shared-wrapper verification. Never reseals or writes shared files."""
import json
from pathlib import Path
from chain_seal import check_map
P=Path(__file__).resolve().parent
def wrapper_seal():
    row=json.loads((P/'shared-wrapper-pin.json').read_text())
    check_map(P.parents[3],row['sources'])
    return row
