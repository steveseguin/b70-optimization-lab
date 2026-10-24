"""Pinned local CPU tokenizer; exact target GGUF text template, no model I/O."""
from pathlib import Path
import hashlib,json,sys
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
TOKENIZER=Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8/tokenizer.json')
TOKENIZER_SHA='0997f410c57a1f4e53b09e4be8f4a172d90edd9564368fb0847030937229b9f3'
CENSUS=L/'metadata/new-census.json';CENSUS_SHA='b47eae82a10854f47f23acc96e44d920a8b04ea1511f100aa1395418c41ca8a1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def load():
 if sha(TOKENIZER)!=TOKENIZER_SHA or sha(CENSUS)!=CENSUS_SHA:raise ValueError('fixed tokenizer/census changed')
 sys.path.extend(str(p) for p in Path('/home/steve/.venvs/vllm-xpu/lib').glob('python*/site-packages'))
 import tokenizers
 from tokenizers import Tokenizer
 from jinja2.sandbox import ImmutableSandboxedEnvironment
 raw=json.loads(TOKENIZER.read_text());meta=json.loads(CENSUS.read_text())['metadata']
 vocab=[None]*248320
 for word,i in raw['model']['vocab'].items():vocab[i]=word
 for t in raw['added_tokens']:vocab[t['id']]=t['content']
 for i in range(len(vocab)):
  if vocab[i] is None:vocab[i]=f'[PAD{i}]'
 for key,value in [('tokenizer.ggml.tokens',vocab),('tokenizer.ggml.merges',raw['model']['merges'])]:
  if hashlib.sha256(canonical(value)).hexdigest()!=meta[key]['canonical_json_sha256']:raise ValueError('full tokenizer metadata mismatch '+key)
 template=meta['tokenizer.chat_template']['value']
 if hashlib.sha256(canonical(template)).hexdigest()!=meta['tokenizer.chat_template']['canonical_json_sha256']:raise ValueError('template mismatch')
 env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
 def fail(message):raise ValueError(message)
 env.globals['raise_exception']=fail
 compiled=env.from_string(template);tok=Tokenizer.from_file(str(TOKENIZER))
 def render(text):return compiled.render(messages=[{'role':'user','content':text}],add_generation_prompt=True,enable_thinking=False,tools=None)
 return tok,render,dict(tokenizers_version=tokenizers.__version__,tokenizer_sha256=TOKENIZER_SHA,census_sha256=CENSUS_SHA,vocab_and_merges_exact=True,chat_template_sha256=meta['tokenizer.chat_template']['canonical_json_sha256'])
def decode(ids):
 tok,_,_=load()
 if not all(type(i)is int and 0<=i<248320 for i in ids):raise ValueError('output token range')
 # Preserve special token spelling, including GGUF padding absent in HF vocab.
 chunks=[];part=[]
 for i in ids:
  if i>=248077:
   chunks.append(tok.decode(part,skip_special_tokens=False));part=[];chunks.append(f'[PAD{i}]')
  else:part.append(i)
 chunks.append(tok.decode(part,skip_special_tokens=False));return ''.join(chunks)
