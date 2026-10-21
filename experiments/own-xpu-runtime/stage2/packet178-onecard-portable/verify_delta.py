"""Prove copied immutable inputs/arithmetic and enumerate only harness deltas."""
import difflib,json
from pathlib import Path
from build_engine import P,ROOT,sha,save
OLD=P.parent/'packet165-warm-prefill'
allowed={'identity.json','inherited-native.json','runtime-constants.json'}
for name in ('one-card',):
    p=P/name;old=OLD/name
    pins=json.loads((p/'evidence/copy-baseline.json').read_text())['files']
    changed=[];patches=[]
    for leaf,expected in pins.items():
        a=old/leaf;b=p/leaf
        assert sha(a)==expected,('frozen parent changed',leaf)
        if sha(b)==expected:continue
        aa=a.read_bytes();bb=b.read_bytes()
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
        patches.extend(difflib.unified_diff(aa.decode().splitlines(True),bb.decode().splitlines(True),fromfile='packet165/'+leaf,tofile='packet178/'+leaf))
    for leaf in ('selection.json','dispatch.json','budget.json','inputs/plan.tsv'):
        assert sha(p/leaf)==sha(old/leaf)
    for f in (p/'inputs').rglob('tokens.txt'):
        assert sha(f)==sha(old/f.relative_to(p))
    (p/'harness-delta.patch').write_text(''.join(patches))
    save(p/'evidence/delta-check.json',dict(passed=True,device_executed=False,
        copied_parent_files_checked=len(pins),frozen_parent_unchanged=True,
        semantic_harness_changes=changed,native_semantic_changes=[],
        native_path_relocation_only=True,all_prompt_tokens_unchanged=True,
        selection_dispatch_budgets_unchanged=True,harness_patch_sha256=sha(p/'harness-delta.patch'),
        binary_not_inherited='portable rebuild; see evidence/build.json'))
    print(name,'copy/delta PASS',changed)
