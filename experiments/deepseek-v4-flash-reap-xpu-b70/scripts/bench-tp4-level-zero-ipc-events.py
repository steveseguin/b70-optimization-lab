#!/usr/bin/env python3
"""Probe ordinary binary Level Zero IPC events across four B70 processes.

Each rank owns one IPC pool with seven one-shot events per measured cycle. The
parent brokers pool descriptor file descriptors with SCM_RIGHTS, every rank
imports the other three pools, and an asynchronous immediate command list
executes seven sequential local signal / peer-wait stages. Events are not
reset or reused; safe production slot retirement remains a separate gate.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import multiprocessing as mp
from multiprocessing.reduction import recv_handle, send_handle
import os
import statistics
import time


WORLD = 4
STAGES = 7
ZE_SUCCESS = 0
ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES = 0x6
ZE_STRUCTURE_TYPE_CONTEXT_DESC = 0xD
ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC = 0xE
ZE_STRUCTURE_TYPE_EVENT_POOL_DESC = 0x10
ZE_STRUCTURE_TYPE_EVENT_DESC = 0x11
ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE = 1 << 0
ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS = 2
ZE_COMMAND_QUEUE_PRIORITY_NORMAL = 0
ZE_EVENT_POOL_FLAG_HOST_VISIBLE = 1 << 0
ZE_EVENT_POOL_FLAG_IPC = 1 << 1
ZE_EVENT_SCOPE_FLAG_DEVICE = 1 << 1
ZE_TIMEOUT_INFINITE = (1 << 64) - 1
IPC_HANDLE_BYTES = 64


class ContextDesc(ctypes.Structure):
    _fields_ = [
        ("stype", ctypes.c_uint32),
        ("pNext", ctypes.c_void_p),
        ("flags", ctypes.c_uint32),
    ]


class QueueGroupProperties(ctypes.Structure):
    _fields_ = [
        ("stype", ctypes.c_uint32),
        ("pNext", ctypes.c_void_p),
        ("flags", ctypes.c_uint32),
        ("maxMemoryFillPatternSize", ctypes.c_size_t),
        ("numQueues", ctypes.c_uint32),
    ]


class QueueDesc(ctypes.Structure):
    _fields_ = [
        ("stype", ctypes.c_uint32),
        ("pNext", ctypes.c_void_p),
        ("ordinal", ctypes.c_uint32),
        ("index", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("mode", ctypes.c_uint32),
        ("priority", ctypes.c_uint32),
    ]


class EventPoolDesc(ctypes.Structure):
    _fields_ = [
        ("stype", ctypes.c_uint32),
        ("pNext", ctypes.c_void_p),
        ("flags", ctypes.c_uint32),
        ("count", ctypes.c_uint32),
    ]


class EventDesc(ctypes.Structure):
    _fields_ = [
        ("stype", ctypes.c_uint32),
        ("pNext", ctypes.c_void_p),
        ("index", ctypes.c_uint32),
        ("signal", ctypes.c_uint32),
        ("wait", ctypes.c_uint32),
    ]


class IpcEventPoolHandle(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * IPC_HANDLE_BYTES)]


def check(result: int, what: str) -> None:
    if result != ZE_SUCCESS:
        raise RuntimeError(f"{what} failed with Level Zero result 0x{result:08x}")


def configure_api(ze: ctypes.CDLL) -> None:
    handle_p = ctypes.POINTER(ctypes.c_void_p)
    ze.zeInit.argtypes = [ctypes.c_uint32]
    ze.zeInit.restype = ctypes.c_uint32
    ze.zeDriverGet.argtypes = [ctypes.POINTER(ctypes.c_uint32), handle_p]
    ze.zeDriverGet.restype = ctypes.c_uint32
    ze.zeDeviceGet.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        handle_p,
    ]
    ze.zeDeviceGet.restype = ctypes.c_uint32
    ze.zeContextCreate.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ContextDesc),
        handle_p,
    ]
    ze.zeContextCreate.restype = ctypes.c_uint32
    ze.zeContextDestroy.argtypes = [ctypes.c_void_p]
    ze.zeContextDestroy.restype = ctypes.c_uint32
    ze.zeDeviceGetCommandQueueGroupProperties.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(QueueGroupProperties),
    ]
    ze.zeDeviceGetCommandQueueGroupProperties.restype = ctypes.c_uint32
    ze.zeCommandListCreateImmediate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(QueueDesc),
        handle_p,
    ]
    ze.zeCommandListCreateImmediate.restype = ctypes.c_uint32
    ze.zeCommandListDestroy.argtypes = [ctypes.c_void_p]
    ze.zeCommandListDestroy.restype = ctypes.c_uint32
    ze.zeCommandListAppendSignalEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ze.zeCommandListAppendSignalEvent.restype = ctypes.c_uint32
    ze.zeCommandListAppendWaitOnEvents.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ze.zeCommandListAppendWaitOnEvents.restype = ctypes.c_uint32
    ze.zeCommandListHostSynchronize.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    ze.zeCommandListHostSynchronize.restype = ctypes.c_uint32
    ze.zeEventPoolCreate.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(EventPoolDesc),
        ctypes.c_uint32,
        handle_p,
        handle_p,
    ]
    ze.zeEventPoolCreate.restype = ctypes.c_uint32
    ze.zeEventPoolDestroy.argtypes = [ctypes.c_void_p]
    ze.zeEventPoolDestroy.restype = ctypes.c_uint32
    ze.zeEventPoolGetIpcHandle.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(IpcEventPoolHandle),
    ]
    ze.zeEventPoolGetIpcHandle.restype = ctypes.c_uint32
    ze.zeEventPoolOpenIpcHandle.argtypes = [
        ctypes.c_void_p,
        IpcEventPoolHandle,
        handle_p,
    ]
    ze.zeEventPoolOpenIpcHandle.restype = ctypes.c_uint32
    ze.zeEventPoolCloseIpcHandle.argtypes = [ctypes.c_void_p]
    ze.zeEventPoolCloseIpcHandle.restype = ctypes.c_uint32
    ze.zeEventCreate.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(EventDesc),
        handle_p,
    ]
    ze.zeEventCreate.restype = ctypes.c_uint32
    ze.zeEventDestroy.argtypes = [ctypes.c_void_p]
    ze.zeEventDestroy.restype = ctypes.c_uint32
    ze.zeEventHostReset.argtypes = [ctypes.c_void_p]
    ze.zeEventHostReset.restype = ctypes.c_uint32
    ze.zeEventQueryStatus.argtypes = [ctypes.c_void_p]
    ze.zeEventQueryStatus.restype = ctypes.c_uint32


def one_handle(getter, owner, what: str) -> ctypes.c_void_p:
    count = ctypes.c_uint32(0)
    if owner is None:
        check(getter(ctypes.byref(count), None), f"{what} count")
    else:
        check(getter(owner, ctypes.byref(count), None), f"{what} count")
    if count.value < 1:
        raise RuntimeError(f"{what} returned no handles")
    values = (ctypes.c_void_p * count.value)()
    if owner is None:
        check(getter(ctypes.byref(count), values), what)
    else:
        check(getter(owner, ctypes.byref(count), values), what)
    return values[0]


def _worker(
    rank: int,
    conn,
    final_barrier,
    warmups: int,
    iterations: int,
) -> None:
    os.environ["ZE_AFFINITY_MASK"] = str(rank)
    os.environ["ONEAPI_DEVICE_SELECTOR"] = "level_zero:*"
    ze = ctypes.CDLL("libze_loader.so.1")
    configure_api(ze)
    check(ze.zeInit(0), "zeInit")
    driver = one_handle(ze.zeDriverGet, None, "zeDriverGet")
    device = one_handle(ze.zeDeviceGet, driver, "zeDeviceGet")

    context_desc = ContextDesc(ZE_STRUCTURE_TYPE_CONTEXT_DESC, None, 0)
    context = ctypes.c_void_p()
    check(
        ze.zeContextCreate(driver, ctypes.byref(context_desc), ctypes.byref(context)),
        "zeContextCreate",
    )

    group_count = ctypes.c_uint32(0)
    check(
        ze.zeDeviceGetCommandQueueGroupProperties(
            device, ctypes.byref(group_count), None
        ),
        "queue group count",
    )
    groups = (QueueGroupProperties * group_count.value)()
    for group in groups:
        group.stype = ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES
    check(
        ze.zeDeviceGetCommandQueueGroupProperties(
            device, ctypes.byref(group_count), groups
        ),
        "queue group properties",
    )
    compute_ordinal = next(
        index
        for index, group in enumerate(groups)
        if group.flags & ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE
    )
    queue_desc = QueueDesc(
        ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC,
        None,
        compute_ordinal,
        0,
        0,
        ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS,
        ZE_COMMAND_QUEUE_PRIORITY_NORMAL,
    )
    command_list = ctypes.c_void_p()
    check(
        ze.zeCommandListCreateImmediate(
            context, device, ctypes.byref(queue_desc), ctypes.byref(command_list)
        ),
        "zeCommandListCreateImmediate",
    )

    pool_desc = EventPoolDesc(
        ZE_STRUCTURE_TYPE_EVENT_POOL_DESC,
        None,
        ZE_EVENT_POOL_FLAG_IPC | ZE_EVENT_POOL_FLAG_HOST_VISIBLE,
        STAGES * (warmups + iterations),
    )
    local_pool = ctypes.c_void_p()
    device_array = (ctypes.c_void_p * 1)(device)
    check(
        ze.zeEventPoolCreate(
            context,
            ctypes.byref(pool_desc),
            1,
            device_array,
            ctypes.byref(local_pool),
        ),
        "zeEventPoolCreate",
    )
    ipc_handle = IpcEventPoolHandle()
    check(
        ze.zeEventPoolGetIpcHandle(local_pool, ctypes.byref(ipc_handle)),
        "zeEventPoolGetIpcHandle",
    )
    raw_handle = bytes(ipc_handle.data)
    embedded_fd = int.from_bytes(raw_handle[:4], byteorder="little", signed=True)
    if embedded_fd < 0:
        raise RuntimeError(f"invalid event-pool IPC descriptor {embedded_fd}")
    conn.send((rank, os.getpid(), raw_handle))
    send_handle(conn, embedded_fd, os.getppid())

    peers = conn.recv()
    peer_fds: list[int] = []
    imported_pools: dict[int, ctypes.c_void_p] = {}
    for peer_rank, _peer_raw in peers:
        peer_fd = recv_handle(conn)
        peer_handle = IpcEventPoolHandle()
        # Event-pool handles carry pool metadata beyond the descriptor. Keep
        # those bytes while replacing the exporter-local FD with the
        # SCM_RIGHTS duplicate valid in this process.
        rebuilt = bytearray(_peer_raw)
        rebuilt[:4] = int(peer_fd).to_bytes(4, byteorder="little", signed=True)
        ctypes.memmove(ctypes.byref(peer_handle), bytes(rebuilt), IPC_HANDLE_BYTES)
        pool = ctypes.c_void_p()
        check(
            ze.zeEventPoolOpenIpcHandle(context, peer_handle, ctypes.byref(pool)),
            f"zeEventPoolOpenIpcHandle peer {peer_rank}",
        )
        imported_pools[peer_rank] = pool
        peer_fds.append(peer_fd)

    local_events: list[ctypes.c_void_p] = []
    peer_events: dict[int, list[ctypes.c_void_p]] = {}
    event_count = STAGES * (warmups + iterations)
    for event_index in range(event_count):
        desc = EventDesc(
            ZE_STRUCTURE_TYPE_EVENT_DESC,
            None,
            event_index,
            ZE_EVENT_SCOPE_FLAG_DEVICE,
            ZE_EVENT_SCOPE_FLAG_DEVICE,
        )
        event = ctypes.c_void_p()
        check(
            ze.zeEventCreate(local_pool, ctypes.byref(desc), ctypes.byref(event)),
            "zeEventCreate local",
        )
        local_events.append(event)
    for peer_rank, pool in imported_pools.items():
        events = []
        for event_index in range(event_count):
            desc = EventDesc(
                ZE_STRUCTURE_TYPE_EVENT_DESC,
                None,
                event_index,
                ZE_EVENT_SCOPE_FLAG_DEVICE,
                ZE_EVENT_SCOPE_FLAG_DEVICE,
            )
            event = ctypes.c_void_p()
            check(
                ze.zeEventCreate(pool, ctypes.byref(desc), ctypes.byref(event)),
                f"zeEventCreate peer {peer_rank}",
            )
            events.append(event)
        peer_events[peer_rank] = events

    conn.send(("ready", rank))
    if conn.recv() != "go":
        raise RuntimeError("parent failed to release workers")

    samples_us = []
    total = warmups + iterations
    for cycle in range(total):
        started = time.perf_counter_ns()
        for stage in range(STAGES):
            event_index = cycle * STAGES + stage
            check(
                ze.zeCommandListAppendSignalEvent(
                    command_list, local_events[event_index]
                ),
                "zeCommandListAppendSignalEvent",
            )
            waits = (ctypes.c_void_p * (WORLD - 1))(
                *[
                    peer_events[peer_rank][event_index]
                    for peer_rank in sorted(peer_events)
                ]
            )
            check(
                ze.zeCommandListAppendWaitOnEvents(
                    command_list, WORLD - 1, waits
                ),
                "zeCommandListAppendWaitOnEvents",
            )
        check(
            ze.zeCommandListHostSynchronize(command_list, ZE_TIMEOUT_INFINITE),
            "zeCommandListHostSynchronize",
        )
        elapsed_us = (time.perf_counter_ns() - started) / 1000.0
        if cycle >= warmups:
            samples_us.append(elapsed_us)

    # Test teardown only: ensure no process destroys an imported pool while a
    # slower peer is completing its final wait. This is not in the measured or
    # reusable event-slot path.
    final_barrier.wait()

    conn.send(
        {
            "rank": rank,
            "median_us": statistics.median(samples_us),
            "p10_us": sorted(samples_us)[int(0.10 * (len(samples_us) - 1))],
            "p90_us": sorted(samples_us)[int(0.90 * (len(samples_us) - 1))],
            "min_us": min(samples_us),
            "max_us": max(samples_us),
            "all_local_events_signaled": all(
                ze.zeEventQueryStatus(event) == ZE_SUCCESS
                for event in local_events
            ),
        }
    )

    for events in peer_events.values():
        for event in events:
            check(ze.zeEventDestroy(event), "zeEventDestroy peer")
    for event in local_events:
        check(ze.zeEventDestroy(event), "zeEventDestroy local")
    for pool in imported_pools.values():
        check(ze.zeEventPoolCloseIpcHandle(pool), "zeEventPoolCloseIpcHandle")
    check(ze.zeEventPoolDestroy(local_pool), "zeEventPoolDestroy")
    check(ze.zeCommandListDestroy(command_list), "zeCommandListDestroy")
    check(ze.zeContextDestroy(context), "zeContextDestroy")
    for fd in peer_fds:
        try:
            os.close(fd)
        except OSError:
            # The Level Zero close path may consume the imported descriptor.
            pass
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    ctx = mp.get_context("spawn")
    final_barrier = ctx.Barrier(WORLD)
    parent_conns = []
    workers = []
    for rank in range(WORLD):
        parent, child = ctx.Pipe(duplex=True)
        worker = ctx.Process(
            target=_worker,
            args=(rank, child, final_barrier, args.warmups, args.iterations),
        )
        worker.start()
        child.close()
        parent_conns.append(parent)
        workers.append(worker)

    exports = []
    for conn in parent_conns:
        rank, pid, raw_handle = conn.recv()
        fd = recv_handle(conn)
        exports.append((rank, pid, raw_handle, fd))

    for destination, conn in enumerate(parent_conns):
        peers = [
            (rank, raw_handle)
            for rank, _, raw_handle, _ in exports
            if rank != destination
        ]
        conn.send(peers)
        destination_pid = exports[destination][1]
        for rank, _, _, fd in exports:
            if rank != destination:
                send_handle(conn, fd, destination_pid)
    for _, _, _, fd in exports:
        os.close(fd)

    for conn in parent_conns:
        message = conn.recv()
        if message[0] != "ready":
            raise RuntimeError(f"unexpected worker message {message}")
    for conn in parent_conns:
        conn.send("go")

    rows = [conn.recv() for conn in parent_conns]
    for worker in workers:
        worker.join(timeout=30)
        if worker.exitcode != 0:
            raise RuntimeError(f"worker {worker.pid} exited {worker.exitcode}")

    result = {
        "schema_version": 1,
        "classification": "deepseek_v4_tp4_level_zero_ipc_binary_event_gate",
        "world_size": WORLD,
        "stages": STAGES,
        "warmups": args.warmups,
        "iterations": args.iterations,
        "one_shot_events": True,
        "event_count_per_rank": STAGES * (args.warmups + args.iterations),
        "event_reuse_attempted": False,
        "final_host_barrier_used_only_for_teardown": True,
        "all_ranks_passed": all(row["all_local_events_signaled"] for row in rows),
        "slowest_rank_median_us": max(row["median_us"] for row in rows),
        "ranks": rows,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered, end="")
    if not result["all_ranks_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
