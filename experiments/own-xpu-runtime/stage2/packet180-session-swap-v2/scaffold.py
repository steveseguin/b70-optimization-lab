"""One-time private copy of packet179's one-card profile; binary and evidence NOT inherited.

packet180 recompiles only the entry TU (main.cpp + checkpoint.hpp v2, adapt_native.py)
and relinks packet165's byte-identical kernel objects exactly as packet179 did
(build_checkpoint.py). Copied here: packet179's tracked one-card harness, inputs,
lineage (minus its pinfix history) and native-source mirror (rewritten from packet165
by the build). Not copied: evidence/, build/, seal.json, READY files.

Also copies, byte-identical, the packet179 device receipts that this packet's
analyzers are tested against and that row a/row b compare to, into
one-card/lineage/packet179-receipts/ (COPY-MANIFEST.json records source, bytes,
sha256). Every pin this packet writes therefore stays inside the packet.
"""
import hashlib,json,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
OLD=P.parent/'packet179-session-swap'
OLD_NAME,NEW_NAME=OLD.name,P.name
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2)+'\n')
old=OLD/'one-card';new=P/'one-card'
assert not new.exists(),'one-time scaffold refuses overwrite'
files=subprocess.check_output(['git','ls-files',str(old.relative_to(ROOT))],cwd=ROOT,text=True).splitlines()
copied={}
for rel in files:
    f=ROOT/rel;leaf=f.relative_to(old)
    if leaf.parts[0] in ('evidence','build') or '__pycache__' in leaf.parts:continue
    if leaf.parts[:2]==('lineage','pinfix-20261021'):continue
    if f.name in ('seal.json','READY-FOR-DEVICE.json','READY.json'):continue
    dest=new/leaf;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    copied[str(leaf)]=sha(f)
save(new/'evidence/copy-baseline.json',dict(passed=True,parent='experiments/own-xpu-runtime/stage2/'+OLD_NAME+'/one-card',
    files=copied,parent_binary_sha256=sha(old/'build/device/own-rt-iq3'),binary_copied=False,device_executed=False,
    excluded=['evidence/','build/','lineage/pinfix-20261021/','seal.json','READY-FOR-DEVICE.json']))
for leaf in ('build.json','identity-check.json','preparation-probe.json'):
    shutil.copy2(old/'evidence'/leaf,new/'evidence'/('parent-'+leaf))
for f in new.glob('*.py'):
    f.write_text(f.read_text().replace(OLD_NAME,NEW_NAME))
for f in (new/'inputs').rglob('input.json'):
    f.write_text(f.read_text().replace(OLD_NAME,NEW_NAME))

# packet179 real device receipts (row a full512 reference, row b checkpoint gate).
RA=old/'evidence/device-p179-full512-A-a';RB=old/'evidence/device-p179-checkpoint-A-b'
dest=new/'lineage/packet179-receipts'
wanted=[(RA,'row-a',l) for l in ('summary.json','identity.json','window.json','run/report-inputs.json','run/teardown.json')]
ids=sorted(p.name for p in (RA/'run/native').iterdir() if (p/'result.json').is_file())
assert len(ids)==13,ids
for i in ids:
    for l in ('result.json','receipt.json','reset.json'):wanted.append((RA,'row-a','run/native/'+i+'/'+l))
for l in ('timings.jsonl','prefill-timings.jsonl'):wanted.append((RA,'row-a','run/native/incident-retrospective/'+l))
wanted+=[(RB,'row-b',l) for l in ('summary.json','identity.json','window.json','run/checkpoint-receipt.json','run/teardown.json')]
for leg in ('save','restore1','restore2'):
    for l in ('result.json','reset.json','receipt.json','timings.jsonl','prefill-timings.jsonl','cold-start.json'):
        wanted.append((RB,'row-b','run/run/'+leg+'/native/'+l))
for l in ('manifest.json','fields.tsv','tokens.bin','token_history.bin','position.bin','next_token.bin','token.bin','active.bin','error.bin'):
    wanted.append((RB,'row-b','run/checkpoints/gate/'+l))
rows=[]
for base,label,leaf in wanted:
    src=base/leaf;out=dest/label/leaf;out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,out);assert sha(src)==sha(out)
    rows.append(dict(source_relative=str(src.relative_to(ROOT)),copy_relative=str(out.relative_to(new)),bytes=src.stat().st_size,sha256=sha(out)))
save(dest/'COPY-MANIFEST.json',dict(schema='packet180.packet179-receipt-copy.v1',
    source_commit_note='packet179 device receipts at 8bf76113f (2026-10-22 window, lanequeue-A34)',
    entries=rows,scope='byte-identical copies; read by this packet\'s analyzer tests and by the row-a/row-b packet179 identity comparisons'))
print('Copied packet179 one-card profile without binary/evidence; READY absent;',len(rows),'packet179 receipts copied')
