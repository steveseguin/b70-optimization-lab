"""Frozen suite renderer/tokenizer and packet29 bundle builder; CPU only."""
import gzip,hashlib,importlib.util,io,json,os,subprocess,sys
from pathlib import Path
from jinja2.sandbox import ImmutableSandboxedEnvironment
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
LANE=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70'
INPUTS=ROOT/'experiments/own-xpu-runtime/stage2/long-inputs-20261012'
PREFIX=['nice','-n','19','ionice','-c','3']
def sha(b):return hashlib.sha256(b).hexdigest()
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert int(subprocess.check_output(PREFIX+['df','-B1','/'],text=True).splitlines()[-1].split()[3])>=8_000_000_000
 suite=json.loads((LANE/'packet2-cpu-oracle/prompts/prompts.json').read_text())
 header=ROOT/suite['header_path'];raw=gzip.decompress(header.read_bytes())
 parser=ROOT/'experiments/own-xpu-runtime/stage1/packet1b/loaders/headers.py'
 meta=load('headers_long',parser).gguf_header(io.BytesIO(raw),10946624)['metadata']
 assert sha(header.read_bytes())==suite['header_sha256'] and sha(parser.read_bytes())==suite['parser_sha256']
 assert sha(meta['tokenizer.chat_template'].encode())==suite['template_sha256']
 renderer=ImmutableSandboxedEnvironment().from_string(meta['tokenizer.chat_template'])
 tok=load('tokenizer_long',LANE/'packet2-cpu-oracle/tokenizer.py').Tokenizer(meta)
 def render(s):return renderer.render(messages=[dict(role='user',content=s)],add_generation_prompt=True,enable_thinking=False)
 # Replay every suite rendering before using the exact same template for new text.
 original=json.loads((ROOT/suite['suite_path']).read_text())
 for row,ref in zip(original['prompts'],suite['prompts']):assert sha(render(row['prompt']).encode())==ref['rendered_sha256']
 cp=ROOT/'experiments/qwen38-27b-b70/data/2026-09-17-long-corpus/corpus.json'
 corpus=json.loads(cp.read_text());prose=next(s for s in corpus['sources'] if s['label']=='prose')
 assert corpus['source_repetition'] is False and sha(prose['text'].encode())==prose['text_sha256']
 # Recover exact historical source bytes by their recorded digest, without writing elsewhere.
 files=[];parts=[]
 for item in prose['source_files']:
  path=ROOT/item['path'];data=path.read_bytes();rev='working-tree'
  if sha(data)!=item['sha256']:
   revisions=subprocess.check_output(PREFIX+['git','log','--format=%H','--',item['path']],cwd=ROOT,text=True).splitlines()
   for rev in revisions:
    data=subprocess.check_output(PREFIX+['git','show',rev+':'+item['path']],cwd=ROOT)
    if sha(data)==item['sha256']:break
   else:raise RuntimeError('cannot recover corpus source '+item['path'])
  assert sha(data)==item['sha256'];parts.append(data.decode());files.append(dict(**item,revision=rev))
 assert '\n\n'.join(parts)==prose['text']
 prep_path=ROOT/'experiments/own-xpu-runtime/stage2/packet29-merged/prepare.py'
 prep=load('prepare_packet29',prep_path)
 # Keep the exact builder; prefix its ionice inspection as required for every subprocess.
 original_check_output=subprocess.check_output
 def checked(cmd,*a,**kw):return original_check_output(cmd if cmd[:len(PREFIX)]==PREFIX else PREFIX+cmd,*a,**kw)
 subprocess.check_output=checked
 prompts=[]
 for label,target,source_index in [('LONG-A',600,0),('LONG-B',2300,1)]:
  doc=parts[source_index];prefix='Summarize the following document in about 200 words.\n\n'
  # Choose a paragraph boundary if it fits, otherwise a word boundary; never repeat text.
  candidates=[j for j in range(1,len(doc)+1) if j==len(doc) or doc[j-1].isspace()]
  lo,hi=0,len(candidates)-1
  while lo<hi:
   mid=(lo+hi+1)//2;n=len(tok.encode(render(prefix+doc[:candidates[mid]].rstrip())))
   if n<=target:lo=mid
   else:hi=mid-1
  end=candidates[lo];excerpt=doc[:end].rstrip();rendered=render(prefix+excerpt);ids=tok.encode(rendered)
  assert abs(len(ids)-target)<= (20 if label=='LONG-A' else 50) and tok.decode(ids)==rendered
  prompt=INPUTS/(label+'.txt');prompt.write_text(rendered)
  temporary=INPUTS/('.'+label+'.partial-input');receipt=prep.prepare(temporary,prompt)
  assert receipt['tokens']==ids
  temporary.rename(INPUTS/label)
  prompts.append(dict(id=label,file=str(prompt),rendered_sha256=sha(rendered.encode()),raw_sha256=sha((prefix+excerpt).encode()),document_sha256=sha(excerpt.encode()),prompt_tokens=len(ids),document_tokens=len(tok.encode(excerpt)),source_files=[files[source_index]],source_char_start=0,source_char_end=len(excerpt),corpus_text_char_start=sum(len(s)+2 for s in parts[:source_index]),source_repetition=False))
 manifest=dict(schema='iq3-long-prompts.v1',corpus_path=str(cp.relative_to(ROOT)),corpus_sha256=sha(cp.read_bytes()),corpus_builder_sha256=sha((ROOT/'experiments/qwen38-27b-b70/scripts/build-long-corpus.py').read_bytes()),class_name='prose',source_repetition=False,header_path=suite['header_path'],header_sha256=suite['header_sha256'],template_sha256=suite['template_sha256'],tokenizer_path=str((LANE/'packet2-cpu-oracle/tokenizer.py').relative_to(ROOT)),tokenizer_sha256=sha((LANE/'packet2-cpu-oracle/tokenizer.py').read_bytes()),prepare_path=str(prep_path.relative_to(ROOT)),prepare_sha256=sha(prep_path.read_bytes()),thinking=False,system_message=None,suite_render_replay_passed=True,prompts=prompts)
 temp=INPUTS/'prompts.json.tmp';temp.write_text(json.dumps(manifest,indent=2)+'\n');assert json.loads(temp.read_text())==manifest;temp.replace(INPUTS/'prompts.json')
 print(json.dumps(prompts,indent=2))
if __name__=='__main__':main()
