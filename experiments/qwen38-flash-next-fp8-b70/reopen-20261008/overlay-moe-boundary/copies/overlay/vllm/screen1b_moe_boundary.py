# SPDX-License-Identifier: Apache-2.0
"""Default-off Screen 1b structural diagnostic; never repairs tensors.

Native USM kind/context/residency cannot be inferred from Torch storage. The
receipts explicitly leave these unknown. Only CPU snapshots are inspected;
every readback follows a queue drain and fresh watcher/latch checks.
"""
import hashlib
import json
import os
from pathlib import Path
import time

ENABLE = "SCREEN1B_MOE_BOUNDARY"
POINTERS = ("a_ptr", "b_ptr", "b_table_ptr", "c_ptr", "b_bias_ptr",
            "a_scale_ptr", "b_scale_ptr", "topk_weights_ptr",
            "sorted_token_ids_ptr", "expert_ids_ptr", "num_tokens_post_padded_ptr")

INTENDED_OWNERS = {
    "a_ptr": "NoDPEP/activation quantizer rank-local output",
    "b_ptr": "placement resident rows; indirect host rows retained separately",
    "b_table_ptr": "placement rank-local int64 offset table or unused B placeholder",
    "c_ptr": "workspace2 output view; writable",
    "b_bias_ptr": "absent in declared FP8 lane",
    "a_scale_ptr": "activation quantizer rank-local FP32 scales",
    "b_scale_ptr": "post-load logical-local FP32 weight scales",
    "topk_weights_ptr": "absent for w13; rank-local router output for w2",
    "sorted_token_ids_ptr": "native alignment rank-local route output",
    "expert_ids_ptr": "rank expert-map remap output",
    "num_tokens_post_padded_ptr": "native alignment rank-local count output",
}


class BoundaryError(RuntimeError):
    pass


def enabled():
    value = os.environ.get(ENABLE, "0")
    if value not in ("0", "1"):
        raise BoundaryError("SCREEN1B_MOE_BOUNDARY must be 0 or 1")
    return value == "1"


def span(t):
    """Metadata only: no device command or tensor-value read."""
    storage = t.untyped_storage()
    start = t.data_ptr()
    width = t.element_size()
    size = 0 if t.numel() == 0 else (1 + sum((n-1)*s for n, s in zip(t.shape, t.stride()))) * width
    return dict(pointer=start, end=start+size, storage_base=storage.data_ptr(),
                storage_end=storage.data_ptr()+storage.nbytes(), storage_offset=t.storage_offset(),
                shape=list(t.shape), stride=list(t.stride()), dtype=str(t.dtype),
                device=str(t.device), bytes=size)


def overlaps(a, b):
    return a["pointer"] < b["end"] and b["pointer"] < a["end"]


class Boundary:
    def __init__(self, directory, watcher, rank, device, synchronize, *, cpu_test=False):
        self.directory, self.watcher = Path(directory), Path(watcher)
        self.rank, self.device, self.pid = rank, str(device), os.getpid()
        self.synchronize, self.cpu_test = synchronize, cpu_test
        self.boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / f"rank{rank}-pid{self.pid}.jsonl"
        self.failed = False
        self.sequence = 0
        self.allocations = {}
        self.alignment = {}

    def emit(self, phase, **values):
        self.sequence += 1
        row = dict(rank=self.rank, pid=self.pid, device=self.device, phase=phase,
                   sequence=self.sequence, unix=time.time(), monotonic=time.monotonic(),
                   boot_id=self.boot, **values)
        # Open/flush/fsync per row: a native crash must not hide completed checks.
        with self.path.open("a") as f:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False)+"\n")
            f.flush()
            os.fsync(f.fileno())

    def latch(self, reason):
        self.failed = True
        # Share cancellation immediately across ranks; never overwrite evidence.
        try:
            with (self.watcher.parent / "STOP").open("x") as f:
                f.write(f"MoE boundary rank={self.rank} pid={self.pid}: {reason}\n")
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            pass

    def require(self, ok, message, **values):
        if not ok:
            self.latch(message)
        self.emit("check", check=message, passed=bool(ok), **values)
        if not ok:
            raise BoundaryError(f"MoE boundary rank={self.rank}: {message}")

    def clear(self):
        if self.failed:
            raise BoundaryError("MoE boundary already failed; no further device work")
        try:
            if any((self.watcher.parent / name).exists() for name in ("STOP", "FAULT", "FAULT.json")):
                raise ValueError("fault/stop latch set")
            w = json.loads(self.watcher.read_text())
            now = time.time()
            if (w.get("passed") is not True or w.get("boot_id") != self.boot
                    or w.get("new_fault_lines") != []
                    or not 0 <= now-w["updated_unix"] <= 3
                    or not 0 <= now-w["read_started_unix"] <= 3):
                raise ValueError("watcher missing clean fresh same-boot approval")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.require(False, "watcher/fault latch: " + str(exc))

    def stage(self, phase):
        self.clear()
        self.emit(phase+".sync_begin")
        try:
            self.synchronize()
        except BaseException as exc:
            self.latch(phase+": synchronization failed")
            self.emit(phase+".sync_failed", exception=repr(exc))
            raise BoundaryError(f"MoE boundary {phase}: synchronization failed") from exc
        self.clear()
        self.emit(phase+".sync_complete")

    def snapshot(self, tensor, phase):
        self.stage(phase)
        self.clear()
        # No GPU conversion/contiguous kernel before the guarded readback.
        try:
            cpu = tensor.detach().cpu()
        except BaseException as exc:
            self.latch(phase+": readback failed")
            self.emit(phase+".readback_failed", exception=repr(exc))
            raise BoundaryError(f"MoE boundary {phase}: readback failed") from exc
        self.clear()
        raw = cpu.contiguous().view(__import__("torch").uint8).numpy().tobytes()
        self.emit(phase+".snapshot", sha256=hashlib.sha256(raw).hexdigest(), tensor_span=span(tensor))
        return cpu

    def register(self, tensor, label):
        s = span(tensor)
        self.require(all(x >= 0 for x in tensor.stride()) and
                     s["storage_base"] <= s["pointer"] <= s["end"] <= s["storage_end"],
                     "tensor span within allocation", label=label, span=s)
        key = (s["storage_base"], s["storage_end"], str(tensor.device))
        previous = self.allocations.get(key)
        if previous is None:
            previous = dict(owner_pid=self.pid, owner_rank=self.rank, owner_device=str(tensor.device),
                            first_observed_as=label, allocation_id=len(self.allocations)+1)
            self.allocations[key] = previous
        return dict(**s, **previous, native_usm_kind=None, native_context=None,
                    native_residency_verified=False, provenance="retained Torch storage; first observation")

    def device_tensor(self, tensor, label):
        self.require(str(tensor.device) == self.device, "pointer device/owner mismatch", label=label,
                     expected=self.device, actual=str(tensor.device))
        self.require(self.cpu_test or tensor.device.type == "xpu", "runtime requires XPU pointer", label=label)
        return self.register(tensor, label)

    def router(self, topk, expert_map, block, global_experts, ignore_invalid=False):
        self.clear()
        self.require(global_experts == 512 and block > 0 and not ignore_invalid,
                     "unsupported alignment geometry/filter", global_experts=global_experts, block=block)
        self.device_tensor(topk, "router.topk_ids")
        self.require(topk.ndim == 2 and topk.is_contiguous()
                     and str(topk.dtype) in ("torch.int32", "torch.int64"), "router ID dtype/shape/layout")
        ids = self.snapshot(topk, "router.ids").reshape(-1).tolist()
        self.require(all(0 <= x < 512 for x in ids), "router IDs outside [0,512)", count=len(ids))
        self.require(expert_map is not None, "TP4 expert map required")
        self.device_tensor(expert_map, "router.expert_map")
        self.require(str(expert_map.dtype) == "torch.int32" and list(expert_map.shape) == [512]
                     and expert_map.is_contiguous(), "expert map dtype/layout")
        mapping = self.snapshot(expert_map, "router.map").tolist()
        expected = [-1]*512
        expected[self.rank*128:(self.rank+1)*128] = list(range(128))
        self.require(mapping == expected, "rank expert map ownership/coverage", rank_start=self.rank*128)
        return dict(routes=ids, mapping=mapping, block=block, M=topk.shape[0], topk=topk.shape[1])

    def raw_alignment(self, state, sorted_ids, raw_ids, padded):
        for label, tensor in (("sorted", sorted_ids), ("raw_experts", raw_ids), ("padded", padded)):
            self.device_tensor(tensor, "alignment."+label)
            self.require(str(tensor.dtype) == "torch.int32" and tensor.ndim == 1 and tensor.is_contiguous(),
                         "alignment buffer dtype/layout", label=label)
        self.require(padded.numel() == 1, "padded count scalar capacity")
        count = self.snapshot(padded, "alignment.padded").item()
        raw = self.snapshot(raw_ids, "alignment.raw_experts").tolist()
        # Entire tail is about to be indexed by production expert_map[expert_ids].
        self.require(all(0 <= x < 512 for x in raw), "raw alignment IDs outside [0,512), including tail", values=raw)
        block, routes = state["block"], state["routes"]
        self.require(0 <= count <= sorted_ids.numel() and count % block == 0 and count//block <= len(raw),
                     "padded layout capacity/divisibility", padded=count, capacity=sorted_ids.numel(), block=block)
        hist = [routes.count(e) for e in range(512)]
        expected = sum((n+block-1)//block*block for n in hist)
        self.require(count == expected, "padded counts inconsistent with M*topk", expected=expected, actual=count)
        ordered = self.snapshot(sorted_ids, "alignment.sorted")[:count].tolist()
        self.require(all(0 <= x <= len(routes) for x in ordered), "sorted route index/padding out of bounds")
        self.require(sorted(x for x in ordered if x < len(routes)) == list(range(len(routes))),
                     "sorted routes missing/duplicate; M*topk coverage")
        for start in range(0, count, block):
            e = raw[start//block]
            chunk = ordered[start:start+block]
            if not all(x == len(routes) or routes[x] == e for x in chunk):
                self.require(False, "sorted route assigned to wrong expert", block=start//block, expert=e)
        self.emit("alignment.block_membership_pass", blocks=count//block)
        blocks = [0]*512
        for e in raw[:count//block]:
            blocks[e] += 1
        self.require(blocks == [(n+block-1)//block for n in hist], "padded expert histogram mismatch")
        state.update(raw=raw, count=count, sorted=ordered)
        self.emit("alignment.raw_pass", count=count, M=state["M"], topk=state["topk"])

    def remapped(self, state, local, sorted_ids, padded):
        self.device_tensor(local, "alignment.remapped")
        self.require(str(local.dtype) == "torch.int32" and local.ndim == 1
                     and local.numel() == len(state["raw"]) and local.is_contiguous(),
                     "remapped ID dtype/layout")
        values = self.snapshot(local, "alignment.remapped").tolist()
        self.require(values == [state["mapping"][e] for e in state["raw"]],
                     "local remap differs from rank expert map")
        active = values[:state["count"]//state["block"]]
        self.require(all(x == -1 or 0 <= x < 128 for x in active), "active local expert out of range")
        self.emit("alignment.local_pass", values=active, nonlocal_zero_blocks=active.count(-1),
                  no_negative_weight_access=True)
        state["local"] = values
        state["owners"] = (local, sorted_ids, padded)  # retain producer allocations
        self.alignment = state
        self.clear()

    def weights(self, weight, local_experts=128):
        self.device_tensor(weight, "weight.resident")
        self.require(weight.ndim == 3 and weight.is_contiguous(), "weight layout unsupported")
        self.require(str(weight.dtype) == "torch.float8_e4m3fn" or
                     (self.cpu_test and str(weight.dtype) == "torch.float32"), "weight FP8 dtype")
        compact = weight.shape[0] != local_experts
        table = getattr(weight, "_q38_base_table", None)
        self.require(not compact or table is not None, "compact weight missing base-table attribute")
        if table is None:
            self.require(weight.shape[0] == local_experts, "dense weight expert capacity")
            return
        self.require(getattr(weight, "_q38_num_experts", None) == local_experts, "compact logical expert count")
        stamp = getattr(weight, "_screen1b_boundary_owner", None)
        self.require(stamp == (self.pid, self.rank, self.device), "compact weight allocation owner mismatch", owner=stamp)
        self.device_tensor(table, "weight.base_table")
        self.require(str(table.dtype) == "torch.int64" and list(table.shape) == [local_experts] and table.is_contiguous(),
                     "base table dtype/length/layout")
        host = getattr(weight, "_q38_host_cpu", None)
        alias = getattr(weight, "_q38_host_storage", None)
        mapping = getattr(weight, "_q38_row_map", None)
        self.require(host is not None and alias is not None and isinstance(mapping, dict), "compact retained owners missing")
        self.require(host.device.type == "cpu" and (self.cpu_test or host.is_pinned()), "host owner must be pinned CPU")
        self.device_tensor(alias, "weight.host_alias")
        self.register(host, "weight.host_cpu")
        self.require(host.is_contiguous() and alias.is_contiguous() and host.shape == alias.shape
                     and host.dtype == alias.dtype == weight.dtype and host.stride() == alias.stride()
                     and tuple(host.shape[1:]) == tuple(weight.shape[1:]), "host alias geometry mismatch")
        # The native view in this lane must retain the exact same host VA.
        self.require(alias.data_ptr() == host.data_ptr(), "host alias address differs from retained owner")
        self.require(sorted(mapping) == list(range(local_experts)), "row-map logical coverage")
        self.require(sorted(mapping.values()) == sorted(
            [("resident", i) for i in range(weight.shape[0])] + [("host", i) for i in range(host.shape[0])]),
            "row-map physical partition")
        offsets = self.snapshot(table, "weight.base_table").tolist()
        row_bytes = weight.shape[1]*weight.shape[2]*weight.element_size()
        spans = {"resident": span(weight), "host": span(alias)}
        rows = []
        for e in range(local_experts):
            kind, index = mapping[e]
            owner = spans[kind]
            address = (weight.data_ptr()+offsets[e]*weight.element_size()) % (1<<64)
            expected = owner["pointer"]+index*row_bytes
            if not (offsets[e] % 256 == 0 and address == expected
                    and owner["pointer"] <= address and address+row_bytes <= owner["end"]):
                self.require(False, "weight row outside owned span or wrong row", expert=e, kind=kind,
                             row_index=index, address=address, expected=expected, row_bytes=row_bytes)
            rows.append([e, kind, index, address, address+row_bytes])
        self.emit("weight.rows_pass", rows=rows, row_bytes=row_bytes)

    def workspace(self, w13, w2, M, topk, N, K, activation_dim, output=None):
        a, b = self.device_tensor(w13, "workspace13"), self.device_tensor(w2, "workspace2")
        self.require(w13.is_contiguous() and w2.is_contiguous() and w13.dtype == w2.dtype
                     and (str(w13.dtype) == "torch.bfloat16" or
                          (self.cpu_test and str(w13.dtype) == "torch.float32")),
                     "workspace layout/dtype")
        needs = [M*topk*max(activation_dim, K), M*topk*max(N, K)]
        self.require(M > 0 and topk > 0 and N > 0 and K > 0 and activation_dim > 0
                     and w13.numel() >= needs[0] and w2.numel() >= needs[1],
                     "workspace capacity for M/topk/N/K", M=M, topk=topk, N=N, K=K,
                     required_elements=needs, actual_elements=[w13.numel(), w2.numel()])
        self.require(not overlaps(a, b), "workspace13/workspace2 overlap", workspace13=a, workspace2=b)
        if output is not None:
            out = self.device_tensor(output, "workspace.output")
            self.require(output.dtype == w13.dtype and output.numel() >= M*K
                         and not overlaps(out, b), "output capacity/workspace2 overlap")
            self.require(not overlaps(out, a) or (a["pointer"] <= out["pointer"] and out["end"] <= a["end"]),
                         "output alias exceeds workspace13")
        self.emit("workspace.pass", sequential_aliases=["cache1/cache3 in workspace2", "output in workspace13"])

    def before_gemm(self, A, B, C, A_scale, B_scale, routes, sorted_ids, local_ids, padded,
                    topk, config, block_shape, bias, mul_weight):
        import torch
        self.stage("gemm.pre")
        state = self.alignment
        self.require(bool(state), "GEMM missing validated alignment")
        self.require(all(x is y for x, y in zip(state["owners"], (local_ids, sorted_ids, padded))),
                     "GEMM alignment producer identity mismatch")
        local = self.snapshot(local_ids, "gemm.local_ids").tolist()
        current_count = self.snapshot(padded, "gemm.padded").item()
        current_sort = self.snapshot(sorted_ids, "gemm.sorted")[:state["count"]].tolist()
        self.require(local == state["local"] and current_count == state["count"] and current_sort == state["sorted"],
                     "alignment mutated before GEMM")
        self.require(config["BLOCK_SIZE_M"] == state["block"] and block_shape == [128, 128], "GEMM config mismatch")
        self.weights(B)
        self.require(A.ndim == 2 and C.ndim == 3 and A.is_contiguous() and C.is_contiguous(), "GEMM A/C layout")
        self.require((A.dtype == B.dtype and str(A.dtype) == "torch.float8_e4m3fn"
                      and C.dtype == torch.bfloat16) or
                     (self.cpu_test and A.dtype == B.dtype == C.dtype == torch.float32),
                     "GEMM FP8 input/BF16 output dtype")
        self.require(topk in (1, state["topk"]) and A.shape[0]*topk == state["M"]*state["topk"] and A.shape[1] == B.shape[2]
                     and list(C.shape) == [state["M"], state["topk"], B.shape[1]], "GEMM A/C capacity")
        self.require(A_scale is not None and B_scale is not None and bias is None, "FP8 scale/bias contract")
        self.require(A_scale.dtype == B_scale.dtype == torch.float32
                     and list(A_scale.shape) == [A.shape[0], (B.shape[2]+127)//128]
                     and list(B_scale.shape) == [128, (B.shape[1]+127)//128, (B.shape[2]+127)//128]
                     and A_scale.is_contiguous() and B_scale.is_contiguous(), "FP8 scale capacity/layout")
        self.require(not mul_weight or (routes is not None and routes.numel() == state["M"]*state["topk"]
                     and routes.dtype == torch.float32 and routes.is_contiguous()), "route weight capacity/layout")
        table = getattr(B, "_q38_base_table", None)
        tensors = (A, B, B if table is None else table, C, bias, A_scale, B_scale,
                   routes, sorted_ids, local_ids, padded)
        census = {}
        for label, tensor in zip(POINTERS, tensors):
            census[label] = None if tensor is None else self.device_tensor(tensor, label)
        for label, tensor in zip(POINTERS, tensors):
            if tensor is not None and label != "c_ptr":
                self.require(not overlaps(span(C), span(tensor)), "GEMM output overlaps live input", pointer=label)
        host_alias = getattr(B, "_q38_host_storage", None)
        if host_alias is not None:
            self.require(not overlaps(span(C), span(host_alias)), "GEMM output overlaps indirect host rows")
        self.emit("gemm.launch_ready", pointers=census, pointer_sources=INTENDED_OWNERS,
                  config=config, block_shape=block_shape,
                  topk=topk, mul_routed_weight=mul_weight, table_placeholder=table is None,
                  negative_blocks="validated nonlocal zero-write return before table/weight/dot",
                  native_usm_context_verified=False)
        self.clear()


_instances = {}


def get(device):
    """Never called on the off path. No import-time Torch/device activity."""
    if not enabled():
        raise BoundaryError("boundary get called while disabled")
    import torch
    from vllm.distributed import get_tensor_model_parallel_rank
    rank = get_tensor_model_parallel_rank()
    key = (os.getpid(), rank, str(device))
    if key not in _instances:
        _instances[key] = Boundary(os.environ["SCREEN1B_MOE_BOUNDARY_DIR"],
            os.environ["SCREEN1B_MOE_BOUNDARY_WATCHER"], rank, device,
            lambda: torch.xpu.synchronize(device))
    return _instances[key]


def stamp_weight(weight):
    if enabled():
        b = get(weight.device)
        b.clear()
        weight._screen1b_boundary_owner = (b.pid, b.rank, b.device)
        b.device_tensor(weight, "placement.allocation")
