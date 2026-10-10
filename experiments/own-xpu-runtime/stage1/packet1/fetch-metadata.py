#!/usr/bin/env python3
"""Packet 1 only: official JSON/text metadata and exact header ranges, no payload.

Original lab implementation. Format reference:
https://huggingface.co/docs/safetensors/main/en/metadata_parsing
No model/runtime imports, device access, tokenizer execution or weight reads.
"""
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request

REPO = "Qwen/Qwen3.8-27B-FP8"
REV = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
BASE = f"https://huggingface.co/{REPO}/resolve/{REV}/"
OUT = Path(__file__).resolve().parent / "metadata"
LIMIT = 2_000_000


def fetch(url, start=None, end=None, total=None):
    headers = {"Accept-Encoding": "identity"}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        if start is not None:
            expected = f"bytes {start}-{end}/{total}"
            actual = response.headers.get("Content-Range", "")
            if response.status != 206 or actual != expected:
                raise ValueError(f"Refused range response before body read: {response.status} {actual}")
            size = end - start + 1
            if int(response.headers.get("Content-Length", -1)) != size:
                raise ValueError("Range length mismatch")
            body = response.read(size)
            if len(body) != size:
                raise ValueError("Truncated range")
        else:
            body = response.read(LIMIT + 1)
            if len(body) > LIMIT:
                raise ValueError("Metadata size limit exceeded")
        return body


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "headers").mkdir(exist_ok=True)
    receipt = {"repository": REPO, "revision": REV,
               "retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "scope": "JSON/text metadata and safetensors headers only; zero tensor payload bytes",
               "sources": []}

    def save(path, body, url, **extra):
        (OUT / path).write_bytes(body)
        receipt["sources"].append({"path": path, "url": url, "bytes": len(body),
                                   "sha256": hashlib.sha256(body).hexdigest(), **extra})

    api_url = f"https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true"
    api_body = fetch(api_url)
    api = json.loads(api_body)
    if api["sha"] != REV or api["id"] != REPO:
        raise ValueError("Wrong publisher identity")
    save("hf-model-info.json", api_body, api_url)
    files = {f["rfilename"]: f for f in api["siblings"]}
    for filename in ("config.json", "model.safetensors.index.json", "tokenizer_config.json",
                     "generation_config.json", "chat_template.jinja"):
        body = fetch(BASE + filename)
        info = files[filename]
        git_hash = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
        if len(body) != info["size"] or git_hash != info["blobId"]:
            raise ValueError(f"Publisher blob mismatch: {filename}")
        save(filename, body, BASE + filename, git_blob_sha1=git_hash)
    index = json.loads((OUT / "model.safetensors.index.json").read_bytes())
    for shard in sorted(set(index["weight_map"].values())):
        if "/" in shard or not shard.endswith(".safetensors"):
            raise ValueError("Unexpected shard path")
        total = files[shard]["size"]
        url = BASE + shard
        prefix = fetch(url + "?packet1=length", 0, 7, total)
        length = int.from_bytes(prefix, "little")
        if not 2 <= length <= LIMIT or length + 8 >= total:
            raise ValueError("Invalid header bound")
        body = fetch(url + "?packet1=header", 8, 7 + length, total)
        json.loads(body)
        save("headers/" + shard + ".json", body, url,
             prefix_range=[0, 7], prefix_hex=prefix.hex(), header_range=[8, 7 + length],
             header_bytes=length, file_bytes=total,
             publisher_lfs_sha256=files[shard]["lfs"]["sha256"],
             payload_sha256_verified=False)
    (OUT / "fetch-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"metadata_files": len(receipt["sources"]),
                      "metadata_bytes": sum(s["bytes"] for s in receipt["sources"]),
                      "tensor_payload_bytes_read": 0}))


if __name__ == "__main__":
    main()
