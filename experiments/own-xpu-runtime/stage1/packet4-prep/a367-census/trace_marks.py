"""Host-only ITT scopes for the admitted census; import is CPU-only.

No tensor contents, device events, synchronization or arithmetic are touched.
Scopes identify host submissions; only PTI flow IDs can connect device events.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
import hashlib
import inspect
import json
import os
from pathlib import Path
import threading
import time


SOURCE_PINS = {
    "vllm/v1/worker/gpu/model_runner.py": "aa2b1f1f2c3bf9277f6cad3639ee7f76874485a171bf673a28a130553c16f218",
    "vllm/v1/worker/gpu_worker.py": "e7d59285879d3dce70d891b99e0e6892bd96ef93c3a4746b3fc723b5086df4d5",
    "vllm/v1/worker/xpu_worker.py": "dc0aa8e7a0e303e38fdaf2729d878e2c23678be1a2e56fd2d46599cf5181ad11",
    "vllm/v1/worker/xpu_model_runner.py": "07fa0390d28f2b8c3c3c0019eb9c3b126e2397aea268ba47c889f06b423deb23",
    "vllm/compilation/cuda_graph.py": "cbc474f9098386d2eef2e3ff61364c611fbc1338d9c259ad5a24439aa7f06412",
    "vllm/forward_context.py": "985adacc9e7ed2a7695819ac2e2ad9cb264a7d886806d3091ad75bfda7392242",
    "vllm/models/qwen4_exp/amd/model.py": "f7691bbd16bbddb39fc093ff19bfd3e7cabfe3289ae6c6ba18ca9afb918becc8",
    "vllm/models/qwen4_exp/amd/mtp.py": "6cf6feab74788c3e7bb3a6813a102c310113538da6e723af50a9ec32301dba03",
    "vllm/v1/spec_decode/qwen4_exp.py": "ba5b709e30ade8b111569bd0b0934e915cd89872ab6638668b136ed97a7112d1",
    "vllm/v1/spec_decode/eagle.py": "b2b1f7d15117b43108be368756d9c6e9334d9415a070e46178e18bb7c6476378",
    "vllm/v1/spec_decode/llm_base_proposer.py": "e4f3180b0d3c0648ee0ab112fc32bf843bc5dd2da110ae84b64821b1f4798039",
    "vllm/v1/attention/backends/gdn_attn.py": "c65552d9aad86472544033d44ad8a872221a83e6b60ba9918cc049ab0c580c7c"
}
TARGET_NAMES = {"Qwen4ExpForCausalLM", "Qwen4ExpForConditionalGeneration"}


def capture_rendezvous(directory, get_rank, *, clock=time.monotonic,
                       sleep=time.sleep, report=print, budget=600):
    """Host files only. Budget expiry reports and waits; never raises or kills.

    The supervisor releases even a failed resume. Atomic publication prevents
    it from seeing a partially written rank receipt on local ext4.
    """
    directory = Path(directory)
    rank = get_rank()
    if type(rank) is not int or rank not in range(4):
        raise RuntimeError("capture rendezvous requires initialized rank 0..3")
    ready = directory / f"capture-ready-rank-{rank}.json"
    record = {"schema": "a367-census-capture-ready.v1", "rank": rank,
              "pid": os.getpid(), "monotonic": clock()}
    temporary = ready.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, sort_keys=True) + "\n")
    temporary.replace(ready)
    deadline = clock() + budget
    while not (directory / "capture-go").is_file():
        if clock() >= deadline:
            report(f"A367 capture rendezvous rank {rank}: {budget}s wait budget exceeded; "
                   "still waiting for capture-go; no exception or kill", flush=True)
            deadline = clock() + budget
        sleep(.05)


def patch_capture(cls, directory, get_rank):
    original = cls.capture_model
    @wraps(original)
    def capture(self, *args, **kwargs):
        capture_rendezvous(directory, get_rank)
        return original(self, *args, **kwargs)
    cls.capture_model = capture


def patch_eager_warmup(cls, directory, get_rank):
    """Eager skips capture_model; hold after warmup, before readiness RPC returns."""
    original = cls.compile_or_warm_up_model
    @wraps(original)
    def warmup(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if self.model_config.enforce_eager:
            capture_rendezvous(directory, get_rank)
        return result
    cls.compile_or_warm_up_model = warmup


def rows(value):
    """Read shape metadata only; never coerce a tensor or read a scalar."""
    shape = getattr(value, "shape", None)
    if shape is None or len(shape) == 0 or type(shape[0]) is not int:
        return None
    return shape[0] if shape[0] > 0 else None


def call_rows(args, kwargs):
    for key in ("input_ids", "inputs_embeds"):
        if kwargs.get(key) is not None:
            return rows(kwargs[key])
    if args and args[0] is not None:
        return rows(args[0])
    # All pinned target/MTP signatures put positions second. M-RoPE has a
    # leading coordinate axis, so its final dimension is the token count.
    positions = kwargs.get("positions", args[1] if len(args) > 1 else None)
    shape = getattr(positions, "shape", None)
    if shape is not None and len(shape) in (1, 2) and type(shape[-1]) is int:
        return shape[-1] if shape[-1] > 0 else None
    return None


def is_verify(m, context):
    """M=2 alone is insufficient: a short prefill can also have two rows."""
    if m != 2 or context is None:
        return False
    metadata = getattr(context, "attn_metadata", None)
    if not isinstance(metadata, dict):
        return False
    gdn = [v for v in metadata.values() if hasattr(v, "num_spec_decodes")]
    return bool(gdn) and all(
        type(getattr(v, "num_prefills", None)) is int
        and v.num_prefills == 0
        and type(v.num_spec_decodes) is int and v.num_spec_decodes == 1
        and type(getattr(v, "num_spec_decode_tokens", None)) is int
        and v.num_spec_decode_tokens == 2
        for v in gdn
    )


def runnable_phase(obj):
    """Only known model identities; do not guess from arbitrary class names."""
    seen = set()
    for _ in range(5):
        if id(obj) in seen:
            return None
        seen.add(id(obj))
        cls = type(obj)
        if cls.__module__ == "vllm.models.qwen4_exp.amd.model" and cls.__name__ in TARGET_NAMES:
            return "target"
        if cls.__module__ == "vllm.models.qwen4_exp.amd.mtp" and cls.__name__ == "Qwen4ExpMTP":
            return "draft"
        # Only the source-pinned graph wrapper may be traversed. A generic
        # runnable attribute is not proof that an unknown wrapper is transparent.
        if cls.__module__ != "vllm.compilation.cuda_graph" or cls.__name__ != "CUDAGraphWrapper":
            return None
        obj = vars(obj).get("runnable")
        if obj is None:
            return None
    return None


class Marker:
    def __init__(self, active, directory, itt, get_rank, get_context, source_pins):
        self.active = Path(active)
        self.directory = Path(directory)
        self.itt = itt
        self.get_rank = get_rank
        self.get_context = get_context
        self.source_pins = source_pins
        self.local = threading.local()
        self.lock = threading.Lock()
        self.sequence = 0
        self.receipted = False

    @contextmanager
    def scope(self, phase, m, dimension="M"):
        if getattr(self.local, "depth", 0) or not self.active.is_file():
            yield
            return
        if type(m) is not int or m < 1:
            raise RuntimeError("census marker cannot determine row count from metadata")
        if dimension not in {"M", "B"} or (dimension == "B" and phase != "draft"):
            raise RuntimeError("census marker dimension does not match scope")
        rank = self.get_rank()
        if type(rank) is not int or rank not in range(4):
            raise RuntimeError("census marker requires initialized rank 0..3")
        if phase == "target":
            phase = "verify" if is_verify(m, self.get_context()) else "target"
        with self.lock:
            self.sequence += 1
            seq = self.sequence
            if not self.receipted:
                record = {"schema": "a367-census-marker-rank-v1", "rank": rank,
                          "pid": os.getpid(), "source_pins": self.source_pins,
                          "binding": "worker OS PID; Chrome device PID is synthetic"}
                path = self.directory / f"marker-rank-{rank}-pid-{os.getpid()}.json"
                with path.open("x", encoding="utf-8") as handle:
                    json.dump(record, handle, sort_keys=True, indent=2)
                    handle.write("\n")
                self.receipted = True
        name = f"A367|{phase}|{dimension}={m}|seq={seq}"
        self.local.depth = 1
        try:
            self.itt.rangePush(name)
            try:
                yield
            finally:
                self.itt.rangePop()
        finally:
            self.local.depth = 0


def patch_forward(cls, marker, phase):
    original = cls.forward
    @wraps(original)
    def forward(self, *args, **kwargs):
        # Inactive/nested path must not inspect shape or context during capture.
        if getattr(marker.local, "depth", 0) or not marker.active.is_file():
            return original(self, *args, **kwargs)
        with marker.scope(phase, call_rows(args, kwargs)):
            return original(self, *args, **kwargs)
    cls.forward = forward


def patch_graph(cls, marker):
    original = cls.__call__
    @wraps(original)
    def call(self, *args, **kwargs):
        if getattr(marker.local, "depth", 0) or not marker.active.is_file():
            return original(self, *args, **kwargs)
        phase = runnable_phase(self.runnable)
        if phase is None:
            raise RuntimeError("census cannot classify active graph runnable")
        with marker.scope(phase, call_rows(args, kwargs)):
            return original(self, *args, **kwargs)
    cls.__call__ = call


def patch_proposer(cls, marker):
    original = cls.propose
    signature = inspect.signature(original)
    @wraps(original)
    def propose(self, *args, **kwargs):
        if getattr(marker.local, "depth", 0) or not marker.active.is_file():
            return original(self, *args, **kwargs)
        bound = signature.bind(self, *args, **kwargs)
        # next_token_ids has one entry per request, NOT per draft model row.
        # set_inputs_first_pass and padding later determine actual model M.
        # This scope includes all proposer staging, model and sampling work.
        batch_size = rows(bound.arguments.get("next_token_ids"))
        with marker.scope("draft", batch_size, dimension="B"):
            return original(self, *args, **kwargs)
    cls.propose = propose


def verify_pins(root):
    if not SOURCE_PINS:
        raise RuntimeError("census marker source pins absent")
    for relative, expected in SOURCE_PINS.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"census marker source drift: {relative}")


def install():
    """Runtime-only entry, after the unchanged driver cleanup bootstrap."""
    active = Path(os.environ["A367_CENSUS_MARKER_ACTIVE"])
    directory = Path(os.environ["A367_CENSUS_MARKER_DIR"])
    capture_directory = Path(os.environ["A367_CENSUS_CAPTURE_DIR"])
    if not active.is_absolute() or not directory.is_absolute() or not directory.is_dir():
        raise RuntimeError("census marker paths must be absolute, prepared run paths")
    if not capture_directory.is_absolute() or not capture_directory.is_dir():
        raise RuntimeError("census capture path must be absolute, prepared local scratch")
    root = Path(os.environ["PACKET4_SOURCE"])
    verify_pins(root)
    # This is the ITT binding only. It does not activate a PyTorch profiler.
    from torch._C import _itt
    from torch import distributed
    if not _itt.is_available():
        raise RuntimeError("census requires a functioning ITT build")
    from vllm import forward_context
    from vllm.compilation.cuda_graph import CUDAGraphWrapper
    from vllm.models.qwen4_exp.amd.model import Qwen4ExpForCausalLM, Qwen4ExpForConditionalGeneration
    from vllm.models.qwen4_exp.amd.mtp import Qwen4ExpMTP
    from vllm.v1.spec_decode.qwen4_exp import Qwen4ExpMTPProposer
    from vllm.v1.worker.gpu.model_runner import GPUModelRunner
    def get_rank():
        return distributed.get_rank() if distributed.is_initialized() else None
    def get_context():
        return forward_context.get_forward_context() if forward_context.is_forward_context_available() else None
    marker = Marker(active, directory, _itt, get_rank, get_context, SOURCE_PINS)
    # XPUModelRunnerV2 inherits this method unchanged. On the pinned XPU path
    # compile_or_warm_up_model calls it after profile_run and initialize_kv_cache;
    # XPU cannot enter the earlier profile_cudagraph_memory path.
    if os.environ["A367_CENSUS_ARM"] == "eager-census":
        from vllm.v1.worker.gpu_worker import Worker
        patch_eager_warmup(Worker, capture_directory, get_rank)
    else:
        patch_capture(GPUModelRunner, capture_directory, get_rank)
    patch_graph(CUDAGraphWrapper, marker)
    for cls in (Qwen4ExpForCausalLM, Qwen4ExpForConditionalGeneration):
        patch_forward(cls, marker, "target")
    patch_forward(Qwen4ExpMTP, marker, "draft")
    patch_proposer(Qwen4ExpMTPProposer, marker)
    return marker
