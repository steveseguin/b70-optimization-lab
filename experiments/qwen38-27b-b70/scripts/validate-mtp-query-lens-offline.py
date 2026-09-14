#!/usr/bin/env python3
"""Differential CPU gate executing actual GDN builders and helper function ASTs.

No vLLM package import, accelerator initialization, weights, or model requests.
CPU transport substitutes only replace accelerator/pinned-memory plumbing;
metadata classification, indexing, padding, state references and chunk arithmetic
execute from supplied source files. This is not native XPU or token qualification.
"""
from __future__ import annotations
import argparse
import ast
import contextlib
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(path, names, namespace, *, strip_decorators=False):
    tree = ast.parse(Path(path).read_text())
    selected = [node for node in tree.body if getattr(node, 'name', None) in names]
    assert {node.name for node in selected} == set(names), (path, names)
    if strip_decorators:
        for node in selected:
            node.decorator_list = []
    code = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + selected, type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), str(path), 'exec'), namespace)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', required=True, type=Path, help='Directory containing v1/ and third_party/')
    p.add_argument('--patch', required=True, type=Path)
    p.add_argument('--proof', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    import numpy as np
    import torch
    from torch.utils._python_dispatch import TorchDispatchMode
    torch.set_num_threads(1)
    assert not torch.xpu.is_initialized()
    assert not torch.cuda.is_initialized()
    accelerator_calls = []
    def deny(*a, **kw):
        accelerator_calls.append(True)
        raise RuntimeError('Offline gate forbids accelerator initialization and device discovery')
    for backend in (torch.xpu, torch.cuda):
        for name in ('init', '_lazy_init', 'device_count', 'is_available', 'current_device', 'set_device'):
            if hasattr(backend, name):
                setattr(backend, name, (lambda label: lambda *a, **kw: deny(label))(f'{backend.__name__}.{name}'))
    root = args.source_root
    paths = {
        'builder': root/'v1/attention/backends/gdn_attn.py',
        'common': root/'v1/attention/backend.py',
        'helpers': root/'v1/attention/backends/utils.py',
        'chunk_index': root/'third_party/flash_linear_attention/ops/index.py',
        'chunk_utils': root/'third_party/flash_linear_attention/ops/utils.py',
    }
    proof = json.loads(args.proof.read_text())
    assert digest(paths['builder']) == proof['baseline_sha256']
    assert digest(args.patch) == proof['patch_sha256']
    with tempfile.TemporaryDirectory(prefix='mtp-offline-source-') as tmp:
        target = Path(tmp)/'vllm/v1/attention/backends/gdn_attn.py'
        target.parent.mkdir(parents=True)
        target.write_bytes(paths['builder'].read_bytes())
        replay = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(args.patch.resolve())], cwd=tmp, text=True, capture_output=True, check=True)
        assert digest(target) == proof['candidate_sha256']
        candidate_text = target.read_text()
    # Keep selected definitions unmodified. Only import dependencies are injected.
    module = types.ModuleType('mtp_offline_actual_source')
    sys.modules[module.__name__] = module
    env = module.__dict__
    env.update(torch=torch, np=np, dataclass=dataclasses.dataclass, replace=dataclasses.replace,
               deprecated=lambda *a, **kw: lambda f: f, Any=object,
               PIN_MEMORY=False, PAD_SLOT_ID=-1, NULL_BLOCK_ID=0,
               np_to_pinned_tensor=lambda a: torch.from_numpy(a.copy()),
               async_tensor_h2d=lambda t, device: t.to(device=device).clone(),
               gpu_sync_allowed=contextlib.nullcontext,
               triton=types.SimpleNamespace(cdiv=lambda x, y: (x+y-1)//y))
    class Base:
        def __init__(self, kv_cache_spec, layer_names, vllm_config, device):
            self.kv_cache_spec = kv_cache_spec
            self.vllm_config = vllm_config
        @classmethod
        def __class_getitem__(cls, _): return cls
        def _init_reorder_batch_threshold(self, value, use_spec):
            self.reorder_batch_threshold = value
    class MambaSpec:
        block_size = 64
        num_speculative_blocks = 1
    env.update(AttentionMetadataBuilder=Base, MambaSpec=MambaSpec,
               AttentionCGSupport=types.SimpleNamespace(UNIFORM_BATCH='uniform'))
    # Pin arithmetic sentinels to the actual helper source, not assumed defaults.
    helper_tree = ast.parse(paths['helpers'].read_text())
    for sentinel in ('PAD_SLOT_ID', 'NULL_BLOCK_ID'):
        nodes = [n for n in helper_tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == sentinel for t in n.targets)]
        assert len(nodes) == 1
        env[sentinel] = ast.literal_eval(nodes[0].value)
    extract(paths['common'], ['CommonAttentionMetadata'], env)
    extract(paths['helpers'], ['split_decodes_and_prefills', 'compute_causal_conv1d_metadata', 'mamba_get_block_table_tensor'], env)
    extract(paths['chunk_index'], ['prepare_lens', 'prepare_chunk_indices', 'prepare_chunk_offsets'], env, strip_decorators=True)
    chunk_size_nodes = [n for n in ast.parse(paths['chunk_utils'].read_text()).body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FLA_CHUNK_SIZE' for t in n.targets)]
    assert len(chunk_size_nodes) == 1
    chunk_size = ast.literal_eval(chunk_size_nodes[0].value)
    injected = {
        'vllm.model_executor.layers.mamba.gdn.qwen_gdn_linear_attn': {'_resolve_gdn_prefill_backend': lambda config: ('unused', 'triton')},
        'vllm.third_party.flash_linear_attention.ops.utils': {'FLA_CHUNK_SIZE': chunk_size},
        'vllm.third_party.flash_linear_attention.ops.index': {name: env[name] for name in ['prepare_chunk_indices', 'prepare_chunk_offsets']},
    }
    for name, entries in injected.items():
        mod = types.ModuleType(name)
        mod.__dict__.update(entries)
        sys.modules[name] = mod
    extract(paths['builder'], ['GDNAttentionMetadata', 'GDNAttentionMetadataBuilder'], env)
    Original = env['GDNAttentionMetadataBuilder']
    with tempfile.TemporaryDirectory(prefix='mtp-candidate-') as tmp:
        target = Path(tmp)/'gdn_attn.py'
        target.write_text(candidate_text)
        extract(target, ['GDNAttentionMetadataBuilder'], env)
    Candidate = env['GDNAttentionMetadataBuilder']
    Common = env['CommonAttentionMetadata']

    def build_instance(cls, depth, graph):
        config = types.SimpleNamespace(
            compilation_config=types.SimpleNamespace(cudagraph_mode=types.SimpleNamespace(has_full_cudagraphs=lambda: graph), max_cudagraph_capture_size=None),
            speculative_config=types.SimpleNamespace(num_speculative_tokens=depth) if depth else None,
            scheduler_config=types.SimpleNamespace(max_num_seqs=16),
            cache_config=types.SimpleNamespace(mamba_cache_mode='none'))
        obj = cls(MambaSpec(), ['test'], config, torch.device('cpu'))
        # Avoid uninitialized-byte comparisons and expose stale buffer reuse.
        for value in vars(obj).values():
            if isinstance(value, torch.Tensor): value.fill_(False if value.dtype == torch.bool else -777)
        return obj

    def fixture(lengths, context, draft=None, accepted=None, prefilling=None, depth=1, graph=False):
        starts = torch.tensor([0] + list(np.cumsum(lengths)), dtype=torch.int32)
        seq = torch.tensor([a+b for a,b in zip(lengths, context)], dtype=torch.int32)
        blocks = (torch.arange(len(lengths)*(depth+2), dtype=torch.int32).reshape(len(lengths), depth+2)+11)
        m = Common(query_start_loc=starts.clone(), query_start_loc_cpu=starts.clone(), seq_lens=seq.clone(), num_reqs=len(lengths), num_actual_tokens=sum(lengths), max_query_len=max(lengths), max_seq_len=int(seq.max()), block_table_tensor=blocks, slot_mapping=torch.arange(sum(lengths)), seq_lens_cpu_upper_bound=seq.clone(), is_prefilling=None if prefilling is None else torch.tensor(prefilling, dtype=torch.bool))
        return m, None if accepted is None else torch.tensor(accepted, dtype=torch.int32), None if draft is None else torch.tensor(draft, dtype=torch.int32)

    # Explicit scheduler forms; not merely a second implementation of build().
    cases = [
        ('ordinary_decode', dict(lengths=[1,1], context=[512,16000], depth=0, prefilling=[False,False])),
        ('mtp_no_drafts_yet', dict(lengths=[1], context=[512], draft=[0], accepted=[1], prefilling=[False])),
        ('mtp_all_accepted', dict(lengths=[2,2], context=[512,2048], draft=[1,1], accepted=[2,2])),
        ('mtp_rejected_drafts', dict(lengths=[2,2], context=[512,16384], draft=[1,1], accepted=[1,1])),
        ('mtp_partial_acceptance', dict(lengths=[2,2], context=[2048,16384], draft=[1,1], accepted=[1,2])),
        ('mtp_trailing_padding', dict(lengths=[2,2,0,0], context=[512,16000,0,0], draft=[1,1,-1,-1], accepted=[1,2,1,1])),
        ('mixed_decode_prefill', dict(lengths=[1,65], context=[16000,0], prefilling=[False,True])),
        ('mixed_spec_prefill', dict(lengths=[2,65], context=[16384,0], draft=[1,-1], accepted=[1,1], prefilling=[False,True])),
        ('mixed_spec_decode_prefill_padding', dict(lengths=[2,1,129,0], context=[16384,512,0,0], draft=[1,-1,-1,-1], accepted=[2,1,1,1], prefilling=[False,False,True,False])),
        ('first_prefill_one_token', dict(lengths=[1], context=[0], prefilling=[True])),
        ('first_prefill_one_token_with_padding', dict(lengths=[1,0,0], context=[0,0,0], prefilling=[True,False,False])),
        ('resumed_prefill_one_token', dict(lengths=[1], context=[2048], prefilling=[True])),
        ('first_prefill_512', dict(lengths=[512], context=[0], prefilling=[True])),
        ('chunked_prefill_2k', dict(lengths=[2048], context=[2048], prefilling=[True])),
        ('chunked_prefill_16k', dict(lengths=[4096], context=[12288], prefilling=[True])),
        ('prefill_chunk_boundary', dict(lengths=[63,64,65], context=[0,128,512], prefilling=[True,True,True])),
        ('deeper_mtp_active_width', dict(lengths=[2,3], context=[512,16384], draft=[1,2], accepted=[1,2], depth=3)),
        ('capture_no_runner_flag', dict(lengths=[1,1,0], context=[1,1,0])),
    ]

    def flatten(value, prefix=''):
        out = {}
        if dataclasses.is_dataclass(value): value = vars(value)
        if isinstance(value, dict):
            for k,v in value.items(): out.update(flatten(v, f'{prefix}/{k}'))
        elif isinstance(value, (tuple,list)):
            for i,v in enumerate(value): out.update(flatten(v, f'{prefix}/{i}'))
        else: out[prefix] = value
        return out

    def values(value):
        out = {}
        for name, v in flatten(value).items():
            if isinstance(v, torch.Tensor):
                assert v.device.type == 'cpu'
                out[name] = {'dtype': str(v.dtype), 'shape': list(v.shape), 'stride': list(v.stride()), 'offset': v.storage_offset(), 'sha256': hashlib.sha256(v.contiguous().numpy().tobytes()).hexdigest()}
            else: out[name] = v
        return out

    def aliases(output, common, accepted, draft, builder):
        all_tensors = flatten({'output': output, 'input': vars(common), 'accepted': accepted, 'draft': draft, 'persistent': {k:v for k,v in vars(builder).items() if isinstance(v, torch.Tensor)}})
        groups = {}
        for name, v in all_tensors.items():
            if isinstance(v, torch.Tensor): groups.setdefault(v.untyped_storage()._cdata, []).append(name)
        return sorted(sorted(names) for names in groups.values() if len(names)>1)

    class CountQuerySubtractions(TorchDispatchMode):
        def __init__(self, query): self.storage=query.untyped_storage()._cdata; self.count=0
        def __torch_dispatch__(self, func, types, args=(), kwargs=None):
            if str(func) == 'aten.sub.Tensor' and len(args)>1 and all(isinstance(v, torch.Tensor) and v.untyped_storage()._cdata == self.storage for v in args[:2]): self.count += 1
            return func(*args, **(kwargs or {}))

    records = []
    for name, spec in cases:
        for graph in (False, True):
            options = dict(spec)
            depth = options.get('depth', 1)
            pair = [build_instance(cls, depth, graph) for cls in (Original,Candidate)]
            args_pair = [fixture(**options) for _ in pair]
            before = [values({'m': x[0], 'accepted': x[1], 'draft': x[2]}) for x in args_pair]
            outputs, counters = [], []
            for builder, (m, accepted, draft) in zip(pair,args_pair):
                counter = CountQuerySubtractions(m.query_start_loc)
                with counter: output = builder.build(0,m,accepted,draft)
                outputs.append(output); counters.append(counter.count)
            snapshots = [values(x) for x in outputs]
            assert snapshots[0] == snapshots[1], (name, graph, 'field mismatch')
            assert aliases(outputs[0],*args_pair[0],pair[0]) == aliases(outputs[1],*args_pair[1],pair[1]), (name, graph, 'alias mismatch')
            after = [values({'m': x[0], 'accepted': x[1], 'draft': x[2]}) for x in args_pair]
            assert after[0] == after[1]
            # The builder may add its documented computed-token cache; base inputs must not mutate.
            for b,a in zip(before,after):
                for key,value in b.items():
                    if '/_num_computed_tokens_cache' not in key: assert a[key] == value, (name,key,'input mutation')
            all_spec = outputs[0].num_spec_decodes > 0 and outputs[0].num_prefills == outputs[0].num_decodes == 0
            assert counters[0]-counters[1] == int(all_spec), (name, counters)
            # Retain prior returned views across another build with different accepted counts
            # and block IDs; equality must persist even when graph buffers are overwritten.
            for builder, inputs in zip(pair,args_pair):
                m, accepted, draft = inputs
                m.block_table_tensor.add_(1000)
                if accepted is not None: accepted.fill_(1)
                builder.build(0,m,accepted,draft)
            assert values(outputs[0]) == values(outputs[1]), (name, 'retained-view lifetime mismatch')
            assert aliases(outputs[0],*args_pair[0],pair[0]) == aliases(outputs[1],*args_pair[1],pair[1])
            records.append({'case': name, 'full_graph_metadata': graph, 'fields': len(dataclasses.fields(outputs[0])), 'exact_fields': True, 'alias_graph_equal': True, 'retained_views_after_buffer_reuse_equal': True, 'inputs_unmodified_except_documented_cache': True, 'query_source_subtractions': {'original': counters[0], 'candidate': counters[1]}, 'counts': {key:getattr(outputs[0],key) for key in ('num_prefills','num_prefill_tokens','num_decodes','num_decode_tokens','num_spec_decodes','num_spec_decode_tokens','num_actual_tokens')}, 'field_snapshot_sha256': hashlib.sha256(json.dumps(snapshots[0], sort_keys=True).encode()).hexdigest()})
    # Verify that these comparison gates detect value and alias corruption.
    sample = torch.tensor([1, 2], dtype=torch.int32)
    assert values(sample) != values(sample + 1)
    alias_fixture = types.SimpleNamespace(x=sample)
    dummy_builder = types.SimpleNamespace()
    assert aliases({'a': sample, 'b': sample}, alias_fixture, None, None, dummy_builder) != aliases({'a': sample, 'b': sample.clone()}, alias_fixture, None, None, dummy_builder)
    assert not accelerator_calls and not torch.xpu.is_initialized() and not torch.cuda.is_initialized()
    result = {'schema':'neural.download.mtp-query-lens-offline-gate.v1', 'passed':True, 'device':'cpu', 'torch_version':torch.__version__, 'script_sha256':digest(__file__), 'source_files':{k:{'path':str(v),'sha256':digest(v)} for k,v in paths.items()}, 'baseline_sha256':proof['baseline_sha256'], 'candidate_sha256':proof['candidate_sha256'], 'patch_sha256':digest(args.patch), 'patch_replay':replay.stdout, 'cases':records, 'case_count':len(records), 'comparator_negative_controls': {'value_corruption_detected': True, 'alias_corruption_detected': True}, 'accelerator_initializations':0, 'model_requests':0, 'source_execution':'Actual unmodified builder constructor/build/chunk metadata methods, CommonAttentionMetadata, classifier, state table and causal convolution helpers; actual FLA index helper bodies.', 'bounded_substitutions':['CPU copies replace asynchronous device transfer', 'CPU tensors replace pinned-memory allocation', 'Integer ceil division replaces triton.cdiv', 'Chunk tensor-cache decorators omitted; arithmetic bodies unchanged', 'Backend selection and generic builder base initialization stubbed; production branch set to triton'], 'limitations':['CPU differential and alias proof only; native XPU stream/allocator lifetime validation pending', 'CPU torch 2.11 differs from deployed torch; no native runtime identity qualification', 'No target token or performance claim', 'Graph metadata staging tested on CPU; no graph capture/replay execution']}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':True,'cases':len(records),'out':str(args.out),'accelerator_initializations':0}))

if __name__ == '__main__': main()
