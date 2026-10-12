"""Remove only packet31 scratch after complete hash-bound results exist."""
import gzip,hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/"build"
def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
    assert B.is_dir() and not B.is_symlink()
    acceptance=json.loads((P/"acceptance.json").read_text());assert len(acceptance["positions"])==256
    gates=json.loads((P/"target-gates.json").read_text());assert gates["incident-retrospective"]["sealed_64_tokens_exact"]
    run=json.loads((P/"target-run-receipt.json").read_text());assert len(run["prompts"])==4
    assert all(r.get("returncode")==0 for r in run["prompts"].values())
    for r in run["prompts"].values():
        status=Path(f"/proc/{r['pid']}/cmdline")
        assert not status.exists() or str(B/"target-cpu").encode() not in status.read_bytes()
    entries={str(f.relative_to(B)):dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(B.rglob("*")) if f.is_file()}
    raw=(json.dumps(entries,sort_keys=True,indent=2)+"\n").encode()
    archive=P/"scratch-inventory.json.gz"
    with archive.open("wb") as f:
        with gzip.GzipFile(filename="",mode="wb",fileobj=f,mtime=0) as out:out.write(raw)
    with gzip.open(archive,"rb") as f:assert f.read()==raw
    receipt=dict(removed="build/",files=len(entries),bytes=sum(v["bytes"] for v in entries.values()),inventory=archive.name,inventory_sha256=sha(archive),
        restoration="reproduce.sh regenerates all scratch; target streams are hash-bound in target-gates.json",preserved=["acceptance.json","target-evidence.json","target-gates.json","target-build-receipt.json","build-receipt.json"],device_executed=False)
    shutil.rmtree(B)
    (P/"cleanup.json").write_text(json.dumps(receipt,indent=2)+"\n")
if __name__=="__main__":main()
