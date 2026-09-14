"""Research-only worker RPCs for matched metadata tests on one idle server.

Launch only on a localhost research endpoint. Full target computation and MTP
policy remain unchanged. CPU/source gates and native differential tests precede
candidate inference. Never install into an already running production worker.
"""
from __future__ import annotations
import ast
import copy
import hashlib
import inspect
from pathlib import Path

EXPECTED_CANDIDATE_AST = '30d6d181060d10f9132c4cbe4163d97931b5a7a177ad6f63d7145b8fce8b17c0'
EXPECTED_SOURCE = '95b0a3c079cb63f04a1a0b78b290c7496c63cc5ebc4dc567962de335ea894b9a'
_STATE = None


def candidate_function(module, original):
    source = Path(module.__file__).read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED_SOURCE:
        raise RuntimeError('Metadata source differs from reviewed refreshed control')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GDNAttentionMetadataBuilder')
    fn = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'build'))
    assignments = [n for n in ast.walk(fn) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'query_lens' for t in n.targets)]
    if len(assignments) != 1 or original.__code__.co_freevars:
        raise RuntimeError('Unexpected metadata assignment or closure')
    assignment = assignments[0]
    expected = ast.parse('query_lens = query_start_loc[1:] - query_start_loc[:-1]').body[0]
    if ast.dump(assignment, include_attributes=False) != ast.dump(expected, include_attributes=False):
        raise RuntimeError('Query-length expression changed')
    containers = [n for n in ast.walk(fn) if isinstance(n, ast.If) and assignment in n.orelse]
    if len(containers) != 1:
        raise RuntimeError('Spec branch not uniquely identified')
    outer = containers[0]
    # All reads must occur in one nested mixed-case else branch, as in the
    # independently reviewed two-line relocation; never generalize by shape.
    uses = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == 'query_lens' and isinstance(n.ctx, ast.Load)]
    branches = [n for n in ast.walk(outer) if isinstance(n, ast.If) and n is not outer and uses and all(any(u is v for child in n.orelse for v in ast.walk(child)) for u in uses)]
    if len(uses) != 4 or len(branches) != 1:
        raise RuntimeError('Query-length consumers changed')
    mixed = branches[0]
    outer.orelse.remove(assignment)
    mixed.orelse.insert(0, assignment)
    fn.name = '_mtp_candidate_build'
    fn.decorator_list = []
    code = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), fn], type_ignores=[])
    namespace = dict(module.__dict__)
    exec(compile(ast.fix_missing_locations(code), '<reviewed-mtp-query-lens>', 'exec'), namespace)
    return namespace[fn.name], hashlib.sha256(ast.dump(fn, include_attributes=False).encode()).hexdigest()


class MtpTransferWorkerExtension:
    def mtp_transfer_prepare(self):
        global _STATE
        import torch
        from vllm.v1.attention.backends import gdn_attn as module
        spec = self.vllm_config.speculative_config
        if spec is None or spec.method != 'mtp' or spec.num_speculative_tokens != 1:
            raise RuntimeError('Only the reviewed native MTP1 configuration is admitted')
        draft_config = spec.draft_model_config
        hf = draft_config.hf_config
        if (hf.model_type != 'qwen3_5_mtp' or hf.architectures != ['Qwen3_5MTP']
                or draft_config.model != self.vllm_config.model_config.model):
            raise RuntimeError('Draft must be this target checkpoint native Qwen MTP head')
        if _STATE is not None:
            raise RuntimeError('Research dispatch is already installed')
        torch.xpu.synchronize()
        original = module.GDNAttentionMetadataBuilder.build
        candidate, candidate_ast_sha256 = candidate_function(module, original)
        if candidate_ast_sha256 != EXPECTED_CANDIDATE_AST:
            raise RuntimeError('Generated candidate differs from independently validated patch')
        state = {'control': original, 'candidate': candidate, 'mode': 'control',
                 'calls': {'control': 0, 'candidate': 0}, 'candidate_ast_sha256': candidate_ast_sha256,
                 'native_gate_passed': False}
        def paired_build(builder, *args, **kwargs):
            mode = state['mode']
            state['calls'][mode] += 1
            return state[mode](builder, *args, **kwargs)
        state['wrapper'] = paired_build
        module.GDNAttentionMetadataBuilder.build = paired_build
        _STATE = state
        return self.mtp_transfer_status()

    def mtp_transfer_status(self):
        from vllm.v1.attention.backends import gdn_attn as module
        state = _STATE
        return {'rank': int(self.rank), 'installed': state is not None,
                'source_sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                'mode': state['mode'] if state else 'unwrapped-control',
                'calls': dict(state['calls']) if state else {},
                'native_gate_passed': state['native_gate_passed'] if state else False,
                'wrapper_active': state is not None and module.GDNAttentionMetadataBuilder.build is state['wrapper'],
                'candidate_ast_sha256': state['candidate_ast_sha256'] if state else None}

    def mtp_transfer_native_gate(self):
        import torch
        from mtp_native_metadata_gate import run_native_metadata_gate
        if _STATE is None or _STATE['mode'] != 'control':
            raise RuntimeError('Native differential gate requires prepared control mode')
        if not self.mtp_transfer_status()['wrapper_active']:
            raise RuntimeError('Research wrapper identity changed')
        torch.xpu.synchronize(self.device)
        result = run_native_metadata_gate(device=self.device, original_build=_STATE['control'], candidate_build=_STATE['candidate'])
        torch.xpu.synchronize()
        if result.get('passed') is not True:
            raise RuntimeError('Native metadata comparison failed')
        _STATE['native_gate_passed'] = True
        return {'rank': int(self.rank), 'result': result, 'status': self.mtp_transfer_status()}

    def mtp_transfer_set_mode(self, mode):
        import torch
        if _STATE is None or mode not in ('control', 'candidate'):
            raise RuntimeError('Invalid research dispatch transition')
        if mode == 'candidate' and not _STATE['native_gate_passed']:
            raise RuntimeError('Native metadata gate has not passed')
        if not self.mtp_transfer_status()['wrapper_active']:
            raise RuntimeError('Research wrapper identity changed')
        torch.xpu.synchronize(self.device)
        _STATE['mode'] = mode
        return self.mtp_transfer_status()
