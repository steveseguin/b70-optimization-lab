"""Private closure verification, without model/full-shape reads."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def verify():
    row=json.loads((P/'build-receipt.json').read_text())
    if row.get('passed') is not True:raise ValueError('CPU build incomplete')
    for base,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):
        if not row.get(key):raise ValueError('empty closure')
        for name,digest in row[key].items():
            if sha(base/name)!=digest:raise ValueError('changed sealed input: '+name)
    return row
