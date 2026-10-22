"""One-time private copy of packet180's one-card profile; binary and evidence NOT inherited.

packet181 recompiles only the entry TU (main.cpp + checkpoint.hpp v3, adapt_native.py) and
relinks packet165's byte-identical kernel objects exactly as packet179/packet180 did
(build_checkpoint.py). Copied here: packet180's tracked one-card harness, inputs, lineage
(minus its window-20261022 history) and native-source mirror (rewritten from packet165 by the
build). Not copied: evidence/, build/, seal.json, READY files.

Also copies, byte-identical, the packet180 device receipts that this packet's analyzers are
tested against (row a full512, row b lifecycle) into one-card/lineage/packet180-receipts/
(COPY-MANIFEST.json records source, bytes, sha256). The small checkpoint files of packet180's
real S1/S2 (tokens.bin and the control blobs) are local untracked device output; they are
copied too so the manifest-semantics replay runs on real bytes. Every pin this packet writes
therefore stays inside the packet.
"""
import hashlib,json,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
OLD=P.parent/'packet180-session-swap-v2'
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
    if leaf.parts[:2]==('lineage','window-20261022'):continue
    if f.name in ('seal.json','READY-FOR-DEVICE.json','READY.json'):continue
    dest=new/leaf;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    copied[str(leaf)]=sha(f)
save(new/'evidence/copy-baseline.json',dict(passed=True,parent='experiments/own-xpu-runtime/stage2/'+OLD_NAME+'/one-card',
    files=copied,parent_binary_sha256=sha(old/'build/device/own-rt-iq3'),binary_copied=False,device_executed=False,
    excluded=['evidence/','build/','lineage/window-20261022/','seal.json','READY-FOR-DEVICE.json']))
for leaf in ('build.json','identity-check.json','preparation-probe.json'):
    shutil.copy2(old/'evidence'/leaf,new/'evidence'/('parent-'+leaf))
for f in new.glob('*.py'):
    f.write_text(f.read_text().replace(OLD_NAME,NEW_NAME))
for f in (new/'inputs').rglob('input.json'):
    f.write_text(f.read_text().replace(OLD_NAME,NEW_NAME))

# packet180 real device receipts (row a full512, row b lifecycle), 2026-10-22 window lanequeue-A35.
RA=old/'evidence/device-p180-full512-A-a';RB=old/'evidence/device-p180-lifecycle-A-b'
dest=new/'lineage/packet180-receipts'
wanted=[(RA,'row-a',l) for l in ('summary.json','bracket-summary.json','identity.json','window.json',
                                 'run/report-inputs.json','run/teardown.json','run/p179-identity.json','run/native/receipt.json')]
ids=sorted(p.name for p in (RA/'run/native').iterdir() if (p/'result.json').is_file())
assert len(ids)==13,ids
for i in ids:
    for l in ('result.json','receipt.json','reset.json'):wanted.append((RA,'row-a','run/native/'+i+'/'+l))
for l in ('timings.jsonl','prefill-timings.jsonl'):
    for i in ('incident-retrospective','prefill512'):wanted.append((RA,'row-a','run/native/'+i+'/'+l))
wanted+=[(RB,'row-b',l) for l in ('summary.json','bracket-summary.json','identity.json','window.json','run/lifecycle-receipt.json',
                                 'run/teardown.json','run/inputs/new.txt','run/inputs/new.json',
                                 'run/s2b-manifest-copy/manifest.json','run/s2b-manifest-copy/fields.tsv')]
legs=('save-s1','append-s2','resume-s2','reference','append-s2b')
for leg in legs:
    for l in ('result.json','reset.json','receipt.json','timings.jsonl','prefill-timings.jsonl','cold-start.json','stream-proof.json','lookup-request-complete.json'):
        wanted.append((RB,'row-b','run/run/'+leg+'/native/'+l))
    wanted.append((RB,'row-b','run/run/'+leg+'/launch.json'))
for cid in ('s1','s2'):
    for l in ('manifest.json','fields.tsv','tokens.bin','position.bin','next_token.bin','token.bin','error.bin','token_history.bin','active.bin'):
        wanted.append((RB,'row-b','run/checkpoints/'+cid+'/'+l))
tools=sorted(p.name for p in (RB/'run/tools').iterdir())
assert len(tools)==12,tools
for t in tools:wanted.append((RB,'row-b','run/tools/'+t))
rows=[]
for base,label,leaf in wanted:
    src=base/leaf;out=dest/label/leaf;out.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,out);assert sha(src)==sha(out)
    rows.append(dict(source_relative=str(src.relative_to(ROOT)),copy_relative=str(out.relative_to(new)),bytes=src.stat().st_size,sha256=sha(out)))
save(dest/'COPY-MANIFEST.json',dict(schema='packet181.packet180-receipt-copy.v1',
    source_commit_note='packet180 device receipts at 35cbcc648 (2026-10-22 06:44-07:23 UTC window, lanequeue-A35); checkpoint tokens.bin and control blobs are local untracked device output (*.bin)',
    entries=rows,scope='byte-identical copies; read by this packet\'s analyzer replays (packet180 analyzers and the packet181 analyzer on packet180 real receipts)'))
print('Copied packet180 one-card profile without binary/evidence; READY absent;',len(copied),'files;',len(rows),'packet180 receipts copied')
