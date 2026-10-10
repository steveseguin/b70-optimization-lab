#!/usr/bin/env python3
"""Capture LOCAL headers and small metadata, and official HF metadata; never weights.
Only explicit invocation writes this packet. Standard library, no model imports.
"""
import datetime, gzip, hashlib, json, os, pathlib, struct, subprocess, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
MODEL = pathlib.Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
REV = 'bcd9f01ddc9cff2316eb84281bebcd5b058bddce'
REPO = 'Qwen/Qwen3.8-Flash-Next-FP8'
KEEP = {'config.json','tokenizer_config.json','generation_config.json','chat_template.jinja','model.safetensors.index.json'}
def sha(b): return hashlib.sha256(b).hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    assert subprocess.check_output(['ionice','-p',str(os.getpid())],text=True).strip() == 'idle'
    out = HERE/'metadata'; (out/'headers').mkdir(parents=True,exist_ok=True)
    records=[]
    for f in sorted(MODEL.iterdir()):
        if not f.is_file(): continue
        is_shard=f.suffix=='.safetensors'
        if is_shard:
            # buffering=0 prevents a buffered read from fetching payload bytes.
            with f.open('rb',buffering=0) as stream:
                prefix=stream.read(8); assert len(prefix)==8
                n=struct.unpack('<Q',prefix)[0]; assert 2 <= n <= 16_000_000
                b=stream.read(n); assert len(b)==n
                assert stream.tell()==8+n
            dest='headers/'+f.name+'.header.json.gz'
        else:
            assert f.stat().st_size < 32_000_000, 'unexpected non-header file'
            b=f.read_bytes(); dest=f.name if f.name in KEEP else None
            if f.name=='model.safetensors.index.json': dest += '.gz'
        if dest:
            (out/dest).write_bytes(gzip.compress(b,mtime=0) if dest.endswith('.gz') else b)
        metadata=MODEL/'.cache/huggingface/download'/(f.name+'.metadata')
        records.append(dict(name=f.name,file_bytes=f.stat().st_size,snapshot=dest,
                            snapshot_sha256=sha(b),git_blob_sha1=None if is_shard else hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),
                            download_metadata=metadata.read_text()))
    url=f'https://huggingface.co/api/models/{REPO}/revision/{REV}?blobs=true'
    b=urllib.request.urlopen(url,timeout=40).read(); (out/'hf-model-info.json').write_bytes(b)
    # Independent publisher metadata fetch; no safetensors resolve request exists.
    remote=[]
    for name in sorted(KEEP-{'model.safetensors.index.json'}):
        u=f'https://huggingface.co/{REPO}/resolve/{REV}/{name}'
        body=urllib.request.urlopen(u,timeout=40).read()
        assert body==(out/name).read_bytes(), 'publisher metadata differs: '+name
        remote.append(dict(name=name,url=u,sha256=sha(body),bytes=len(body)))
    receipt=dict(source=str(MODEL),revision=REV,hf_url=url,hf_sha256=sha(b),
                 captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 method='Unbuffered 8-byte length then bounded header only for safetensors; nonweight root metadata hashed; no tensor payload reads.',
                 files=records,publisher_metadata_checks=remote,nice=19,ionice='idle',OMP_NUM_THREADS=2)
    (out/'local-metadata-receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('Captured',len(records),'root metadata records; HF and local metadata agree.')
if __name__=='__main__': main()
