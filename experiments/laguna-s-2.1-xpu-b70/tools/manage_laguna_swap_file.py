#!/usr/bin/env python3
"""Fail-closed lifecycle helper for the one Laguna validation swap file."""

from __future__ import annotations

import json
import os
import signal
import stat
import sys
from pathlib import Path


SWAP_PATH = Path("/swap-laguna-longctx.img")
SWAP_SIZE = 16 * 1024**3


def die(message: str) -> None:
    raise SystemExit(f"Laguna swap helper: {message}")


def identity(st: os.stat_result) -> dict[str, int]:
    return {
        "device": st.st_dev,
        "inode": st.st_ino,
        "uid": st.st_uid,
        "gid": st.st_gid,
        "size": st.st_size,
        "mode": stat.S_IMODE(st.st_mode),
    }


def expected_identity(argv: list[str]) -> dict[str, int]:
    if len(argv) != 6:
        die("identity requires device inode uid gid size mode")
    try:
        values = [int(value) for value in argv]
    except ValueError as exc:
        die(f"invalid identity integer: {exc}")
    return dict(zip(("device", "inode", "uid", "gid", "size", "mode"), values))


def require_identity(expected: dict[str, int]) -> os.stat_result:
    try:
        observed = os.lstat(SWAP_PATH)
    except OSError as exc:
        die(f"cannot inspect swap path: {exc}")
    if not stat.S_ISREG(observed.st_mode):
        die("swap path is not a regular file")
    if identity(observed) != expected:
        die(f"swap identity mismatch: observed={identity(observed)}")
    return observed


def swap_state() -> str:
    try:
        lines = Path("/proc/swaps").read_text(encoding="utf-8").splitlines()[1:]
    except OSError as exc:
        die(f"cannot inspect /proc/swaps: {exc}")
    matches = [line for line in lines if line.split() and line.split()[0] == str(SWAP_PATH)]
    if len(matches) > 1:
        die("temporary swap appears more than once")
    return "ACTIVE" if matches else "INACTIVE"


def interrupt_allocation(signum: int, _frame: object) -> None:
    raise InterruptedError(f"received signal {signum} during swap allocation")


def create() -> None:
    fd: int | None = None
    created_identity: tuple[int, int] | None = None
    previous_handlers: dict[signal.Signals, signal.Handlers] = {}
    managed_signals = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    opening_mask: set[signal.Signals] | None = None
    cleanup_mask: set[signal.Signals] | None = None
    try:
        for signum in managed_signals:
            previous_handlers[signum] = signal.signal(signum, interrupt_allocation)
        opening_mask = signal.pthread_sigmask(signal.SIG_BLOCK, managed_signals)
        fd = os.open(
            SWAP_PATH,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600,
        )
        first = os.fstat(fd)
        created_identity = (first.st_dev, first.st_ino)
        signal.pthread_sigmask(signal.SIG_SETMASK, opening_mask)
        opening_mask = None
        os.fchmod(fd, 0o600)
        os.posix_fallocate(fd, 0, SWAP_SIZE)
        final = os.fstat(fd)
        observed = identity(final)
        expected = {
            "device": final.st_dev,
            "inode": final.st_ino,
            "uid": 0,
            "gid": 0,
            "size": SWAP_SIZE,
            "mode": 0o600,
        }
        if observed != expected:
            die(f"created swap identity mismatch: observed={observed}")
        print(json.dumps(observed, sort_keys=True))
    except BaseException:
        cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, managed_signals)
        if fd is not None:
            try:
                if created_identity is None:
                    opened = os.fstat(fd)
                    created_identity = (opened.st_dev, opened.st_ino)
                current = os.lstat(SWAP_PATH)
                if (current.st_dev, current.st_ino) == created_identity:
                    os.unlink(SWAP_PATH)
            except FileNotFoundError:
                pass
        raise
    finally:
        if fd is not None:
            os.close(fd)
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)
        if cleanup_mask is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)
        elif opening_mask is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, opening_mask)


def verify(argv: list[str]) -> None:
    require_identity(expected_identity(argv))
    print("IDENTITY_PASS")


def remove_inactive(argv: list[str]) -> None:
    expected = expected_identity(argv)
    require_identity(expected)
    if swap_state() != "INACTIVE":
        die("refusing to remove active swap")
    os.unlink(SWAP_PATH)
    print("REMOVE_PASS")


def main() -> None:
    if len(sys.argv) < 2:
        die("usage: manage_laguna_swap_file.py create|verify|state|remove-inactive")
    command, args = sys.argv[1], sys.argv[2:]
    if command == "create" and not args:
        create()
    elif command == "verify":
        verify(args)
    elif command == "state" and not args:
        print(swap_state())
    elif command == "remove-inactive":
        remove_inactive(args)
    else:
        die("invalid command or arguments")


if __name__ == "__main__":
    main()
