#!/usr/bin/env python3
"""Exclusive two-rank operator screen. NOT a server or production communicator.

Launch only under the lane fault monitor after explicit ownership admission.
Import and --help do not import torch or initialize a GPU.

Stage 05 (2026-09-15): --add-mode selects the et_add_mode formulation chosen by
nan-semantics-01. A mutually acknowledged quality mismatch retires peer
mappings cooperatively (quality_retirement.py), destroys the process group,
writes a receipt and exits 2. os._exit(70) remains only for unknown faults.
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

from native import ADD_MODES, Native, Collective
from protocol import Channel, exchange_ipc
from quality_retirement import retire_completed_allocations
import nan_analysis

KINDS = ("varied", "cancel", "signed_zero", "subnormal", "overflow", "rounding", "nan_inf", "nan_matrix")
PATTERNS = {
    "cancel": ([0x3555, 0x7bff, 0x0001, 0x0400], [0xb555, 0xfbff, 0x8001, 0x8400]),
    "signed_zero": ([0, 0x8000, 0, 0x8000], [0, 0, 0x8000, 0x8000]),
    "subnormal": ([1, 0x3ff, 0x8001, 0x83ff], [1, 1, 0x8001, 0x8001]),
    "overflow": ([0x7bff, 0xfbff, 0x7bff, 0x3555], [0x7bff, 0xfbff, 0x3c00, 0x3555]),
    "rounding": ([0x3c00, 0x3c01, 0x3c02, 0xbc01], [0x1000, 0x1000, 0x1000, 0x9000]),
    "nan_inf": ([0x7c00, 0xfc00, 0x7e01, 0xfe02], [0xfc00, 0x7c00, 0x3c00, 0x7e03]),
    # Postmortem requirement: NaNs in both operand positions, both signs,
    # quiet/signaling and varied payloads, against each other and finite/inf/zero.
    "nan_matrix": tuple([pair[r] for pair in nan_analysis.PAIRS] for r in (0, 1)),
}
QUALITY_EXIT = 2
FAULT_EXIT = 70


class QualityRejected(Exception):
    pass


def outputs_equal(raw, ref, rule):
    """bit-exact: every bit. nan-class (user decision 2026-09-15): any two NaNs equal, all else bit-exact."""
    if rule == "bit-exact":
        return raw == ref
    if rule == "nan-class":
        return nan_analysis.class_mismatch_count(raw, ref) == 0
    raise ValueError("unknown NaN comparison rule")


def fixture(torch, n, rank, kind, repeat):
    i = torch.arange(n, dtype=torch.int64)
    if kind == "varied":
        return (((i * (71 + rank * 4) + repeat * 173) % 65521 - 32760) / 4096).half()
    bits = torch.tensor(PATTERNS[kind][rank], dtype=torch.uint16)
    return bits[((i + repeat) % len(bits))].view(torch.float16)


def bytes_of(t):
    return t.contiguous().view(-1).view(__import__("torch").uint8).numpy().tobytes()


def reject_quality(torch, dist, native, channel, sock, queue, peer, remote_fd, handle, output, local, rows, prefix):
    """Mutually acknowledged mismatch: every candidate event completed, verdict frames matched.

    Drain the current queue (XCCL reference and host copies) without submitting
    work, then close imports, acknowledge, return exports, free, and tear down.
    Any failure here propagates to the unknown-fault path.
    """
    torch.xpu.synchronize()
    retire_completed_allocations(native, channel, queue, peer, remote_fd, handle, output, local, rows,
                                 completed_and_agreed=True)
    sock.close()
    dist.destroy_process_group()
    raise QualityRejected(f"{prefix}: quality gate rejected")


def main(args):
    import torch
    import torch.distributed as dist
    rank, world = int(os.environ["RANK"]), int(os.environ["WORLD_SIZE"])
    if world != 2 or rank not in (0, 1):
        raise ValueError("exactly two ranks required")
    if not args.admitted_exclusive_gpu_test:
        raise ValueError("run only under exclusive ownership and kernel fault monitor")
    if args.add_mode not in ADD_MODES:
        raise ValueError("explicit --add-mode required")
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
    channel.exchange("READY", peer_access_admitted=True, add_mode=args.add_mode, nan_rule=args.nan_rule)
    channel.exchange("COPIED", peer_access_admitted=True, add_mode=args.add_mode, nan_rule=args.nan_rule)
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
        # validate_fd is an EXPORT-map query, not a receiver-import API. The
        # exporter still passed it above; SCM_RIGHTS/fstat validate the received
        # descriptor, and zeMemOpenIpcHandle performs actual driver admission.
        peer = native.pointer("open", remote_buffer)
        collective = Collective(native, channel, n, local, peer, output, add_mode=args.add_mode)
        for kind in KINDS:
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
                bit_exact = raw == ref
                same = outputs_equal(raw, ref, args.nan_rule) and bytes_of(preserved) == original
                prefix = f"rank{rank}-rows{rows}-{kind}-{repeat}"
                (out / f"{prefix}.candidate.bin").write_bytes(raw)
                (out / f"{prefix}.xccl.bin").write_bytes(ref)
                record = {"rows": rows, "kind": kind, "repeat": repeat, "exact": same, "add_mode": args.add_mode,
                          "nan_rule": args.nan_rule, "bit_exact": bit_exact,
                          "input_sha256": hashlib.sha256(original).hexdigest(),
                          "candidate_sha256": hashlib.sha256(raw).hexdigest(),
                          "xccl_sha256": hashlib.sha256(ref).hexdigest(),
                          "input_unchanged": bytes_of(preserved) == original}
                records.append(record)
                (out / f"rank{rank}-quality.json").write_text(json.dumps(records, indent=2) + "\n")
                # Communicate the verdict before further GPU submission. A rank
                # mismatch poisons both peers; do not let the passing rank advance.
                verdict = {"quality_passed": same, "nan_rule": args.nan_rule, "rows": rows, "kind": kind,
                           "repeat": repeat, "candidate_sha256": record["candidate_sha256"],
                           "xccl_sha256": record["xccl_sha256"]}
                channel.exchange("READY", **verdict)
                channel.exchange("COPIED", **verdict)
                if not same:
                    # Identical verdict frames on both ranks: both take this path.
                    reject_quality(torch, dist, native, channel, sock, queue, peer, remote_fd,
                                   handle, output, local, rows, prefix)
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
        # Both importers close BEFORE either exporter returns its IPC handle or
        # frees the underlying allocation. Explicit two-phase lifetime barrier.
        retire_completed_allocations(native, channel, queue, peer, remote_fd, handle, output, local, rows,
                                     completed_and_agreed=True)
    sock.close()
    dist.destroy_process_group()
    (out / f"rank{rank}-DONE.json").write_text(json.dumps({"status": "operator-screen-completed", "quality_cases": len(records), "add_mode": args.add_mode, "nan_rule": args.nan_rule, "runtime_qualified": False, "torch": torch.__version__}) + "\n")
    if rank == 0:
        os.unlink(sock_path)


def run(args, main_fn=main, hard_exit=os._exit):
    """Returns the process exit code; unknown faults never return."""
    rank = os.environ.get("RANK", "unknown")
    try:
        main_fn(args)
    except QualityRejected as exc:
        out = Path(args.out)
        (out / f"rank{rank}-QUALITY-REJECTED.json").write_text(json.dumps({
            "rank": rank, "error": str(exc), "add_mode": args.add_mode, "imports_retired": True,
            "exporter_storage_released_after_peer_ack": True, "process_group_destroyed": True,
            "os_exit": False}, indent=2) + "\n")
        if rank == "0":
            (out / "control.sock").unlink(missing_ok=True)
        return QUALITY_EXIT  # Normal interpreter exit; no new GPU work or restart.
    except BaseException:
        # In fault cases do not call GPU destruction, synchronize, collective
        # teardown, or automatic retries. The external monitor owns termination.
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"rank{rank}-FAULT.txt").write_text(traceback.format_exc())
        hard_exit(FAULT_EXIT)
    return 0


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--rows", default="1,2,512,4096")
    p.add_argument("--blocks", type=int, default=5)
    p.add_argument("--iterations", type=int, default=12)
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--add-mode", choices=sorted(ADD_MODES), required=True)
    p.add_argument("--nan-rule", choices=nan_analysis.RULES, default="bit-exact")
    p.add_argument("--admitted-exclusive-gpu-test", action="store_true")
    return p


if __name__ == "__main__":
    raise SystemExit(run(parser().parse_args()))
