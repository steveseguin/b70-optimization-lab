"""Exact512 real-document prefix, following the lab's unrepeated prefill method."""
import hashlib,json,resource,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
sys.path.extend(str(p)for p in Path('/home/steve/.venvs/vllm-xpu/lib').glob('python*/site-packages'))
from tokenizers import Tokenizer
path=Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/tokenizer.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(path)=='0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3'
tok=Tokenizer.from_file(str(path))
corpus=ROOT/'experiments/qwen38-27b-b70/data/2026-09-13-prefill-followup-corpus.json'
data=json.loads(corpus.read_text());assert data['source_repetition']is False
source=data['sources'][0];text=source['text'];assert hashlib.sha256(text.encode()).hexdigest()==source['text_sha256']
ids=tok.encode(text,add_special_tokens=False).ids;assert len(ids)>=512
ids=ids[:512]
checks=[]
for inp in(P/'two-card/inputs').glob('*/input.json'):
 row=json.loads(inp.read_text());prompt=Path(row['prompt'])
 actual=tok.encode(prompt.read_text(),add_special_tokens=False).ids
 assert actual==row['tokens'],inp
 checks.append(dict(prompt_id=inp.parent.name,tokens=len(actual),passed=True))
for name in('one-card','two-card'):
 out=P/name/'inputs/prefill512';out.mkdir(exist_ok=True)
 (out/'tokens.txt').write_text(' '.join(map(str,ids))+'\n')
 (out/'source.txt').write_text(text)
 (out/'input.json').write_text(json.dumps(dict(tokens=ids,source_text_sha256=source['text_sha256'],input_tokens=512,add_special_tokens=False),indent=2)+'\n')
receipt=dict(passed=True,device_executed=False,model_payload_read=False,tokenizer=str(path),tokenizer_sha256=sha(path),
 tokenizer_verified_against_all12_registered_inputs=checks,corpus=str(corpus.relative_to(ROOT)),corpus_sha256=sha(corpus),
 corpus_label=source['label'],source_path=source['source_path'],source_repetition=False,source_text_sha256=source['text_sha256'],
 construction='first exactly512 numeric token IDs, no special tokens, unrepeated contiguous source excerpt',
 method='experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py:123-137',
 timing='native prompt loop start through first generated token;512/seconds; separate request TTFT',
 oracle_coverage=False,decoded_prefix=tok.decode(ids,skip_special_tokens=False),input_tokens=512)
(P/'evidence/prefill-input.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS exact512, official tokenizer matches12 registered prompts; no model reads')
