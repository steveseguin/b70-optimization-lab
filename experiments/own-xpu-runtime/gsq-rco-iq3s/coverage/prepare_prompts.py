#!/usr/bin/env python3
"""Preregister fixed prompts using local tokenizer metadata only; never inference."""
from pathlib import Path
import hashlib,json,os,resource,sys
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
sys.path.insert(0,str(P));import tokenizer as T
sha=T.sha

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 tok,render,authority=T.load();baseline=json.loads((L/'baseline/manifest.json').read_text());b=baseline['prompts'][0]
 original=R/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/prompts/incident-retrospective.txt';chat=original.read_text()
 assert tok.encode(chat,add_special_tokens=False).ids==b['tokens']
 user=chat.split('<|im_start|>user\n',1)[1].split('<|im_end|>',1)[0];assert render(user)==chat
 old=R/'experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/inputs/prefill512';raw=(old/'source.txt').read_text();oldids=list(map(int,(old/'tokens.txt').read_text().split()));oldmeta=json.loads((old/'input.json').read_text())
 assert oldmeta['add_special_tokens'] is False and hashlib.sha256(raw.encode()).hexdigest()==oldmeta['source_text_sha256']
 assert tok.encode(raw,add_special_tokens=False).ids[:512]==oldids==oldmeta['tokens'] and len(oldids)==512
 first='EARLY RECORD: The North Quay observatory sealed the amber ledger on 17 April 2031. Its authorized custodian was Mira Solano.'
 middle='MIDDLE RECORD: The shipment assigned to route Cobalt carried exactly 73 ceramic sensors. It was placed in vault H7, not the neighboring vault H8.'
 last='LATE RECORD: The final inspection required the signal phrase silver heron. Release was authorized only after both the pressure check and the checksum check passed.'
 records=[]
 for i in range(1,37):
  records.append(f'Register entry {i:02d}: station {chr(65+(i%26))}{i:02d} logged {100+i} calibration samples during its scheduled survey. The clerk recorded the local weather, checked the sealed equipment case, and forwarded a routine receipt to the archive desk. This entry grants no release authority.')
 doc='\n\n'.join([first,*records[:18],middle,*records[18:],last])
 question='Read the document below. Return only one JSON object with keys custodian, sealed_date, sensor_count, vault, signal_phrase, release_checks. Copy the relevant facts exactly; sensor_count must be an integer and release_checks a two-item array. Ignore unrelated register entries.\n\nDOCUMENT\n'+doc+'\n\nReturn the requested JSON object now.'
 rendered=render(question);ids=tok.encode(rendered,add_special_tokens=False).ids
 assert 1800<=len(ids)<=2300,(len(ids),'roughly2048 case')
 facts={'custodian':'Mira Solano','sealed_date':'17 April 2031','sensor_count':73,'vault':'H7','signal_phrase':'silver heron','release_checks':['pressure check','checksum check']}
 cases=[dict(id='prompt00-extended',tokens=b['tokens'],input_tokens=87,max_new=512,order=['none','mtp'],input_mode='unchanged chat template, thinking disabled',prefix_oracle_tokens=128,rubric={'kind':'manual','criteria':['incident impact and timeline','contributing cache invalidation cause','detection gaps','remediation and prevention','owner handoff','coherent complete output; report truncation/EOS and omissions'],'requested_word_range':[450,550]}),dict(id='historical-reading512',tokens=oldids,input_tokens=512,max_new=512,order=['mtp','none'],input_mode='raw first512 IDs, no chat template or special tokens added; historical continuation',prefix_oracle_tokens=0,rubric={'kind':'manual','criteria':['continuation coherence with document prefix','readability and obvious contradictions','report truncation/EOS; not a question-answer task']}),dict(id='document-facts',tokens=ids,input_tokens=len(ids),max_new=128,order=['none','mtp'],input_mode='target GGUF chat template, thinking disabled',prefix_oracle_tokens=0,rubric={'kind':'exact_json_facts','expected':facts,'positions':{label:len(tok.encode(rendered[:rendered.index(text)],add_special_tokens=False).ids) for label,text in [('early',first),('middle',middle),('late',last)]},'criteria':['all six fact fields correct','no unsupported added facts','valid JSON with only requested keys']})]
 for c in cases:assert c['input_tokens']==len(c['tokens']) and len(c['tokens'])+c['max_new']<=4096
 texts={'prompt00-extended.txt':chat,'historical-reading512.txt':tok.decode(oldids,skip_special_tokens=False),'document-facts.txt':rendered,'document-source.txt':doc}
 for name,text in texts.items():
  with (P/'prompts'/name).open('x') as f:f.write(text)
 inputs=[original,old/'source.txt',old/'tokens.txt',old/'input.json',L/'baseline/manifest.json',L/'metadata/new-census.json',Path(__file__),P/'tokenizer.py',T.TOKENIZER]
 manifest=dict(schema='gsq.coverage.six-request.v1',cases=cases,requests=6,pairs=3,retained_state_dumps=7,context=4096,binary_sha256='97348925367e1ad67313cf9863d0c4cba47abea871c386972983965e036ea4b2',tokenizer=authority,source_sha256={str(f):sha(f) for f in inputs},prompt_sha256={name:sha(P/'prompts'/name) for name in texts},order_balance={'target_first':2,'mtp_first':1,'exact_balance':False},excluded_warmups=0,scope='Broader same-target equivalence and preregistered task readback; no independent full-model oracle or performance promotion')
 with (P/'manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
 print(json.dumps({'passed':True,'input_tokens':[c['input_tokens'] for c in cases],'facts_positions':cases[2]['rubric']['positions'],'manifest_sha256':sha(P/'manifest.json'),'model_payload_read':False}))
if __name__=='__main__':main()
