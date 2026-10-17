#!/usr/bin/env python3
"""Tokenize independent calibration text from admitted GGUF headers only."""
import hashlib,json,os,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4];BASE=P.parents[1]/'packet49c-round2'
MODEL=Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS')
sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/stage1/packet1b'))
from loaders.headers import gguf_header
sys.path.insert(0,str(ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle'))
from tokenizer import Tokenizer

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    base=BASE/'build/input';authority=json.loads((base/'input.json').read_text())
    assert Path(authority['model_dir']).resolve()==MODEL
    for line in (base/'identity.tsv').read_text().splitlines():
        name,size,dev,ino,mtime,ctime=line.split();st=(MODEL/name).stat()
        assert (st.st_size,st.st_dev,st.st_ino,st.st_mtime_ns,st.st_ctime_ns)==tuple(map(int,(size,dev,ino,mtime,ctime)))
    first=next(MODEL.glob('*00001-of-00003.gguf'))
    with first.open('rb') as f:header=gguf_header(f,first.stat().st_size)
    with first.open('rb') as f:raw=f.read(header['header_bytes_read'])
    assert hashlib.sha256(raw).hexdigest()==authority['header_sha256']
    tokenizer=Tokenizer(header['metadata']);manifest=json.loads((P/'calibration-prompts.json').read_text())
    suite=json.loads((BASE/'oracle/results/suite-manifest.json').read_text())
    forbidden=[tuple(map(int,(ROOT/r['input_bundle']/'tokens.txt').read_text().split())) for r in suite['prompts']]
    for entry in manifest['prompts']:
        ids=tokenizer.encode(entry['text']);assert tokenizer.decode(ids)==entry['text'] and 0<len(ids)<1024
        assert not any(tuple(ids)==ref or any(tuple(ids[i:i+len(ref)])==ref for i in range(len(ids)-len(ref)+1)) for ref in forbidden)
        entry.update(tokens=ids,prompt_tokens=len(ids),prompt_sha256=hashlib.sha256(entry['text'].encode()).hexdigest())
    out=P/'build/input';out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.tsv','identity.tsv','vocab.bin','input.json','tokens.txt'):(out/name).write_bytes((base/name).read_bytes())
    manifest.update(model_dir=str(MODEL),header_sha256=hashlib.sha256(raw).hexdigest(),header_bytes_read=header['header_bytes_read'],
                    benchmark_prompt_overlap=False,source_sha256=hashlib.sha256((P/'calibration-prompts.json').read_bytes()).hexdigest())
    (P/'build/calibration-tokenized.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(prompts=24,train=12,test=12,max_prompt_tokens=max(r['prompt_tokens'] for r in manifest['prompts']),model_payload_bytes_read=0,header_bytes_read=2*len(raw))))
if __name__=='__main__':main()
