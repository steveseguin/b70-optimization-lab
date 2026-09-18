#!/usr/bin/env python3
"""Measure the HOST-memory footprint of `run_h3_t2v.py`'s loaders, on CPU, with a byte budget.

    /mnt/fast-ai/venvs/minimax-h3-cpu/bin/python profile-encoder-load.py [--denoiser]
        [--loader pread|mmap] [--max-bytes GIB] [--max-tensors N] [--every N] [--no-force-copy]
        [--drop-pagecache] [--json OUT] [--min-avail-mib MIB] [--no-watchdog]

Why
---
Precondition 1 of the rerun list in `notes/2026-09-18-standup-prep.md`: the 2026-09-18 03:05 first
light died in phase `encode.load`, and the dry run's "resident bytes 27.141 GB" is a DEVICE-side
figure that says nothing about what the loader holds in HOST memory. This measures that, and only
that, without a GPU, without diffusers/transformers, and without ever approaching the host limit.

*** RUN IT UNDER THE WATCHDOG. ***
This script arms `mem-watchdog.sh` on its own pid by default (min available 2048 MiB), in its own
process group, so a surprise -- a loader that holds far more than expected -- kills this process
and nothing else. `--no-watchdog` disables that and is only for a run already inside a watchdog
(set `B70_WATCHDOG=1` in that case, and the arming is skipped with a note). Do not disable it to
"see how far it gets": the 2026-09-17 incident is exactly what that produces.

What it reproduces
------------------
The two loops of `run_h3_t2v.py`, in their real order, with their real per-tensor conversions:

* `_build_text_encoder` (default): every non-quantized tensor of the INT8 ConvRot text encoder in
  safetensors header order (`.comfy_quant` / `.weight_scale` skipped, quantized base weights
  skipped), then `sorted(quantized)` with `bias -> bfloat16`, `weight` as stored,
  `weight_scale -> float32` -- the same three-`get_tensor` order the real loader uses.
* `load_sharded_transformer` (`--denoiser`): `adaln_t_table -> float32`, then `build_remap()`
  order with the same row slice, the same SwiGLU half swap, the same `target_dtype()` and the same
  `.contiguous()`.

Which loader
------------
`--loader` (default: whatever `B70_H3_LOADER` says, which itself defaults to `pread`) selects the
same two tensor readers `run_h3_t2v.py` uses, through the same `open_tensor_reader`:

* `pread` -- the header is parsed once and each tensor's byte range is `os.pread`-ed into a private
  buffer, which is then released with `posix_fadvise(DONTNEED)`.  Nothing is mapped, so RssFile
  stays flat and the host cost is one tensor at a time.
* `mmap` -- the old `safetensors.safe_open` path.  Sessions 6 and 7 measured it: RssAnon peaked
  where a streaming loader should (1.661 GiB encoder / 0.499 GiB denoiser) but RssFile tracked
  every byte touched -- 6.291 GiB at a 6 GiB budget, 6.352 GiB with `--drop-pagecache`, which is
  to say the drop did nothing, because `posix_fadvise` cannot evict a page the handle still maps.

Two honest differences from the real load, both of which make this an UPPER bound on host bytes:

1. There is no model skeleton, so the real loader's `if name not in live: continue` cannot be
   evaluated; every checkpoint tensor is processed. A real load can only touch fewer.
2. The real `.to(device="xpu:N")` allocates on the card and reads every source byte. On CPU,
   `.to(device="cpu")` is a no-op alias that touches nothing, which on the *mmap* loader would
   measure zero -- so on that loader each tensor is materialized with `.clone()` (`--force-copy`,
   the default): one real read of the mapped pages plus one real host allocation of the tensor's
   bytes, the closest CPU stand-in for the host side of a host-to-device copy. On the *pread*
   loader the read buffer already IS a host allocation of exactly those bytes, so no clone is
   taken: cloning there would double-count a cost the real load does not pay. `--no-force-copy`
   shows the do-nothing baseline and is only useful to prove that point.

Every tensor is dropped (`del`) immediately after its conversion, which is what the real loader
does too, so what remains is the loader's *transient* host footprint plus the mmap page cache.

What it reports
---------------
`VmRSS`, `RssAnon` and `RssFile` from /proc/self/status, sampled every `--every` tensors (default
25) and at every new high-water mark; `VmHWM` and `ru_maxrss` at the end; the low-water mark of
`MemAvailable`; and the largest single tensor seen. RssAnon is the loader's own memory. RssFile is
the file-backed page cache mapped into this process -- reclaimable, but reclaiming it is what
generates the memory PRESSURE that systemd-oomd kills on, so it is reported separately and it is
the number the go/no-go rule in `notes/2026-09-18-first-light-plan.md` adds to RssAnon. On the
`pread` loader nothing is mapped, so RssFile should stay flat at the interpreter's own shared
objects (~0.07 GiB) no matter how many bytes are read; if it climbs with the bytes read, something
has re-introduced a mapping.

`--drop-pagecache` additionally calls `posix_fadvise(POSIX_FADV_DONTNEED)` on the whole checkpoint
every `--every` tensors and reports what that does to RssFile: this is the A/B behind the
`B70_H3_DROP_PAGECACHE=1` option in `run_h3_t2v.py`. Session 7 is the answer for the mmap loader --
it does nothing, because a mapped page cannot be evicted. The `pread` loader releases each tensor's
range as it goes and does not need it.

Budget
------
Stops at the first of `--max-bytes` (default 6 GiB of tensor bytes), `--max-tensors` /
`B70_PROFILE_MAX_TENSORS`, or the end of the checkpoint. The default budget is a fraction of the
27 GB encoder on purpose: the footprint of a streaming loader is per-tensor, so the shape of the
curve over 6 GiB answers the question, and a full pass is not needed to get the peak.

No XPU: this module never imports `torch.xpu` and never creates a device tensor. It imports
cleanly on a host with no XPU runtime at all.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import resource
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
RUNNER = HERE / "run_h3_t2v.py"
WATCHDOG = HERE / "mem-watchdog.sh"

GIB = 2**30


# ---------------------------------------------------------------------------------------------
# Host memory sampling
# ---------------------------------------------------------------------------------------------

_STATUS_FIELDS = ("VmRSS", "VmHWM", "RssAnon", "RssFile", "RssShmem", "VmSwap")


def proc_status() -> dict[str, int]:
    """The interesting /proc/self/status fields, in bytes."""
    out: dict[str, int] = {}
    with open("/proc/self/status") as fh:
        for line in fh:
            key, _, rest = line.partition(":")
            if key in _STATUS_FIELDS:
                out[key] = int(rest.split()[0]) * 1024
    return out


def mem_available() -> int:
    with open("/proc/meminfo") as fh:
        for line in fh:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    return 0


def pressure_some_avg10() -> float:
    try:
        with open("/proc/pressure/memory") as fh:
            for line in fh:
                if line.startswith("some"):
                    for field in line.split():
                        if field.startswith("avg10="):
                            return float(field.split("=", 1)[1])
    except OSError:
        pass
    return 0.0


def ru_maxrss_bytes() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024  # KiB on Linux


def gb(n: int) -> str:
    return f"{n / GIB:7.3f} GiB"


class Sampler:
    """Tracks the high-water marks and prints a line every `every` tensors."""

    def __init__(self, every: int, label: str):
        self.every = max(1, every)
        self.label = label
        self.peak: dict[str, int] = {k: 0 for k in _STATUS_FIELDS}
        self.peak_sum_rss_anon_file = 0
        self.low_avail = mem_available()
        self.peak_pressure = pressure_some_avg10()
        self.rows: list[dict] = []
        self.t0 = time.perf_counter()

    def peak_only(self) -> None:
        """Update the high-water marks without recording a row.

        Called while the converted tensor is still ALIVE, which is the transient peak the
        after-the-`del` sample cannot see. VmHWM corroborates it.
        """
        st = proc_status()
        for key, value in st.items():
            if value > self.peak.get(key, 0):
                self.peak[key] = value
        self.peak_sum_rss_anon_file = max(
            self.peak_sum_rss_anon_file, st.get("RssAnon", 0) + st.get("RssFile", 0)
        )
        self.low_avail = min(self.low_avail, mem_available())
        self.peak_pressure = max(self.peak_pressure, pressure_some_avg10())

    def sample(self, index: int, done_bytes: int, force: bool = False) -> dict[str, int]:
        st = proc_status()
        new_high = False
        for key, value in st.items():
            if value > self.peak.get(key, 0):
                self.peak[key] = value
                if key in ("VmRSS", "RssAnon", "RssFile"):
                    new_high = True
        combined = st.get("RssAnon", 0) + st.get("RssFile", 0)
        self.peak_sum_rss_anon_file = max(self.peak_sum_rss_anon_file, combined)
        avail = mem_available()
        self.low_avail = min(self.low_avail, avail)
        self.peak_pressure = max(self.peak_pressure, pressure_some_avg10())

        if force or new_high or index % self.every == 0:
            row = {
                "tensor_index": index,
                "tensor_bytes_done": done_bytes,
                "elapsed_s": round(time.perf_counter() - self.t0, 3),
                "VmRSS": st.get("VmRSS", 0),
                "RssAnon": st.get("RssAnon", 0),
                "RssFile": st.get("RssFile", 0),
                "MemAvailable": avail,
            }
            self.rows.append(row)
            if force or index % self.every == 0:
                print(
                    f"  [{self.label}] {index:5d} tensors  read {gb(done_bytes)}   "
                    f"VmRSS {gb(st.get('VmRSS', 0))}  anon {gb(st.get('RssAnon', 0))}  "
                    f"file {gb(st.get('RssFile', 0))}   MemAvailable {gb(avail)}",
                    flush=True,
                )
        return st


# ---------------------------------------------------------------------------------------------
# The runner's own code, imported rather than copied
# ---------------------------------------------------------------------------------------------


def load_runner():
    """Import run_h3_t2v.py as a module. It has no import-time side effects and no torch import."""
    spec = importlib.util.spec_from_file_location("run_h3_t2v", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec: `@dataclasses.dataclass` resolves annotations through
    # `sys.modules[cls.__module__]` and raises if the module is not there yet.
    sys.modules["run_h3_t2v"] = module
    spec.loader.exec_module(module)
    return module


def shares_storage(a, b) -> bool:
    """True when `a` is still a view on `b`'s storage (i.e. no copy happened)."""
    try:
        return a.untyped_storage().data_ptr() == b.untyped_storage().data_ptr()
    except Exception:  # very old torch
        return a.data_ptr() == b.data_ptr()


def drop_pagecache(path: pathlib.Path) -> None:
    """Ask the kernel to drop this file's page cache. Advisory: mapped pages may survive."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------------------------
# The two loops
# ---------------------------------------------------------------------------------------------


def profile_encoder(args, rt, sampler: Sampler) -> dict:
    """Reproduce `run_h3_t2v.py::_build_text_encoder`'s safe_open order, to CPU."""
    import torch

    path = rt.INT8_TEXT_ENCODER
    header = rt.read_header(path)
    quantized = {k[: -len(".comfy_quant")] for k in header if k.endswith(".comfy_quant")}
    print(f"encoder: {path}")
    print(f"  {len(header)} header entries, {len(quantized)} quantized Linears, loader {args.loader}")

    done = 0
    count = 0
    largest = {"name": None, "bytes": 0, "dtype": None, "shape": None}

    def take(key: str, dtype=None):
        """One `get_tensor(...).to(...)` exactly as the loader does it, then drop the tensor."""
        nonlocal done, count, largest
        src = fh.get_tensor(key)  # a private pread buffer, or a view on the mapping
        nbytes = src.numel() * src.element_size()
        shape = tuple(src.shape)
        dt = str(src.dtype)
        # The real loader's `.to(device="xpu:N"[, dtype=...])`. A dtype change allocates and reads
        # every source byte; a same-dtype `.to("cpu")` is an alias that touches nothing, so on the
        # mmap loader that case is materialized with clone() (see the module docstring). On pread
        # the buffer is already the host allocation, so no clone.
        t = src.to(device="cpu", dtype=dtype) if dtype is not None else src.to(device="cpu")
        if args.force_copy and fh.backing == "mmap" and shares_storage(t, src):
            t = t.clone()
        out_bytes = t.numel() * t.element_size()
        sampler.peak_only()  # while the converted tensor is still alive
        del t, src
        fh.release(key)
        done += nbytes
        count += 1
        if nbytes > largest["bytes"]:
            largest = {"name": key, "bytes": nbytes, "dtype": dt, "shape": shape,
                       "converted_bytes": out_bytes}
        sampler.sample(count, done)
        if args.drop_pagecache and count % sampler.every == 0:
            drop_pagecache(path)
        return count >= args.max_tensors or done >= args.max_bytes

    stop = False
    with rt.open_tensor_reader(path, header, loader=args.loader) as fh:
        # 1. Plain tensors, in header order (the loader's `for key in header`).
        for key in header:
            if key.endswith((".comfy_quant", ".weight_scale")):
                continue
            base = key[: -len(".weight")] if key.endswith(".weight") else None
            if base is not None and base in quantized:
                continue
            if take(key):
                stop = True
                break

        # 2. Quantized Linears: bias -> bf16, weight as stored, scale -> f32.
        if not stop:
            for base in sorted(quantized):
                if base + ".bias" in header and take(base + ".bias", torch.bfloat16):
                    stop = True
                    break
                if take(base + ".weight"):
                    stop = True
                    break
                if take(base + ".weight_scale", torch.float32):
                    stop = True
                    break

    sampler.sample(count, done, force=True)
    return {"loop": "encoder", "file": str(path), "tensors": count, "bytes": done,
            "largest_tensor": largest, "stopped_early": stop}


def profile_denoiser(args, rt, sampler: Sampler) -> dict:
    """Reproduce `run_h3_t2v.py::load_sharded_transformer`'s stream loop, to CPU."""
    import torch

    path = rt.PRUNED_DENOISER
    header = rt.read_header(path)
    config = json.loads(rt.TRANSFORMER_CONFIG.read_text())
    remap = rt.build_remap(config["num_layers"], config["num_refiner_layers"])
    print(f"denoiser: {path}")
    print(f"  {len(remap)} diffusers parameters from the remap, adaln_dtype={args.adaln_dtype}, "
          f"loader {args.loader}")

    done = 0
    count = 0
    largest = {"name": None, "bytes": 0, "dtype": None, "shape": None}

    with rt.open_tensor_reader(path, header, loader=args.loader) as fh:
        table = fh.get_tensor("adaln_t_table").to(device="cpu", dtype=torch.float32)
        done += table.numel() * table.element_size()
        count += 1
        sampler.peak_only()
        del table
        fh.release("adaln_t_table")
        sampler.sample(count, done)

        stop = False
        for name, src in remap.items():
            # The real loader asks the reader for the row slice, so the pread path reads only
            # those rows; the mmap path slices the view, as it always did.
            raw = fh.get_tensor(src.key, src.row_slice)
            nbytes = raw.numel() * raw.element_size()
            shape = tuple(raw.shape)
            dt = str(raw.dtype)
            t = raw
            if src.swap_halves:
                half = t.shape[0] // 2
                t = torch.cat((t[half:], t[: half]), dim=0)
            t = t.to(device="cpu", dtype=rt.target_dtype(name, args.adaln_dtype)).contiguous()
            if args.force_copy and fh.backing == "mmap" and shares_storage(t, raw):
                t = t.clone()
            out_bytes = t.numel() * t.element_size()
            sampler.peak_only()  # while the converted tensor is still alive
            del t, raw
            fh.release(src.key, src.row_slice)
            done += nbytes
            count += 1
            if nbytes > largest["bytes"]:
                largest = {"name": src.key, "bytes": nbytes, "dtype": dt, "shape": shape,
                           "converted_bytes": out_bytes}
            sampler.sample(count, done)
            if args.drop_pagecache and count % sampler.every == 0:
                drop_pagecache(path)
            if count >= args.max_tensors or done >= args.max_bytes:
                stop = True
                break

    sampler.sample(count, done, force=True)
    return {"loop": "denoiser", "file": str(path), "tensors": count, "bytes": done,
            "largest_tensor": largest, "stopped_early": stop}


# ---------------------------------------------------------------------------------------------
# Watchdog arming
# ---------------------------------------------------------------------------------------------


def arm_watchdog(args) -> subprocess.Popen | None:
    """Start mem-watchdog.sh on our own pid, in our own process group, so its group kill is ours."""
    if os.environ.get("B70_WATCHDOG") == "1":
        print("watchdog: already inside one (B70_WATCHDOG=1); not arming a second")
        return None
    if not args.watchdog:
        print("watchdog: DISABLED by --no-watchdog -- this is not how this script should be run")
        return None
    if not WATCHDOG.exists():
        raise SystemExit(f"{WATCHDOG} is missing; it is not optional (see the module docstring)")
    try:
        os.setpgrp()  # our own process group: the watchdog's group kill then hits only us
    except OSError:
        pass
    log = args.watchdog_log or (pathlib.Path(args.json).with_suffix(".watchdog.log") if args.json
                                else pathlib.Path("/tmp/h3-profile-watchdog.log"))
    proc = subprocess.Popen(
        [str(WATCHDOG), str(os.getpid()), str(args.min_avail_mib), str(log)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    print(f"watchdog: armed on pid {os.getpid()}, min available {args.min_avail_mib} MiB, log {log}")
    return proc


# ---------------------------------------------------------------------------------------------


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="CPU-only host-memory profile of the MiniMax-H3 loaders (run under the watchdog).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--denoiser", action="store_true",
                   help="profile the pruned BF16 denoiser split loop instead of the text encoder")
    p.add_argument("--loader", choices=("pread", "mmap"),
                   default=os.environ.get("B70_H3_LOADER", "pread").strip().lower(),
                   help="which run_h3_t2v.py tensor reader to profile (env B70_H3_LOADER)")
    p.add_argument("--max-bytes", type=float, default=6.0, metavar="GIB",
                   help="stop after this many GiB of tensor bytes have been read")
    p.add_argument("--max-tensors", type=int,
                   default=int(os.environ.get("B70_PROFILE_MAX_TENSORS", 0)) or 10**9,
                   help="stop after this many tensors (env B70_PROFILE_MAX_TENSORS)")
    p.add_argument("--every", type=int, default=25, help="sample/print every N tensors")
    p.add_argument("--no-force-copy", dest="force_copy", action="store_false",
                   help="do NOT materialize each tensor; measures the do-nothing baseline only")
    p.add_argument("--drop-pagecache", action="store_true",
                   help="posix_fadvise(DONTNEED) the checkpoint every --every tensors")
    p.add_argument("--adaln-dtype", choices=("bf16", "fp32"), default="bf16",
                   help="denoiser only: the AdaLN projection dtype policy, as in run_h3_t2v.py")
    p.add_argument("--json", help="write the full sample series and summary here")
    p.add_argument("--min-avail-mib", type=int, default=2048, help="watchdog floor on MemAvailable")
    p.add_argument("--watchdog-log", help="watchdog logfile (default: beside --json)")
    p.add_argument("--no-watchdog", dest="watchdog", action="store_false",
                   help="do not arm mem-watchdog.sh (only when already inside one)")
    args = p.parse_args(argv)
    args.max_bytes = int(args.max_bytes * GIB)
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    watchdog = arm_watchdog(args)

    rt = load_runner()
    label = "denoiser" if args.denoiser else "encoder"
    print(f"profile: {label} loop, loader {args.loader}, CPU only, budget {gb(args.max_bytes)} / "
          f"{args.max_tensors} tensors, force_copy={args.force_copy}, "
          f"drop_pagecache={args.drop_pagecache}")
    start = proc_status()
    print(f"  at start: VmRSS {gb(start.get('VmRSS', 0))}  MemAvailable {gb(mem_available())}")

    sampler = Sampler(args.every, label)
    t0 = time.perf_counter()
    result = profile_denoiser(args, rt, sampler) if args.denoiser else profile_encoder(args, rt, sampler)
    elapsed = time.perf_counter() - t0

    final = proc_status()
    summary = {
        "loop": result["loop"],
        "loader": args.loader,
        "file": result["file"],
        "tensors_processed": result["tensors"],
        "tensor_bytes_read": result["bytes"],
        "stopped_early": result["stopped_early"],
        "elapsed_seconds": round(elapsed, 2),
        "force_copy": args.force_copy,
        "drop_pagecache": args.drop_pagecache,
        "peak": {k: sampler.peak.get(k, 0) for k in _STATUS_FIELDS},
        "peak_rss_anon_plus_file": sampler.peak_sum_rss_anon_file,
        "go_no_go_bytes": max(sampler.peak_sum_rss_anon_file, proc_status().get("VmHWM", 0)),
        "vm_hwm": final.get("VmHWM", 0),
        "ru_maxrss": ru_maxrss_bytes(),
        "mem_available_low": sampler.low_avail,
        "pressure_some_avg10_peak": sampler.peak_pressure,
        "largest_tensor": result["largest_tensor"],
    }

    print()
    print("=" * 92)
    print(f"{label} loop, loader {args.loader}: {result['tensors']} tensors, "
          f"{gb(result['bytes'])} of tensor bytes read in {elapsed:.1f} s"
          + ("  (stopped at the budget)" if result["stopped_early"] else ""))
    print(f"  peak VmRSS          {gb(sampler.peak.get('VmRSS', 0))}")
    print(f"  peak RssAnon        {gb(sampler.peak.get('RssAnon', 0))}   (the loader's own memory)")
    print(f"  peak RssFile        {gb(sampler.peak.get('RssFile', 0))}   "
          + ("(mapped page cache, reclaimable -- and what reclaim pressure oomd kills on)"
             if args.loader == "mmap" else "(no mapping on the pread loader; expect this flat)"))
    go_no_go = max(sampler.peak_sum_rss_anon_file, final.get("VmHWM", 0))
    print(f"  peak anon+file      {gb(sampler.peak_sum_rss_anon_file)}   (sampled in flight)")
    print(f"  GO/NO-GO NUMBER     {gb(go_no_go)}   = max(peak anon+file, VmHWM)")
    print(f"  VmHWM / ru_maxrss   {gb(final.get('VmHWM', 0))} / {gb(ru_maxrss_bytes())}")
    print(f"  MemAvailable low    {gb(sampler.low_avail)}   peak some avg10 {sampler.peak_pressure:.2f}")
    lt = result["largest_tensor"]
    if lt["name"]:
        print(f"  largest tensor      {lt['name']}  {lt['shape']} {lt['dtype']}  "
              f"{lt['bytes'] / 1e6:.1f} MB stored -> {lt.get('converted_bytes', 0) / 1e6:.1f} MB converted")
    print("=" * 92)

    if args.json:
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"summary": summary, "samples": sampler.rows}, indent=2))
        print(f"wrote {out}")

    if watchdog is not None and watchdog.poll() is None:
        watchdog.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
