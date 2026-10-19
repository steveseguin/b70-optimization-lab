"""Passive packet metadata helpers; no preparation, compiler or device imports."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
AH=P.parent/'packet58ah-onecard-record'
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')
