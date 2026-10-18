"""Pinned non-secret native environment, independent of temporary env files."""
import json,os
from pathlib import Path
P=Path(__file__).resolve().parent
def apply():
 row=json.loads((P/'launch-environment.json').read_text())
 assert set(row)=={'PATH','OMP_NUM_THREADS','LD_LIBRARY_PATH'} and row['OMP_NUM_THREADS']=='2'
 assert all(Path(p).is_absolute() and Path(p).is_dir() for p in row['LD_LIBRARY_PATH'].split(':'))
 os.environ.update(row)
 return row
