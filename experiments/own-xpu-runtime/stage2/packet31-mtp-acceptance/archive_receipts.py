"""Losslessly compress range-hash ledgers, verify bytes, update build receipt."""
from pathlib import Path
import gzip,hashlib,json
P=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    receipt=json.loads((P/"build-receipt.json").read_text())
    for key in ("tensor_range_hashes_file","iq3_binding_range_hashes_file"):
        item=receipt[key];src=P/item["path"]
        if src.suffix==".gz":continue
        raw=src.read_bytes();assert sha(raw)==item["sha256"]
        dst=src.with_suffix(src.suffix+".gz")
        with dst.open("wb") as f:
            with gzip.GzipFile(filename="",mode="wb",fileobj=f,mtime=0) as out:out.write(raw)
        with gzip.open(dst,"rb") as f:assert f.read()==raw
        receipt[key]=dict(path=dst.name,sha256=sha(dst.read_bytes()),uncompressed_sha256=sha(raw),uncompressed_bytes=len(raw),roundtrip_verified=True)
        src.unlink()
    (P/"build-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
if __name__=="__main__":main()
