"""Native metadata differential gate, invoked only by the idle owning XPU worker.

Importing this module performs no torch import or GPU action. The caller owns
service admission, fault monitoring and serialization against inference. This
function neither changes an installed builder nor launches a model or worker.
"""
from __future__ import annotations
import ast
import dataclasses
import gc
import hashlib
import json
import types


def compile_build_from_source(source: str, namespace: dict):
    """Compile only the exact supplied build method with installed helper globals."""
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GDNAttentionMetadataBuilder')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'build')
    assert not method.decorator_list
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), method], type_ignores=[])
    env = dict(namespace)
    exec(compile(ast.fix_missing_locations(module), '<hash-bound-mtp-builder>', 'exec'), env)
    return env['build']


def run_native_metadata_gate(device, original_build, candidate_build):
    """Compare actual original/candidate methods on native helper/tensor operations.

    Device must already be initialized by the owning worker. All fixture buffers
    are private to this call. The source methods must use the installed module's
    globals; caller must bind their full source hashes in its RPC result.
    """
    import torch
    from vllm.v1.attention.backends.gdn_attn import GDNAttentionMetadataBuilder
    from vllm.v1.attention.backend import CommonAttentionMetadata
    device = torch.device(device)
    assert device.type == 'xpu', device
    assert torch.xpu.is_initialized(), 'Owning worker must initialize XPU first'
    assert original_build.__name__ == 'build'
    assert candidate_build.__name__ in ('build', '_mtp_candidate_build')
    required_helpers = ('mamba_get_block_table_tensor', 'split_decodes_and_prefills', 'compute_causal_conv1d_metadata', 'async_tensor_h2d')
    assert all(original_build.__globals__[name] is candidate_build.__globals__[name] for name in required_helpers)

    def factory(depth, graph):
        # Test only metadata: no production builder, model state, target weights,
        # request scheduler or service configuration is touched. These are the
        # exact fields consumed by build() and its unchanged chunk helper.
        obj = GDNAttentionMetadataBuilder.__new__(GDNAttentionMetadataBuilder)
        obj.vllm_config = types.SimpleNamespace(cache_config=types.SimpleNamespace(mamba_cache_mode='none'))
        obj.kv_cache_spec = None  # 'none' mode returns block_table without inspecting spec.
        obj.num_spec = depth
        obj.use_spec_decode = depth > 0
        obj.use_full_cuda_graph = graph
        obj.decode_cudagraph_max_bs = 16 * (depth + 1)
        obj.gdn_prefill_backend = 'triton'
        n = obj.decode_cudagraph_max_bs
        for name, shape, dtype in (
            ('spec_state_indices_tensor', (n,depth+1), torch.int32),
            ('non_spec_state_indices_tensor', (n,), torch.int32),
            ('spec_sequence_masks', (n,), torch.bool),
            ('spec_token_indx', (n*(depth+1),), torch.int32),
            ('non_spec_token_indx', (n*(depth+1),), torch.int32),
            ('spec_query_start_loc', (n+1,), torch.int32),
            ('non_spec_query_start_loc', (n+1,), torch.int32),
            ('num_accepted_tokens', (n,), torch.int32),
        ):
            setattr(obj,name,torch.full(shape,False if dtype == torch.bool else -777,dtype=dtype,device=device))
        return obj

    def fixture(lengths, context, draft=None, accepted=None, prefilling=None, depth=1):
        starts = [0]
        for length in lengths: starts.append(starts[-1]+length)
        qcpu = torch.tensor(starts,dtype=torch.int32)
        scpu = torch.tensor([a+b for a,b in zip(lengths,context)],dtype=torch.int32)
        m = CommonAttentionMetadata(
            query_start_loc=qcpu.to(device), query_start_loc_cpu=qcpu.clone(),
            seq_lens=scpu.to(device), num_reqs=len(lengths), num_actual_tokens=sum(lengths),
            max_query_len=max(lengths), max_seq_len=max(a+b for a,b in zip(lengths,context)),
            block_table_tensor=(torch.arange(len(lengths)*(depth+2),dtype=torch.int32,device=device).reshape(len(lengths),depth+2)+11),
            slot_mapping=torch.arange(sum(lengths),device=device),
            seq_lens_cpu_upper_bound=scpu.clone(),
            is_prefilling=None if prefilling is None else torch.tensor(prefilling,dtype=torch.bool))
        return m, None if accepted is None else torch.tensor(accepted,dtype=torch.int32,device=device), None if draft is None else torch.tensor(draft,dtype=torch.int32)

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
        out={}
        if dataclasses.is_dataclass(value): value=vars(value)
        if isinstance(value,dict):
            for key,v in value.items(): out.update(flatten(v,f'{prefix}/{key}'))
        elif isinstance(value,(tuple,list)):
            for key,v in enumerate(value): out.update(flatten(v,f'{prefix}/{key}'))
        else: out[prefix]=value
        return out

    def snapshot(value):
        out={}
        for name,v in flatten(value).items():
            if isinstance(v,torch.Tensor):
                out[name]={'dtype':str(v.dtype),'device_type':v.device.type,'shape':list(v.shape),'stride':list(v.stride()),'offset':v.storage_offset(),'sha256':hashlib.sha256(v.detach().contiguous().cpu().numpy().tobytes()).hexdigest()}
            else: out[name]=v
        return out

    def aliases(output, common, accepted, draft, builder):
        items=flatten({'output':output,'input':vars(common),'accepted':accepted,'draft':draft,'persistent':{k:v for k,v in vars(builder).items() if isinstance(v,torch.Tensor)}})
        groups={}
        for name,v in items.items():
            if isinstance(v,torch.Tensor): groups.setdefault(v.untyped_storage()._cdata,[]).append(name)
        return sorted(sorted(names) for names in groups.values() if len(names)>1)

    results=[]
    for name,options in cases:
        for graph in (False,True):
            depth=options.get('depth',1)
            builders=[factory(depth,graph),factory(depth,graph)]
            inputs=[fixture(**options),fixture(**options)]
            before=[snapshot({'m':i[0],'accepted':i[1],'draft':i[2]}) for i in inputs]
            outputs=[method(builder,0,*args) for method,builder,args in zip((original_build,candidate_build),builders,inputs)]
            # Complete the worker's current-stream work before inspecting values.
            torch.xpu.synchronize(device)
            snapshots=[snapshot(x) for x in outputs]
            assert snapshots[0] == snapshots[1], (name,graph,'metadata differs')
            assert aliases(outputs[0],*inputs[0],builders[0]) == aliases(outputs[1],*inputs[1],builders[1]), (name,graph,'alias differs')
            for old,args in zip(before,inputs):
                current=snapshot({'m':args[0],'accepted':args[1],'draft':args[2]})
                for key,value in old.items():
                    if '/_num_computed_tokens_cache' not in key: assert current[key] == value,(name,key,'input mutation')
            # Keep returned metadata alive while async copies refill private graph
            # buffers and allocator scratch is released/reused. No alternate stream
            # is invented: production metadata is built on its current stream.
            for generation in range(3):
                for method,builder,args in zip((original_build,candidate_build),builders,inputs):
                    m,accepted,draft=args
                    m.block_table_tensor.add_(1000)
                    if accepted is not None: accepted.fill_(1 if generation % 2 == 0 else 2)
                    scratch=method(builder,0,m,accepted,draft)
                    del scratch
                gc.collect()
            torch.xpu.synchronize(device)
            assert snapshot(outputs[0]) == snapshot(outputs[1]),(name,graph,'retained-view lifetime differs')
            assert aliases(outputs[0],*inputs[0],builders[0]) == aliases(outputs[1],*inputs[1],builders[1]),(name,graph,'retained aliases differ')
            results.append({'case':name,'full_graph_metadata':graph,'exact_fields':len(dataclasses.fields(outputs[0])),'aliases_equal':True,'buffer_reuses':3,'retained_views_equal':True,'inputs_unmodified_except_documented_cache':True,'snapshot_sha256':hashlib.sha256(json.dumps(snapshots[0],sort_keys=True).encode()).hexdigest(),'counts':{key:getattr(outputs[0],key) for key in ('num_prefills','num_prefill_tokens','num_decodes','num_decode_tokens','num_spec_decodes','num_spec_decode_tokens','num_actual_tokens')}})
    torch.xpu.synchronize(device)
    return {'schema':'neural.download.mtp-query-lens-native-gate.v1','passed':True,'device':str(device),'torch_version':str(torch.__version__),'cases':results,'case_count':len(results),'native_helpers':list(required_helpers)+['_build_chunk_metadata'],'production_builder_changed':False,'model_requests':0,'limitations':['Metadata fixtures use private test builder attributes; production builder initialization unchanged and not under test','FULL graph metadata staging only; no graph capture/replay','Target token identity and performance require separate full endpoint gates','No cross-stream safety claim; tests use owning worker current stream']}
