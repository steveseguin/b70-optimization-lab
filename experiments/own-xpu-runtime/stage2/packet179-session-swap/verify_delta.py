"""Prove copied immutable inputs/arithmetic and enumerate only harness deltas."""
import difflib,json
from pathlib import Path
from build_engine import P,ROOT,sha,save
OLD=P.parent/'packet165-warm-prefill'
NAT='native-source/repo/experiments/own-xpu-runtime/stage2/packet58aj-onecard-resident/build/native'
allowed={'identity.json','inherited-native.json','runtime-constants.json','worker.py','measurement.py','screen.py','entry.py','budget.json','native-help-flags.json'}
new_files={NAT+'/checkpoint.hpp'}
packet_new_files=['scaffold.py','adapt_native.py','build_checkpoint.py','checkpoint_probe.py','test_checkpoint.py']
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
            # The single native semantic delta, recorded in lineage/packet179-native-delta.patch.
            import hashlib
            assert hashlib.sha256(bb.replace(str(P).encode(),str(OLD).encode())).hexdigest()==delta['patched_main_sha256'],leaf
            patches.extend(difflib.unified_diff(aa.decode().splitlines(True),bb.replace(str(P).encode(),str(OLD).encode()).decode().splitlines(True),fromfile='packet165/'+leaf,tofile='packet179/'+leaf))
            changed.append(leaf)
            continue
        if leaf.startswith('native-source/'):
            assert bb.replace(str(P).encode(),str(OLD).encode())==aa,leaf
            continue
        if leaf.startswith('inputs/') and leaf.endswith('/input.json'):
            assert bb.replace(str(P).encode(),str(OLD).encode())==aa,leaf
            continue
        # Relocated self-contained Python dependency paths are also mechanical.
        if leaf.endswith('.py') and bb.replace(str(P.name).encode(),str(OLD.name).encode())==aa:continue
        assert leaf in allowed,('unexpected copied-file change',name,leaf)
        changed.append(leaf)
        patches.extend(difflib.unified_diff(aa.decode().splitlines(True),bb.decode().splitlines(True),fromfile='packet165/'+leaf,tofile='packet179/'+leaf))
    for leaf in new_files:
        f=p/leaf;assert f.is_file(),leaf;changed.append(leaf+' (new)')
    for leaf in ('selection.json','dispatch.json','inputs/plan.tsv'):
        assert sha(p/leaf)==sha(old/leaf)
    for f in (p/'inputs').rglob('tokens.txt'):
        assert sha(f)==sha(old/f.relative_to(p))
    for leaf in packet_new_files:
        assert (P/leaf).is_file(),leaf
    (p/'harness-delta.patch').write_text(''.join(patches))
    save(p/'evidence/delta-check.json',dict(passed=True,device_executed=False,
        copied_parent_files_checked=len(pins),frozen_parent_unchanged=True,
        semantic_harness_changes=changed,native_semantic_changes=[NAT+'/main.cpp'],
        native_new_files=sorted(new_files),packet_new_files=packet_new_files,
        native_path_relocation_only=False,native_delta_patch='lineage/packet179-native-delta.patch',
        all_prompt_tokens_unchanged=True,
        selection_dispatch_unchanged=True,budget_floors_unchanged=True,
        harness_patch_sha256=sha(p/'harness-delta.patch'),
        binary_not_inherited='entry TU recompiled; kernel objects relinked byte-identical; see evidence/build.json'))
    print(name,'copy/delta PASS',changed)
