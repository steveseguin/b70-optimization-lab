#!/usr/bin/env python3
"""List exact file deltas against the copied packet38 baseline."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
base=json.loads((P/'baseline.json').read_text())
rows=[]
for name,old in sorted(base['files'].items()):
 f=P/name;new=hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
 if new!=old:rows.append(dict(path=name,base_sha256=old,packet44_sha256=new))
added=sorted(({str(f.relative_to(P)) for f in P.rglob('*') if f.is_file() and P/'build' not in f.parents and '__pycache__' not in f.parts}|{'INTEGRATE.md','integration-delta.json'})-set(base['files']))
(P/'integration-delta.json').write_text(json.dumps(dict(base_commit=base['commit'],changed_files=rows,added_files=added),indent=2)+'\n')
text="""# Integrating packet44 with packet40

The table below is the complete changed-file list against the copy recorded in
baseline.json. integration-delta.json carries both hashes. New packet44 review,
gate and documentation files are local additions, not edits to packet38.

Keep packet40 fixture retention, cancellation and nonblocking draft work. Merge
packet44's launch extent into Engine and draft state: refresh only QSA selection
and attention, swap extent with the alternate bank, and admit each position
before issuing work. Preserve packet40 cancellation checks while refreshing.
Keep its reset/terminal-state semantics and add both extent fields to the state
inventory. Capacity does not authorize prompt/KV reuse across requests.

Adapter Shape/Spec gains extent. Zero means capacity for legacy callers. New
launch sites pass the rounded valid bound only for selection and attention.
Do not change valid-position reduction leaves, pooling groups or tie order.
The full RoPE table preserves every old byte. Reconcile packet40 draft fixture
retention with packet44's valid-prefix row dumps; final state remains complete.

Merge wrapper safety fixes once, preserving unchanged LD_LIBRARY_PATH and
structured owner-failure evidence. Suite token caps (32/64/128) come from their manifest;
context is separately checked against it. Regenerate all merged receipts and
rerun CPU qualification. Neither packet's receipts qualify a different merged
binary. Device windows are pending and must be rerun after integration.

| Changed copied file | Base SHA-256 | Packet44 SHA-256 |
| --- | --- | --- |
"""
for r in rows:text+='| '+r['path']+' | '+r['base_sha256']+' | '+str(r['packet44_sha256'])+' |\n'
text+='\nThe complete new-file list (including every evidence artifact) is the `added_files` array in [integration-delta.json](integration-delta.json). New source/helpers are:\n\n'
for name in added:
 if Path(name).suffix in ('.cpp','.hpp','.py'):text+='- `'+name+'`\n'
(P/'INTEGRATE.md').write_text(text)
print(len(rows),'changed copied files')
