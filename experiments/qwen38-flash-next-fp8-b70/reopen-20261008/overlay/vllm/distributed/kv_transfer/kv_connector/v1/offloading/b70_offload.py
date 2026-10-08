# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""B70 patch 0014 — env-gated KV-offload tracing and hybrid-model fixes.

Every switch defaults OFF; with all of them unset the connector behaves exactly
as upstream. Flags are read when the scheduler / coordinator is constructed.

  B70_OFFLOAD_TRACE=1                 cheap: a periodic CPU-tier state line plus
                                      the mechanism events only (junction-set,
                                      zeroed_by a Mamba group), once per request
  B70_OFFLOAD_TRACE=2                 also every per-request lookup / store /
                                      load / handoff / req-done line (prefix
                                      ``B70-OFFLOAD``). With TRACE=1 these lines
                                      are emitted at DEBUG instead, so they
                                      appear only when vLLM logs at DEBUG.
  B70_OFFLOAD_TRACE_PERIOD_S=60       period of the state line (seconds)
  B70_OFFLOAD_JUNCTION=1              (0014b) set a shared-prefix junction when a
                                      sparse (Mamba/GDN) group is what cuts the
                                      offload hit short of the full-attention hit
  B70_OFFLOAD_GDN_BACKSTEP=N          (0014c) also retain Mamba states N block
                                      boundaries below the replay boundary
  B70_OFFLOAD_EMPTY_ADVANCE_GUARD=1     (0014d) do not advance the stored index
                                      past keys that are present but still
                                      write-pending (vllm#56795)
  B70_OFFLOAD_GROUP_EVICT=1           (0014e/f) use the vllm#51787 backport:
                                      request-scoped recency, tail-before-head
                                      eviction across KV groups. Unset = the
                                      upstream v0.30.0 LRU/ARC and per-step
                                      touch, verbatim.
"""

import logging

import os
import threading
import time
from collections import Counter
from collections.abc import Callable

from vllm.logger import init_logger

logger = init_logger("vllm.b70_offload")

TAG = "B70-OFFLOAD"


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s: ignoring non-integer %s=%r", TAG, name, raw)
        return default


def trace_level() -> int:
    """0 off, 1 cheap (state timer + events), 2 per-request lines.
    ``true``/``yes``/``on`` count as 1."""
    raw = os.environ.get("B70_OFFLOAD_TRACE", "").strip().lower()
    if raw in ("true", "yes", "on"):
        return 1
    return max(0, env_int("B70_OFFLOAD_TRACE", 0))


def trace_enabled() -> bool:
    return trace_level() >= 1


def trace_per_request() -> bool:
    """Whether the per-request lines are built at all (their cost is the
    formatting, not only the write): TRACE>=2, or TRACE=1 with DEBUG on."""
    level = trace_level()
    return level >= 2 or (level >= 1 and logger.isEnabledFor(logging.DEBUG))


def group_evict_enabled() -> bool:
    return env_flag("B70_OFFLOAD_GROUP_EVICT")


def junction_enabled() -> bool:
    return env_flag("B70_OFFLOAD_JUNCTION")


def guard_enabled() -> bool:
    return env_flag("B70_OFFLOAD_EMPTY_ADVANCE_GUARD")


def gdn_backstep() -> int:
    return max(0, env_int("B70_OFFLOAD_GDN_BACKSTEP", 0))


def trace_period_s() -> float:
    return float(max(1, env_int("B70_OFFLOAD_TRACE_PERIOD_S", 60)))


def log(fmt: str, *args) -> None:
    logger.info(TAG + " " + fmt, *args)


def log_debug(fmt: str, *args) -> None:
    logger.debug(TAG + " " + fmt, *args)


def _policy_chunks(policy) -> list:
    """Snapshot (key, chunk) pairs of a CPU cache policy (LRU or ARC)."""
    chunks = getattr(policy, "chunks", None)
    if isinstance(chunks, dict):
        return list(chunks.items())
    items: list = []
    for attr in ("t1", "t2"):
        d = getattr(policy, attr, None)
        if isinstance(d, dict):
            items.extend(list(d.items()))
    return items


def cpu_tier_snapshot(
    manager, group_kind: Callable[[int], str], slot_bytes: int
) -> str:
    """One-line summary of the CPU offload tier. Read-only, lock-free."""
    from vllm.v1.kv_offload.base import get_offload_group_idx

    pending = getattr(manager, "_num_write_pending_chunks", None)
    if pending is None:
        return f"manager={type(manager).__name__} (no CPU-tier counters)"
    num_chunks = getattr(manager, "_num_chunks", 0)
    allocated = getattr(manager, "_num_allocated_chunks", 0)
    free_list = len(getattr(manager, "_free_list", ()))
    evictable = getattr(manager, "_num_evictable_cache_chunks", 0)
    items = _policy_chunks(getattr(manager, "_policy", None))
    keys_by_kind: Counter = Counter()
    pending_by_kind: Counter = Counter()
    groups_by_kind: dict[str, set[int]] = {}
    in_use = 0
    for key, chunk in items:
        gidx = get_offload_group_idx(key)
        kind = group_kind(gidx)
        keys_by_kind[kind] += 1
        groups_by_kind.setdefault(kind, set()).add(gidx)
        ref = chunk.ref_cnt
        if ref < 0:
            pending_by_kind[kind] += 1
        elif ref > 0:
            in_use += 1
    ready = len(items) - sum(pending_by_kind.values())
    kinds = " ".join(
        f"{kind}[groups={len(groups_by_kind[kind])} keys={keys_by_kind[kind]} "
        f"pending={pending_by_kind[kind]}]"
        for kind in sorted(keys_by_kind)
    )
    return (
        f"write_pending_chunks={pending} write_pending_bytes={pending * slot_bytes} "
        f"ready_chunks={ready} loading_or_pinned={in_use} evictable={evictable} "
        f"resident_keys={len(items)} allocated={allocated - free_list}/{num_chunks} "
        f"slot_bytes={slot_bytes} {kinds}"
    )


class PeriodicStateLogger:
    """Daemon thread: logs the CPU tier state every ``period`` seconds.

    Runs in the engine-core process next to the scheduler, so it keeps logging
    while the engine is idle (the scheduler loop does not step at idle).
    """

    def __init__(self, period: float, fn: Callable[[], str]):
        self._period = period
        self._fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="b70-offload-state", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self._period):
            for _ in range(3):
                try:
                    log("state t=%.0f %s", time.time(), self._fn())
                    break
                except RuntimeError:
                    # dict changed size under us; retry the snapshot
                    continue
                except Exception as e:  # never kill the engine over a log line
                    log("state error %s: %s", type(e).__name__, e)
                    break

    def stop(self) -> None:
        self._stop.set()
