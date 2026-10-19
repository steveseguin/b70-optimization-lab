"""Restore only this packet's immutable binaries from its vendored archive."""
import argparse,hashlib,json,os,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args()
    row=json.loads((P/'native-artifacts.json').read_text());archive=P/row['archive']
    assert sha(archive)==row['archive_sha256']
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers();assert {m.name for m in members}==set(row['files'])
        for member in members:
            assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            path=P/member.name;raw=tar.extractfile(member).read()
            assert hashlib.sha256(raw).hexdigest()==row['files'][member.name]
            if path.exists():assert sha(path)==row['files'][member.name],'refuse overwrite of different bytes'
            elif a.verify:raise ValueError('missing binary: '+member.name)
            else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o755)
    print(json.dumps(dict(passed=True,device_executed=False,files=len(members),restore=not a.verify)))
if __name__=='__main__':main()
