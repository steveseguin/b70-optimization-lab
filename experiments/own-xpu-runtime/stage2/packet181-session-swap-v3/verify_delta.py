"""Prove copied immutable inputs/arithmetic against packet180 and enumerate only the intended deltas.

Also proves packet180's analyzers are kept byte-for-byte: packet180's measurement.py is an exact
prefix of this packet's (the v3 analyzer is appended), so the replays in test_p180_receipts.py run
packet180's own code.
"""
import difflib,hashlib,json
from pathlib import Path
from build_engine import P,ROOT,sha,save
OLD=P.parent/'packet180-session-swap-v2'
NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
allowed={'identity.json','inherited-native.json','worker.py','measurement.py','screen.py','entry.py','budget.json','harness-delta.patch'}
packet_new_files=['scaffold.py','adapt_native.py','checkpoint.hpp','build_checkpoint.py','checkpoint_probe.py','test_lifecycle.py','test_p180_receipts.py']
new_profile_files=['lineage/packet181-native-delta.patch','lineage/packet181-vs-packet180-main.patch','lineage/packet181-vs-packet180-checkpoint.patch',
                   'lineage/packet181-build.json','lineage/packet180-receipts/COPY-MANIFEST.json']
unchanged=['selection.json','dispatch.json','inputs/plan.tsv','inputs/identity.tsv','parent-native-argv.json','oracle-binding.json',
           'lifecycle.json','reference-p179-row-a.json','tokenizer-identity.tsv','native-help-flags.json']
for name in ('one-card',):
    p=P/name;old=OLD/name
    pins=json.loads((p/'evidence/copy-baseline.json').read_text())['files']
    delta=json.loads((p/'evidence/native-delta.json').read_text())
    changed=[];patches=[]
    for leaf,expected in pins.items():
        a=old/leaf;b=p/leaf
        assert sha(a)==expected,('frozen parent changed',leaf)
        if sha(b)==expected:continue
        aa=a.read_bytes();bb=b.read_bytes()
        if leaf==NAT+'/main.cpp':
            normalized=bb.replace(str(P).encode(),str(P.parent/'packet165-warm-prefill').encode())
            assert hashlib.sha256(normalized).hexdigest()==delta['patched_main_sha256'],leaf
            changed.append(leaf);continue
        if leaf==NAT+'/checkpoint.hpp':
            assert sha(b)==delta['checkpoint_hpp_sha256'],leaf
            changed.append(leaf);continue
        if leaf.startswith('native-source/') or (leaf.startswith('inputs/') and leaf.endswith('/input.json')):
            assert bb.replace(str(P).encode(),str(OLD).encode())==aa,leaf
            continue
        if leaf.endswith('.py') and bb.replace(P.name.encode(),OLD.name.encode())==aa:continue
        assert leaf in allowed,('unexpected copied-file change',name,leaf)
        changed.append(leaf)
        if leaf!='harness-delta.patch':
            patches.extend(difflib.unified_diff(aa.decode().splitlines(True),bb.decode().splitlines(True),fromfile='packet180/'+leaf,tofile='packet181/'+leaf))
    for leaf in new_profile_files:assert (p/leaf).is_file(),leaf
    for leaf in unchanged:assert sha(p/leaf)==sha(old/leaf),leaf
    for f in (p/'inputs').rglob('tokens.txt'):
        assert sha(f)==sha(old/f.relative_to(p))
    for leaf in packet_new_files:assert (P/leaf).is_file(),leaf
    parent_measurement=(old/'measurement.py').read_text().replace(OLD.name,P.name)
    current=(p/'measurement.py').read_text()
    assert current.startswith(parent_measurement) and len(current)>len(parent_measurement),'packet180 analyzers must be an exact prefix of measurement.py'
    (p/'harness-delta.patch').write_text(''.join(patches))
    save(p/'evidence/delta-check.json',dict(passed=True,device_executed=False,
        parent='packet180-session-swap-v2/one-card',copied_parent_files_checked=len(pins),frozen_parent_unchanged=True,
        semantic_harness_changes=sorted(set(changed)-{NAT+'/main.cpp',NAT+'/checkpoint.hpp'}),
        native_semantic_changes=[NAT+'/main.cpp',NAT+'/checkpoint.hpp'],
        new_profile_files=new_profile_files,packet_new_files=packet_new_files,unchanged_profile_files=unchanged,
        native_delta_patches=['lineage/packet181-native-delta.patch (vs packet165)','lineage/packet181-vs-packet180-main.patch','lineage/packet181-vs-packet180-checkpoint.patch'],
        packet180_analyzers_exact_prefix_of_measurement=True,
        all_prompt_tokens_unchanged=True,selection_dispatch_plan_identity_unchanged=True,cli_flags_unchanged=True,
        budget_floors_unchanged=json.loads((p/'budget.json').read_text())['device_floor_bytes']==25_000_000_000,
        harness_patch_sha256=sha(p/'harness-delta.patch'),
        binary_not_inherited='entry TU recompiled; kernel objects relinked byte-identical from packet165; see evidence/build.json'))
    print(name,'copy/delta PASS',sorted(set(changed)))
