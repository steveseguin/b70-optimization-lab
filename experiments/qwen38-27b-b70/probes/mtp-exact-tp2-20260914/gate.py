#!/usr/bin/env python3
"""Exclusive two-rank operator screen. NOT a server or production communicator.

Launch only under the lane fault monitor after explicit ownership admission.
Import and --help do not import torch or initialize a GPU.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import statistics
import time
import traceback

from native import Native, Collective
from protocol import Channel, exchange_ipc


def fixture(torch, n, rank, kind, repeat):
    i = torch.arange(n, dtype=torch.int64)
    if kind == "varied":
        return (((i * (71 + rank * 4) + repeat * 173) % 65521 - 32760) / 4096).half()
    patterns = {
        "cancel": ([0x3555, 0x7bff, 0x0001, 0x0400], [0xb555, 0xfbff, 0x8001, 0x8400]),
        "signed_zero": ([0, 0x8000, 0, 0x8000], [0, 0, 0x8000, 0x8000]),
        "subnormal": ([1, 0x3ff, 0x8001, 0x83ff], [1, 1, 0x8001, 0x8001]),
        "overflow": ([0x7bff, 0xfbff, 0x7bff, 0x3555], [0x7bff, 0xfbff, 0x3c00, 0x3555]),
        "rounding": ([0x3c00, 0x3c01, 0x3c02, 0xbc01], [0x1000, 0x1000, 0x1000, 0x9000]),
        "nan_inf": ([0x7c00, 0xfc00, 0x7e01, 0xfe02], [0xfc00, 0x7c00, 0x3c00, 0x7e03]),
    }
    bits = torch.tensor(patterns[kind][rank], dtype=torch.uint16)
    return bits[((i + repeat) % len(bits))].view(torch.float16)


def bytes_of(t):
    return t.contiguous().view(-1).view(__import__("torch").uint8).numpy().tobytes()


def main(args):
    import torch
    import torch.distributed as dist
    rank, world = int(os.environ["RANK"]), int(os.environ["WORLD_SIZE"])
    if world != 2 or rank not in (0, 1):
        raise ValueError("exactly two ranks required")
    if not args.admitted_exclusive_gpu_test:
        raise ValueError("run only under exclusive ownership and kernel fault monitor")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    torch.xpu.set_device(int(os.environ["LOCAL_RANK"]))
    dist.init_process_group("xccl", timeout=datetime.timedelta(seconds=args.timeout))
    sock_path = str(out / "control.sock")
    server = None
    if rank == 0:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.settimeout(args.timeout)
        server.bind(sock_path)  # Existing path is a hard refusal, never unlink it.
        os.chmod(sock_path, 0o600)
        server.listen(1)
    dist.barrier()
    if rank == 0:
        sock, _ = server.accept()
        server.close()
    else:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(args.timeout)
        sock.connect(sock_path)
    sock.settimeout(args.timeout)
    channel = Channel(sock, rank, args.timeout)
    queue = torch.xpu.current_stream().sycl_queue
    native = Native(args.library, queue, args.timeout)
    uuid = C.create_string_buffer(16)
    native.call("device_uuid", queue, uuid)
    sock.sendall(uuid.raw)
    peer_uuid = sock.recv(16, socket.MSG_WAITALL)
    if len(peer_uuid) != 16:
        raise ConnectionError("truncated peer UUID")
    native.call("admit_peer", queue, C.create_string_buffer(peer_uuid, 16))
    channel.exchange("READY", peer_access_admitted=True)
    channel.exchange("COPIED", peer_access_admitted=True)
    records = []
    for rows in map(int, args.rows.split(",")):
        if rows not in (1, 2, 512, 4096):
            raise ValueError("unregistered shape")
        n, size = rows * 5120, rows * 5120 * 2
        local = native.pointer("allocate", size)
        output = native.pointer("allocate", size)
        handle = C.create_string_buffer(64)
        native.call("export", queue, local, handle)
        native.call("validate_fd", queue, handle)
        remote_handle, remote_fd = exchange_ipc(sock, handle.raw)
        remote_buffer = C.create_string_buffer(remote_handle, 64)
        native.call("validate_fd", queue, remote_buffer)
        peer = native.pointer("open", remote_buffer)
        collective = Collective(native, channel, n, local, peer, output)
        for kind in ["varied", "cancel", "signed_zero", "subnormal", "overflow", "rounding", "nan_inf"]:
            for repeat in range(2):
                cpu = fixture(torch, n, rank, kind, repeat)
                original = bytes_of(cpu)
                native.copy(local, cpu.data_ptr(), size)
                reference_input = cpu.to("xpu")
                reference = reference_input.clone()
                dist.all_reduce(reference)
                reference_bits = reference.cpu().view(torch.int16)
                collective.run()
                got = torch.empty(n, dtype=torch.float16)
                native.copy(got.data_ptr(), output, size)
                preserved = torch.empty_like(cpu)
                native.copy(preserved.data_ptr(), local, size)
                raw, ref = bytes_of(got), bytes_of(reference_bits)
                same = raw == ref and bytes_of(preserved) == original
                prefix = f"rank{rank}-rows{rows}-{kind}-{repeat}"
                (out / f"{prefix}.candidate.bin").write_bytes(raw)
                (out / f"{prefix}.xccl.bin").write_bytes(ref)
                record = {"rows": rows, "kind": kind, "repeat": repeat, "exact": same,
                          "input_sha256": hashlib.sha256(original).hexdigest(),
                          "candidate_sha256": hashlib.sha256(raw).hexdigest(),
                          "xccl_sha256": hashlib.sha256(ref).hexdigest(),
                          "input_unchanged": bytes_of(preserved) == original}
                records.append(record)
                (out / f"rank{rank}-quality.json").write_text(json.dumps(records, indent=2) + "\n")
                # Communicate the verdict before further GPU submission. A rank
                # mismatch poisons both peers; do not let the passing rank advance.
                verdict = {"quality_passed": same, "rows": rows, "kind": kind,
                           "repeat": repeat, "candidate_sha256": record["candidate_sha256"],
                           "xccl_sha256": record["xccl_sha256"]}
                channel.exchange("READY", **verdict)
                channel.exchange("COPIED", **verdict)
                if not same:
                    raise AssertionError(f"{prefix}: XCCL bit equality/input lifetime failed")
        timings = []
        for block in range(args.blocks):
            # Every block changes both messages. Setup copies are excluded for
            # BOTH algorithms, with persistent input and output allocations.
            cpu = fixture(torch, n, rank, "varied", 100 + block)
            native.copy(local, cpu.data_ptr(), size)
            reference_input = cpu.to("xpu")
            torch.xpu.synchronize()
            order = ["xccl", "candidate", "candidate", "xccl"] if block % 2 == 0 else ["candidate", "xccl", "xccl", "candidate"]
            for arm in order:
                channel.exchange("READY", timing_arm=arm, block=block)
                channel.exchange("COPIED", timing_arm=arm, block=block)
                start = time.perf_counter_ns()
                for _ in range(args.iterations):
                    if arm == "candidate":
                        collective.run()
                    else:
                        result = reference_input.clone()
                        work = dist.all_reduce(result, async_op=True)
                        work.wait()
                        torch.xpu.synchronize()
                elapsed = (time.perf_counter_ns() - start) / args.iterations
                timings.append({"block": block, "arm": arm, "ns_per_call": elapsed})
        (out / f"rank{rank}-rows{rows}-timing.json").write_text(json.dumps(timings, indent=2) + "\n")
        channel.exchange("READY", retiring_rows=rows)
        channel.exchange("COPIED", retiring_rows=rows)
        native.call("close", queue, peer)
        os.close(remote_fd)
        # Both importers close BEFORE either exporter returns its IPC handle or
        # frees the underlying allocation. Explicit two-phase lifetime barrier.
        channel.exchange("READY", importers_closed=rows)
        channel.exchange("COPIED", importers_closed=rows)
        native.call("put_export", queue, handle)
        native.call("free", queue, output)
        native.call("free", queue, local)
    sock.close()
    dist.destroy_process_group()
    (out / f"rank{rank}-DONE.json").write_text(json.dumps({"status": "operator-screen-completed", "quality_cases": len(records), "runtime_qualified": False, "torch": torch.__version__}) + "\n")
    if rank == 0:
        os.unlink(sock_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--rows", default="1,2,512,4096")
    p.add_argument("--blocks", type=int, default=5)
    p.add_argument("--iterations", type=int, default=12)
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--admitted-exclusive-gpu-test", action="store_true")
    args = p.parse_args()
    try:
        main(args)
    except BaseException:
        # In fault cases do not call GPU destruction, synchronize, collective
        # teardown, or automatic retries. The external monitor owns termination.
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"rank{os.environ.get('RANK', 'unknown')}-FAULT.txt").write_text(traceback.format_exc())
        os._exit(70)
