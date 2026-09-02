#!/usr/bin/env python3
"""Drive Samsung's interactive `fumagician` updater through a pseudo-terminal.

The vendor utility is interactive: it lists supported drives, asks
`Do you want to continue the firmware update? [Y/N]:`, performs the NVMe
firmware download/commit, and may ask about a next device or wait on
`Press any key ...`. This driver answers exactly those prompts, records a
complete transcript, and fails closed on anything unexpected:

- the first `continue the firmware update?` prompt receives `Y` once;
- a `continue the firmware update on next device?` prompt receives `N`;
- `Press any key` prompts receive Enter;
- any other `[Y/N]` prompt receives `N`;
- silence longer than `--prompt-timeout` seconds, or a total runtime longer
  than `--total-timeout` seconds, ends the run with a nonzero status.

It never selects a drive, never touches raw firmware images, and never
reboots. Run it as root from the staged tmpfs directory that holds the
hash-verified `fumagician`, `DSRD.enc`, and `5B2QGXA7.enc` files.
"""

from __future__ import annotations

import argparse
import errno
import os
import pty
import select
import sys
import time
from pathlib import Path


CONTINUE_PROMPT = b"Do you want to continue the firmware update? [Y/N]:"
NEXT_DEVICE_PROMPT = b"continue the firmware update on next device? [Y/N]:"
PRESS_ANY_KEY = b"Press any key"
GENERIC_YN = b"[Y/N]:"
COMPLETED = b"Firmware Update Completed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--binary", default="./fumagician")
    parser.add_argument("--prompt-timeout", type=float, default=600.0)
    parser.add_argument("--total-timeout", type=float, default=1500.0)
    parser.add_argument(
        "--answer-continue",
        default="N",
        choices=["Y", "N"],
        help="answer for the first continue prompt; N performs a vendor dry run",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    binary = (args.cwd / args.binary).resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        print(f"FAIL: updater binary is not executable: {binary}", file=sys.stderr)
        return 2
    args.transcript.parent.mkdir(parents=True, exist_ok=True)

    pid, fd = pty.fork()
    if pid == 0:  # child
        os.chdir(args.cwd)
        os.environ["TERM"] = "dumb"
        os.execv(str(binary), [args.binary])
        os._exit(127)

    buffer = b""
    answered_continue = False
    answered_next = 0
    answered_any_key = 0
    saw_completed = False
    started = time.monotonic()
    last_output = started
    transcript = args.transcript.open("wb")
    exit_reason = "child-exit"
    try:
        while True:
            now = time.monotonic()
            if now - started > args.total_timeout:
                exit_reason = "total-timeout"
                break
            if now - last_output > args.prompt_timeout:
                exit_reason = "prompt-timeout"
                break
            ready, _, _ = select.select([fd], [], [], 1.0)
            if not ready:
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            last_output = time.monotonic()
            transcript.write(chunk)
            transcript.flush()
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
            buffer = (buffer + chunk)[-8192:]
            if COMPLETED in buffer:
                saw_completed = True
            reply = None
            if buffer.rstrip().endswith(CONTINUE_PROMPT) and not answered_continue:
                reply = args.answer_continue.encode() + b"\n"
                answered_continue = True
            elif buffer.rstrip().endswith(NEXT_DEVICE_PROMPT):
                reply = b"N\n"
                answered_next += 1
            elif buffer.rstrip().endswith(GENERIC_YN):
                reply = b"N\n"
            elif PRESS_ANY_KEY in buffer[-200:]:
                reply = b"\n"
                answered_any_key += 1
            if reply is not None:
                time.sleep(0.5)
                os.write(fd, reply)
                transcript.write(b"\n[driver-reply] " + reply)
                transcript.flush()
                buffer = b""
    finally:
        transcript.close()

    if exit_reason != "child-exit":
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
    _, status = os.waitpid(pid, 0)
    child_rc = os.waitstatus_to_exitcode(status)
    summary = {
        "exit_reason": exit_reason,
        "child_exit": child_rc,
        "answered_continue": answered_continue,
        "answer_continue": args.answer_continue,
        "answered_next_device": answered_next,
        "answered_any_key": answered_any_key,
        "saw_firmware_update_completed": saw_completed,
    }
    print("\n[driver-summary] " + repr(summary))
    if exit_reason != "child-exit":
        return 3
    if args.answer_continue == "Y" and not saw_completed:
        return 4
    return 0 if child_rc == 0 else 5


if __name__ == "__main__":
    sys.exit(main())
