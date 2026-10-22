"""Sealed draft-only KD projection; target storage never executes in capture.

The resident target rank exceeds the 8 GiB CPU limit. Keep the existing bounded
streaming capture and its unchanged draft arithmetic instead. Only target-only
storage/retirement choices are projected; all draft, route and dispatch choices
remain byte-identical. This does not qualify target outputs (W2m/WS do that).
"""
import copy
import json
from pathlib import Path
from build_engine import sha, save

TARGET_ONLY = {'other_fusion':'production', 'experts': 'wide64', 'head': 'production',
               'hc_norm': 'production', 'host_retire': 'ordered'}

def project(target):
    from bundle_selection import views, selection
    assert any(target == selection(v) for v in views().values()), 'unsealed KD composition'
    result = copy.deepcopy(target)
    result['choices'].update(TARGET_ONLY)
    assert result['draft'] == target['draft']
    assert all(result['choices'][k] == v for k, v in target['choices'].items() if k not in TARGET_ONLY)
    return result

def prepare(target_path, target_sha, out):
    assert sha(target_path) == target_sha, 'KD target selection changed'
    target = json.loads(Path(target_path).read_text())
    path = Path(out)/'draft-reference-selection.json'
    save(path, project(target))
    binding = dict(schema='packet103.kd-draft-projection.v1', passed=True, selection_sha256=target_sha, target_selection_sha256=target_sha,
                   reference_selection_sha256=sha(path), target_only=TARGET_ONLY,
                   draft=target['draft'], target_executed=False,
                   reason='Draft-only capture; resident target exceeds 8 GiB host bound')
    save(Path(out)/'draft-reference-binding.json', binding)
    return path, binding

def command(binary, a, table, inp, dest, selection_path, selection_sha, stop_fd, *, device=False):
    return [str(binary), *(['--authorized-device-window'] if device else []),
            '--card', str(a.card+getattr(a,'draft_rank',1)), '--rank','1',
            '--draft-rank','1','--target-split','0','--memory','layer-streaming',
            '--stop-fd',str(stop_fd),'--draft-capture',str(table),'--context',str(a.context),
            '--plan',str(a.input/'plan.tsv'),'--identity',str(a.input/'identity.tsv'),
            '--model-dir',inp['model_dir'],'--output',str(dest),'--dispatch',str(a.dispatch),
            '--selection',str(selection_path),'--selection-sha256',selection_sha,'--seconds','10800']

def check_owner(root, binding):
    root = Path(root)
    receipt = json.loads((root/'receipt.json').read_text())
    assert receipt['selection_sha256'] == binding['reference_selection_sha256'], 'KD reference selection differs'
    choices = json.loads((root/'draft-kernel-choices.json').read_text())
    assert choices['selection_sha256'] == binding['reference_selection_sha256']
    assert choices['choices'] == binding['draft'], 'KD draft kernels changed'
    assert choices['target_mutable_aliases'] == 0
    proof=dict(passed=True,selection_sha256=binding['target_selection_sha256'],
               reference_selection_sha256=binding['reference_selection_sha256'],draft_kernel_choices=choices)
    save(root/'draft-reference-identity.json',proof)
    return proof
