"""Capture immutable metadata identities only; no model/table payload reads."""
import json,re,shutil,sys
from pathlib import Path
from copy_bundle import ROOT,S,P,O,sha,save
registration={}
for dimension,variant in [('attention_layout','attention-order600'),('expert_gate_up_layout','expert-gate-up-order600'),('hc_layout','hc-gate-low-order600'),('token_input','both')]:
 parent=S/('packet137-token-input' if dimension=='token_input' else 'packet142-class-layout');v5=parent/'v5'
 line=v5/'lineage' if dimension=='token_input' else v5/'lineage'/variant
 dest=P/'lineage-inputs/components'/dimension;dest.mkdir(parents=True,exist_ok=True)
 for leaf in ('selection.json','candidate.json','memory-plan.json','dispatch-speed6.json'):
  if (line/leaf).exists():shutil.copy2(line/leaf,dest/leaf)
 registration[dimension]=dict(variant=variant,binary_sha256=sha(v5/'build/device/own-rt-iq3'),control_selection_sha256=sha(line/'selection.json'),candidate_selection_sha256=sha(line/'candidate.json'),evidence_directory=str(v5/'evidence'/('device-v5-B' if dimension=='token_input' else 'device-'+variant+'-v5-B')),source_commit='d4312dbce' if dimension=='token_input' else '65589e393',source_lineage=str(line))
 # Read-side source snapshot: provenance, not imports from the mutable packet.
 report=v5/('packet137_report.py' if dimension=='token_input' else 'compare.py');shutil.copy2(report,dest/'original-report.py')
save(P/'lineage-inputs/component-registration.json',registration)
shutil.copy2(S/'packet136-record-bundle/selection.json',P/'lineage-inputs/bundle8-selection.json')
shutil.copy2(S/'packet136-record-bundle/memory-plan.json',P/'lineage-inputs/bundle8-memory-plan.json')
# Pinned ledger snapshot and its exact record row, checked again at submission.
ledger=ROOT/'results/localmaxxing-submissions.md';text=ledger.read_text();matches=[line for line in text.splitlines() if 'cmve4dtir007wrf01k57sdf23' in line]
assert matches,'record ID missing from ledger'
shutil.copy2(ledger,P/'lineage-inputs/localmaxxing-submissions.md')
save(P/'record-baseline.json',dict(record_id='cmve4dtir007wrf01k57sdf23',record_tok_s=58.798109,ledger=str((P/'lineage-inputs/localmaxxing-submissions.md').relative_to(ROOT)),ledger_sha256=sha(P/'lineage-inputs/localmaxxing-submissions.md'),matched_lines=matches,prepared_commit=__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip()))
print('Four component registrations and record ledger pinned')
