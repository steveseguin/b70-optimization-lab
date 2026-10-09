# SPDX-License-Identifier: Apache-2.0
"""CPU-reviewed V30 port of lab v5 (005dc578); XPU qualification pending.

Allocate final resident/host row counts at creation, never compact a loaded
model. All logical experts remain callable; scales and arithmetic stay intact.
The offset-table mechanism is from the lab's placement series (Codex Agent,
Claude Fable 5.1). This port is restricted to serialized block-FP8 Triton/EP4.
"""
import json
import math
import os
from pathlib import Path
import re


def enabled():
    return bool(os.environ.get('Q38_EXPERT_HOST_PLACEMENT'))


def row_plan(raw, rank, layer, experts=128):
    """Pure CPU validation shared by prediction, allocation and tests."""
    if set(raw) != {'0', '1', '2', '3'}:
        raise ValueError('v5 requires an explicit four-rank map')
    ranks = raw[str(rank)]
    if any(not k.isdecimal() or not 0 <= int(k) < 48 for k in ranks):
        raise ValueError('placement layer outside target [0,48)')
    rows = ranks.get(str(layer), [])
    if (not isinstance(rows, list) or any(type(e) is not int or not 0 <= e < experts for e in rows)
            or len(rows) != len(set(rows)) or len(rows) == experts):
        raise ValueError('invalid/duplicate/all-host expert rows')
    host = sorted(rows)
    return [e for e in range(experts) if e not in set(host)], host


def layer_rows(layer, experts):
    if not enabled():
        return [], []
    from vllm.distributed import get_tensor_model_parallel_rank
    name = layer.layer_name
    found = re.search(r'layers\.(\d+)\.', name)
    if not found:
        raise RuntimeError(f'v5 cannot identify layer: {name}')
    index = int(found.group(1))
    if index >= 48:  # draft is device-resident, as in the certified lane
        return list(range(experts)), []
    if experts != 128 or layer.expert_placement_strategy != 'linear':
        raise RuntimeError('v5 requires EP4 linear placement of 512 experts')
    raw = json.loads(Path(os.environ['Q38_EXPERT_HOST_PLACEMENT']).read_text())
    return row_plan(raw, get_tensor_model_parallel_rank(), index, experts)


def validate_method(method, layer):
    if not enabled():
        return
    from vllm.platforms import current_platform
    if (not current_platform.is_xpu() or method.fp8_backend.name != 'TRITON'
            or not method.block_quant or method.moe.has_bias
            or layer.moe_config.moe_parallel_config.enable_eplb):
        raise RuntimeError('v5 requires XPU block-FP8 Triton, no bias/EPLB')


def offsets(resident_base, host_base, resident_rows, host_rows, row_bytes, itemsize):
    """Signed offsets used by the unchanged K loop; preserve 256 alignment."""
    count = len(resident_rows) + len(host_rows)
    if sorted(resident_rows + host_rows) != list(range(count)):
        raise ValueError('row partition must cover all logical experts exactly once')
    table = [0] * count
    for base, rows in ((resident_base, resident_rows), (host_base, host_rows)):
        for index, logical in enumerate(rows):
            delta = ((base + index * row_bytes - resident_base) + 2**63) % 2**64 - 2**63
            if delta % itemsize or (delta // itemsize) % 256:
                raise ValueError('unaligned v5 row offset')
            table[logical] = delta // itemsize
    return table



def local_row_tables(resident_rows, host_rows, row_elements):
    """Per-expert in-allocation row index and host selector; no addresses."""
    count = len(resident_rows) + len(host_rows)
    if sorted(resident_rows + host_rows) != list(range(count)):
        raise ValueError('row partition must cover all logical experts exactly once')
    if row_elements <= 0 or row_elements % 256:
        raise ValueError('unaligned hostptr row stride')
    local_rows, is_host = [0] * count, [0] * count
    for selector, rows in enumerate((resident_rows, host_rows)):
        for index, logical in enumerate(rows):
            local_rows[logical], is_host[logical] = index, selector
    return local_rows, is_host


def storage_facts(*tensors):
    """Immutable host-side snapshot; querying tensor metadata submits no work."""
    return tuple((tensor.data_ptr(), tuple(tensor.shape), tensor.stride(),
                  str(tensor.dtype), str(tensor.device)) for tensor in tensors)


def validate_hostptr_storage(param):
    if storage_facts(param, param._q38_host_cpu, param._q38_host_storage) != param._q38_storage_facts:
        raise RuntimeError('v5 hostptr storage changed after table construction')


def allocate_weight(layer, name, shape, dtype):
    import torch
    from vllm import screen1b_guard as guard
    from vllm.utils.torch_utils import get_accelerator_view_from_cpu_tensor
    resident_rows, host_rows = layer_rows(layer, shape[0])
    if not host_rows:
        return torch.nn.Parameter(torch.empty(shape, dtype=dtype), requires_grad=False)
    tail = tuple(shape[1:])
    itemsize = torch.empty((), device='meta', dtype=dtype).element_size()
    row_bytes = math.prod(tail) * itemsize
    allocation = guard.pinned_allocation_bytes(len(host_rows) * row_bytes)
    with guard.admission('v5_final_host_rows', allocation['allocator_request_bytes']):
        host = torch.empty((len(host_rows), *tail), dtype=dtype, device='cpu', pin_memory=True)
        if not host.is_contiguous() or host.stride(0) * itemsize != row_bytes:
            raise RuntimeError('v5 host rows must remain contiguous with unchanged row stride')
        if not host.is_pinned():
            raise RuntimeError('v5 host allocation was not pinned')
        resident = torch.empty((len(resident_rows), *tail), dtype=dtype)
        if resident.device.type != 'xpu':
            raise RuntimeError('v5 resident allocation requires active XPU device')
        # Explicit device: no default-device or rank-zero UVA alias.
        with torch.xpu.device(resident.device):
            uva = get_accelerator_view_from_cpu_tensor(host)
        if uva.device != resident.device:
            raise RuntimeError("v5 UVA view belongs to another XPU")
        table = torch.tensor(offsets(resident.data_ptr(), uva.data_ptr(), resident_rows,
                                     host_rows, row_bytes, itemsize),
                             dtype=torch.int64, device='cpu').to(resident.device)
        local_rows, is_host = local_row_tables(resident_rows, host_rows,
                                               row_bytes // itemsize)
        local_table = torch.tensor(local_rows, dtype=torch.int64,
                                   device='cpu').to(resident.device)
        host_table = torch.tensor(is_host, dtype=torch.uint8,
                                  device='cpu').to(resident.device)
        if (uva.data_ptr() != host.data_ptr() or uva.dtype != host.dtype
                or tuple(uva.shape) != tuple(host.shape)
                or uva.stride() != host.stride()):
            raise RuntimeError('v5 hostptr UVA must preserve pointer/dtype/shape/stride')
        param = torch.nn.Parameter(resident, requires_grad=False)
        param._q38_row_map = ({e: ('resident', i) for i, e in enumerate(resident_rows)} |
                              {e: ('host', i) for i, e in enumerate(host_rows)})
        param._q38_host_cpu = host
        param._q38_host_storage = uva
        param._q38_num_experts = shape[0]
        # Preserve the original signed-offset oracle for review, not GPU reads.
        param._q38_base_table = table
        param._q38_local_row_table = local_table
        param._q38_is_host_table = host_table
        param._q38_storage_facts = storage_facts(param, host, uva)
        # Save on __dict__, not register a second parameter alias in the module.
        layer.__dict__['_q38_placed_' + name] = param
        guard.receipt('v5_allocated', layer=layer.layer_name, parameter=name,
                      logical_experts=shape[0], host_rows=len(host_rows),
                      host_bytes=host.numel()*itemsize, device_bytes=resident.numel()*itemsize,
                      pinned_allocation=allocation, host_stride=list(host.stride()),
                      host_alignment_remainder=host.data_ptr() % 256)
        return param


def row_view(param, expert_id):
    mapping = getattr(param, '_q38_row_map', None)
    if mapping is None:
        return param.data[expert_id]
    kind, index = mapping[expert_id]
    return param.data[index] if kind == 'resident' else param._q38_host_cpu[index]


def restore(layer):
    """Restore metadata only for unchanged storage; never silently drop a table."""
    for name in ('w13_weight', 'w2_weight'):
        saved = layer.__dict__.get('_q38_placed_' + name)
        if saved is None:
            continue
        current = getattr(layer, name)
        if current.data_ptr() != saved.data_ptr() or current.shape != saved.shape:
            raise RuntimeError('v5 postprocessing changed placed weight storage')
        for key in ('_q38_row_map', '_q38_host_cpu', '_q38_host_storage',
                    '_q38_num_experts', '_q38_base_table',
                    '_q38_local_row_table', '_q38_is_host_table',
                    '_q38_storage_facts'):
            setattr(current, key, getattr(saved, key))
