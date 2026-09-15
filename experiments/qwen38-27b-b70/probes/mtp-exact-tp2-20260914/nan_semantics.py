#!/usr/bin/env python3
"""NaN-semantics characterization: standard XCCL versus four local add kernels.

No IPC, export, import or control socket. Each rank all-reduces its column of
the ordered-pair fixture with standard XCCL, then runs m0..m3 through
et_add_mode on two LOCAL native allocations on its own device: local holds the
rank's own operand and output holds the other rank's operand, exactly as the
collective kernel sees them. Raw XCCL and mode bits are saved for every element.

Mismatches are data. The worker completes every shape, frees its allocations
after their events complete, destroys the process group and exits 0.
os._exit(70) is kept only for unknown faults (any exception), as in gate.py.
Import and --help do not import torch or initialize a GPU.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import traceback

import nan_analysis as NA

FAULT_EXIT = 70


def save(path, value):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def host_fp16(torch, bits):
    return torch.frombuffer(bytearray(bits.tobytes()), dtype=torch.int16).clone().view(torch.float16)


def bytes_of(torch, t):
    return t.contiguous().view(-1).view(torch.uint8).numpy().tobytes()


def parse_rows(text):
    rows = [int(x) for x in text.split(",")]
    if not rows or any(r not in NA.SHAPES for r in rows) or len(set(rows)) != len(rows):
        raise ValueError("unregistered or duplicate shape")
    return rows


def main(args):
    import torch
    import torch.distributed as dist
    from native import ADD_MODES, Native
    rank, world, local_rank = int(os.environ["RANK"]), int(os.environ["WORLD_SIZE"]), int(os.environ["LOCAL_RANK"])
    if world != 2 or rank not in (0, 1) or local_rank != rank:
        raise ValueError("exactly two local ranks required")
    if not args.admitted_exclusive_gpu_test:
        raise ValueError("run only under exclusive ownership and kernel fault monitor")
    if ADD_MODES != NA.MODE_CODES:
        raise RuntimeError("native/analysis mode table drift")
    rows_list = parse_rows(args.rows)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"rank{rank}-nan-semantics.json"
    receipt = {"rank": rank, "status": "started", "backend": "xccl", "torch": torch.__version__,
               "library_sha256": sha(Path(args.library).read_bytes()), "add_mode_codes": ADD_MODES,
               "fixture_values": [f"{b:04x}" for b in NA.BITS], "pair_period": NA.PERIOD,
               "custom_ipc": False, "group_destroyed": False, "shapes": {}}
    save(path, receipt)
    torch.xpu.set_device(local_rank)
    dist.init_process_group("xccl", timeout=datetime.timedelta(seconds=args.timeout))
    dist.barrier()
    queue = torch.xpu.current_stream().sycl_queue
    native = Native(args.library, queue, args.timeout)
    for rows in rows_list:
        n, size = rows * NA.ELEMENTS_PER_ROW, rows * NA.ELEMENTS_PER_ROW * 2
        own, peer = host_fp16(torch, NA.column(rank, n)), host_fp16(torch, NA.column(1 - rank, n))
        own_raw = bytes_of(torch, own)
        reference = own.to("xpu")
        dist.all_reduce(reference)
        raw = {"xccl": bytes_of(torch, reference.cpu())}
        torch.xpu.synchronize()
        record = {"elements": n, "input_sha256": sha(own_raw), "peer_input_sha256": sha(bytes_of(torch, peer)),
                  "sha256": {}, "input_unchanged": {}, "elements_matching_xccl": {}}
        local = native.pointer("allocate", size)
        output = native.pointer("allocate", size)
        for mode, code in ADD_MODES.items():
            native.copy(local, own.data_ptr(), size)
            native.copy(output, peer.data_ptr(), size)
            native.wait(native.pointer("add_mode", local, output, n, rank, code))
            got = torch.empty(n, dtype=torch.float16)
            native.copy(got.data_ptr(), output, size)
            kept = torch.empty(n, dtype=torch.float16)
            native.copy(kept.data_ptr(), local, size)
            raw[mode] = bytes_of(torch, got)
            record["input_unchanged"][mode] = bytes_of(torch, kept) == own_raw
            record["elements_matching_xccl"][mode] = n - NA.mismatch_count(raw[mode], raw["xccl"])
        # Every copy/add event above completed through native.wait before free.
        native.call("free", queue, output)
        native.call("free", queue, local)
        for arm, data in raw.items():
            (out / f"rank{rank}-rows{rows}-{arm}.bin").write_bytes(data)
            record["sha256"][arm] = sha(data)
        receipt["shapes"][str(rows)] = record
        save(path, receipt)
    dist.barrier()
    dist.destroy_process_group()
    receipt.update(status="completed", group_destroyed=True)
    save(path, receipt)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--rows", default="1,2,512,4096")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--admitted-exclusive-gpu-test", action="store_true")
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        main(args)
    except BaseException:
        # Unknown fault only: no GPU teardown, synchronize or retry. The owner
        # controller watches kernel faults and bounds the container.
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"rank{os.environ.get('RANK', 'unknown')}-FAULT.txt").write_text(traceback.format_exc())
        os._exit(FAULT_EXIT)
