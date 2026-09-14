#!/usr/bin/env python3
"""Stdlib-only source contract for the inactive CLIP ownership integration."""
import ast
import hashlib
import json
from pathlib import Path
import sys

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
SOURCE = ROOT / 'prepared-encoder-na-axis-10/source'
PINS = {'comfy/sd.py': '41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0',
        'comfy/model_management.py': 'ef3f3af0657c1b022ad69b25928fa52dd429db9aed9cb688e89c7fbe68ab50cd',
        'comfy/model_patcher.py': '768d9b6f24b632dffba9e4c3c2d2962b3c309bf33182cf599d8c9abda2125d99'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def methods(path, name):
    node = next(node for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.ClassDef) and node.name == name)
    return {value.name: value for value in node.body if isinstance(value, ast.FunctionDef)}


for name, digest in PINS.items():
    assert sha(SOURCE / name) == digest, name
adapter = LANE / 'scripts/host_embedding_clip.py'
diagnostic = LANE / 'scripts/host_embedding_placement_node.py'
for path in (adapter, diagnostic):
    compile(path.read_text(), str(path), 'exec')  # Compile source only; never execute/import.
base = methods(SOURCE / 'comfy/sd.py', 'CLIP')['load_model']
updated = methods(adapter, 'HostEmbeddingCLIP')['load_model']
assert [ast.dump(node) for node in base.body[:2]] == [ast.dump(node) for node in updated.body[2:4]], 'Estimator changed'
calls = [node for node in ast.walk(updated) if isinstance(node, ast.Call)
         and ast.unparse(node.func) == 'model_management.load_models_gpu']
assert len(calls) == 1 and len(calls[0].args) == 1
assert [(key.arg, ast.unparse(key.value)) for key in calls[0].keywords] == [('memory_required', 'memory_used')]
assert "options['initial_device'] = torch.device('cpu')" in adapter.read_text()
assert "patchers.append(group.owner.host)" in adapter.read_text()
assert "register_state_dict_pre_hook" in adapter.read_text() and "register_load_state_dict_pre_hook" in adapter.read_text()
assert "self.owner.host.model._modules.pop('embedding')" in adapter.read_text()
assert "return (conditioning,)" in diagnostic.read_text()
cpu_receipt = ROOT / 'host-embedding-cpu-v3-native-01/result.json'
cpu = json.loads(cpu_receipt.read_text())
assert cpu['status'] == 'passed-guarded-cpu-fixture' and cpu['tests_run'] == 6
assert cpu['xpu_initialized'] is False and cpu['cuda_initialized'] is False and cpu['final_guards_intact'] is True
candidate = LANE / 'scripts/ltx_host_embedding_candidate.py'
assert sha(candidate) == cpu['helper_sha256s']['scripts/ltx_host_embedding_candidate.py']
assert 'torch' not in sys.modules
print(json.dumps({'schema': 'ltx.host-embedding-integration-source.v1', 'status': 'passed-stdlib-source-contract',
    'source_sha256s': PINS, 'new_files': {str(path.relative_to(LANE)): sha(path) for path in (adapter, diagnostic, Path(__file__))},
    'candidate_sha256': sha(candidate), 'prior_cpu_receipt_sha256': sha(cpu_receipt),
    'torch_imported': False, 'native_requests': 0,
    'scope': 'Estimator/load-argument/source identity checks only; adapter lifecycle and startup integration not yet natively tested'}, indent=2))
