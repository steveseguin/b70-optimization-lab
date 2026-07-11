#!/usr/bin/env python3
import argparse
import array
import os
import socket
import struct
import time

import torch
import torch.distributed as dist

import qwen27_esimd_allreduce as ext


def signed_ptr(ptr: int) -> int:
    return ptr - (1 << 64) if ptr >= (1 << 63) else ptr


def share_rank0_ipc_event_handle(
    local_hex: str | None, rank: int
) -> tuple[str | None, int]:
    """Share rank 0's fd-backed Level Zero IPC handle with rank 1."""
    path = f"/tmp/qwen27-esimd-event-{os.environ['MASTER_PORT']}.sock"
    server = None
    if rank == 0:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(path)
        server.listen(1)
    dist.barrier()

    if rank == 0:
        assert server is not None
        conn, _ = server.accept()
    else:
        conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.connect(path)

    imported_fd = -1
    shared_hex = local_hex
    if rank == 0:
        assert local_hex is not None
        local = bytes.fromhex(local_hex)
        local_fd = struct.unpack_from("i", local, 0)[0]
        conn.sendmsg(
            [local],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [local_fd]))],
        )
    else:
        remote, ancillary, _, _ = conn.recvmsg(
            64, socket.CMSG_SPACE(array.array("i").itemsize)
        )
        imported_fds = array.array("i")
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                imported_fds.frombytes(data[: imported_fds.itemsize])
        if len(imported_fds) != 1 or not remote:
            raise RuntimeError("failed to transfer Level Zero IPC event-pool fd")
        imported_fd = imported_fds[0]
        remote_mutable = bytearray(remote)
        struct.pack_into("i", remote_mutable, 0, imported_fd)
        shared_hex = remote_mutable.hex()

    conn.close()
    if server is not None:
        server.close()
        os.unlink(path)
    dist.barrier()
    return shared_hex, imported_fd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--hidden", type=int, default=5120)
    parser.add_argument("--slots", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--timeout-iters", type=int, default=10_000_000)
    parser.add_argument("--poll-mode", type=int, choices=range(4), default=0)
    parser.add_argument("--barrier-rounds", type=int, choices=range(9), default=1)
    parser.add_argument("--publish-mode", type=int, choices=range(4), default=0)
    parser.add_argument("--queue-barrier", action="store_true")
    parser.add_argument("--l0-memory-barrier", action="store_true")
    parser.add_argument("--l0-event-scope", type=int, choices=range(3), default=0)
    parser.add_argument("--ipc-open-mode", type=int, choices=range(3), default=1)
    parser.add_argument("--l0-ipc-event", action="store_true")
    parser.add_argument("--precompile-local", action="store_true")
    parser.add_argument("--l0-counter-event", action="store_true")
    parser.add_argument("--graph", action="store_true")
    parser.add_argument("--sync-every", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world = int(os.environ["WORLD_SIZE"])
    if world != 2:
        raise RuntimeError("this prototype currently requires exactly two ranks")

    torch.xpu.set_device(local_rank)
    dist.init_process_group("xccl")

    shape = (args.rows, args.hidden)
    payload = torch.empty(
        (args.slots, *shape), device="xpu", dtype=torch.bfloat16
    )
    sequence = torch.zeros((args.slots,), device="xpu", dtype=torch.int32)
    counter = torch.zeros((1,), device="xpu", dtype=torch.int32)
    status = torch.zeros((1,), device="xpu", dtype=torch.int32)

    payload_handles = [None] * world
    sequence_handles = [None] * world
    dist.all_gather_object(payload_handles, ext.get_ipc_handle(payload))
    dist.all_gather_object(sequence_handles, ext.get_ipc_handle(sequence))
    peer_rank = rank ^ 1
    peer_payload_ptr = ext.open_ipc_handle_with_mode(
        payload_handles[peer_rank], local_rank, args.ipc_open_mode
    )
    peer_sequence_ptr = ext.open_ipc_handle_with_mode(
        sequence_handles[peer_rank], local_rank, args.ipc_open_mode
    )
    peer_payload_arg = signed_ptr(peer_payload_ptr)
    peer_sequence_arg = signed_ptr(peer_sequence_ptr)

    local_ipc_event = 0
    peer_ipc_event = 0

    event_counter = None
    peer_event_counter_ptr = 0
    counter_event_pair_first = 0
    if args.l0_counter_event:
        event_counter = torch.zeros((1,), device="xpu", dtype=torch.int64)
        counter_handles = [None] * world
        dist.all_gather_object(counter_handles, ext.get_ipc_handle(event_counter))
        peer_event_counter_ptr = ext.open_ipc_handle_with_mode(
            counter_handles[peer_rank], local_rank, args.ipc_open_mode
        )
        pair = ext.create_external_counter_event_pair(
            event_counter, signed_ptr(peer_event_counter_ptr)
        )
        counter_event_pair_first = pair[0]
        local_ipc_event = signed_ptr(pair[0])
        peer_ipc_event = signed_ptr(pair[1])

    imported_event_fd = -1
    owns_event_pair = False
    opened_event_pair_first = 0
    if args.l0_ipc_event:
        print(f"rank={rank} ipc_event_phase=create", flush=True)
        local_event_pool_handle = (
            ext.create_ipc_event_pair_pool(payload) if rank == 0 else None
        )
        print(f"rank={rank} ipc_event_phase=exchange", flush=True)
        shared_event_pool_handle, imported_event_fd = share_rank0_ipc_event_handle(
            local_event_pool_handle, rank
        )
        print(f"rank={rank} ipc_event_phase=open", flush=True)
        if rank == 0:
            pair = ext.local_ipc_event_pair_handles(payload)
            owns_event_pair = True
        else:
            assert shared_event_pool_handle is not None
            pair = ext.open_ipc_event_pair(shared_event_pool_handle)
            opened_event_pair_first = pair[0]
        local_ipc_event = signed_ptr(pair[rank])
        peer_ipc_event = signed_ptr(pair[rank ^ 1])
        print(f"rank={rank} ipc_event_phase=ready", flush=True)

    base = (
        torch.arange(args.rows * args.hidden, device="xpu", dtype=torch.float32)
        .reshape(shape)
        .remainder(97)
        .div_(32)
        .to(torch.bfloat16)
    )
    input_tensor = torch.empty(shape, device="xpu", dtype=torch.bfloat16)
    output = torch.empty_like(input_tensor)

    if rank == 0:
        print(f"native_queue_kind={ext.native_queue_kind(input_tensor)}", flush=True)

    if args.precompile_local:
        input_tensor.copy_(base + rank)
        ext.allreduce_bf16(
            input_tensor,
            output,
            payload,
            sequence,
            signed_ptr(payload.data_ptr()),
            signed_ptr(sequence.data_ptr()),
            counter,
            status,
            args.timeout_iters,
            args.poll_mode,
            0,
            args.publish_mode,
            0,
            0,
            0,
            0,
            0,
        )
        torch.xpu.synchronize()
        if int(status.cpu().item()) != 0:
            raise RuntimeError(f"rank {rank}: local precompile unexpectedly timed out")
        counter.zero_()
        sequence.zero_()
        status.zero_()
        torch.xpu.synchronize()
        dist.barrier()

    graph = None
    if args.graph:
        input_tensor.copy_(base + rank)
        ext.allreduce_bf16(
            input_tensor,
            output,
            payload,
            sequence,
            peer_payload_arg,
            peer_sequence_arg,
            counter,
            status,
            args.timeout_iters,
            args.poll_mode,
            args.barrier_rounds,
            args.publish_mode,
            int(args.queue_barrier),
            int(args.l0_memory_barrier),
            args.l0_event_scope,
            local_ipc_event,
            peer_ipc_event,
        )
        torch.xpu.synchronize()
        dist.barrier()
        graph = torch.xpu.XPUGraph()
        with torch.xpu.graph(graph):
            ext.allreduce_bf16(
                input_tensor,
                output,
                payload,
                sequence,
                peer_payload_arg,
                peer_sequence_arg,
                counter,
                status,
                args.timeout_iters,
                args.poll_mode,
                args.barrier_rounds,
                args.publish_mode,
                int(args.queue_barrier),
                int(args.l0_memory_barrier),
                args.l0_event_scope,
                local_ipc_event,
                peer_ipc_event,
            )
        dist.barrier()

    def run_one(iteration: int) -> None:
        offset = float((iteration % 31) - 15)
        input_tensor.copy_(base + rank * 3 + offset)
        if args.l0_ipc_event:
            print(f"rank={rank} ipc_event_phase=submit iteration={iteration}", flush=True)
        if graph is None:
            ext.allreduce_bf16(
                input_tensor,
                output,
                payload,
                sequence,
                peer_payload_arg,
                peer_sequence_arg,
                counter,
                status,
                args.timeout_iters,
                args.poll_mode,
                args.barrier_rounds,
                args.publish_mode,
                int(args.queue_barrier),
                int(args.l0_memory_barrier),
                args.l0_event_scope,
                local_ipc_event,
                peer_ipc_event,
            )
        else:
            graph.replay()
        if args.l0_ipc_event:
            print(f"rank={rank} ipc_event_phase=submitted iteration={iteration}", flush=True)

    for iteration in range(args.warmup):
        run_one(iteration)
        torch.xpu.synchronize()
        if int(status.cpu().item()) != 0:
            raise RuntimeError(
                f"rank {rank}: poll timeout during warmup; "
                f"counter={counter.cpu().tolist()} "
                f"sequence={sequence.cpu().tolist()} "
                f"status={status.cpu().tolist()}"
            )
    dist.barrier()

    start = time.perf_counter()
    checked = 0
    for iteration in range(args.iterations):
        run_one(iteration + args.warmup)
        should_check = (
            args.sync_every > 0
            and ((iteration + 1) % args.sync_every == 0
                 or iteration + 1 == args.iterations)
        )
        if should_check:
            torch.xpu.synchronize()
            if int(status.cpu().item()) != 0:
                raise RuntimeError(
                    f"rank {rank}: poll timeout at iteration {iteration}"
                )
            logical = iteration + args.warmup
            offset = float((logical % 31) - 15)
            local_expected = (base + rank * 3 + offset).to(torch.bfloat16)
            peer_expected = (base + peer_rank * 3 + offset).to(torch.bfloat16)
            expected = (local_expected.float() + peer_expected.float()).to(
                torch.bfloat16
            )
            if not torch.equal(output, expected):
                diff = (output.float() - expected.float()).abs()
                raise AssertionError(
                    f"rank {rank}: mismatch at iteration {iteration}: "
                    f"max_diff={diff.max().item()} bad={int((diff != 0).sum().item())}"
                )
            checked += 1
    torch.xpu.synchronize()
    dist.barrier()
    elapsed = time.perf_counter() - start

    if rank == 0:
        mode = "graph" if graph is not None else "direct"
        print(
            f"PASS mode={mode} shape={shape} iterations={args.iterations} "
            f"checks={checked} ms_per_iter={elapsed * 1000 / args.iterations:.6f}",
            flush=True,
        )

    ext.close_ipc_handle(peer_payload_ptr, local_rank)
    ext.close_ipc_handle(peer_sequence_ptr, local_rank)
    if args.l0_ipc_event:
        if owns_event_pair:
            ext.destroy_local_ipc_event_pair(payload)
        else:
            ext.close_ipc_event_pair(opened_event_pair_first)
            os.close(imported_event_fd)
    if args.l0_counter_event:
        ext.destroy_external_counter_event_pair(counter_event_pair_first)
        ext.close_ipc_handle(peer_event_counter_ptr, local_rank)
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
