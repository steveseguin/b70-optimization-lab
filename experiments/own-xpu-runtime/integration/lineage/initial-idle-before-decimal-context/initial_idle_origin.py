"""Conservative initial idle origin for one independently admitted p198 owner.

Pure CPU reads/arithmetic only. No process, native tool, listener or admission.
The caller must bind the fresh owner output and its held directory identity to
that owner, sample launch_monotonic BEFORE Popen, and observe the same boot's
CLOCK_MONOTONIC after readiness. The cold-start file contains no PID: its SHA
cannot establish ownership. The caller must independently confirm the owner's
mapped clock library and absence of clock-symbol interposition. Nothing here
changes the absolute deadline or substitutes readiness receive time as activity.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKET = HERE.parent / 'stage2/packet198-postreply-checkpoint'
BINARY = PACKET / 'build/device/own-rt-iq3'
BINARY_SHA256 = 'c9b401089d95eeb152953a8c0d82d0678de2474934941bc6c97abd4b03287875'
CLOCK_LIBRARY = Path('/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.33')
CLOCK_SHA256 = '1fd75fe70354a416d75aef22bcae68c47bd25d20e2d0568c30b1a9838cf62f11'
SOURCE_PINS = {
 'build/native/main.cpp': '1e7c5f1b6ab19f909fbd03165ead029ea7331a27810b7a6e97961d9f32039581',
 'build/native/request_front.hpp': 'e3a5a90848c88bf7833b6df354115d18e3ef594bbb86eaf3774a8a3281e41dde',
 'evidence/build-compile-only.json': 'c1b3378c6237254a4b6363a8bccd20cfbfb67b186deefa7ea7899b2828e2e962',
 'evidence/source-overlay.json': '761c3817c05e7ab21fb39004b361b4c03250fc65c031ca6cca1ed5bb86a67fbf',
}
MAX_COLD_BYTES = 512
ROUNDING_MARGIN_SECONDS = Decimal('0.001')
_NATIVE_COLD = re.compile(rb'\{"load_and_pin_ms":((?:0|[1-9][0-9]{0,6})\.[0-9]{6}),"initial_cache_fill_bytes":0,"initial_cache_policy":"empty-content-independent","first_prompt_fills_charged_in_request":true\}\n')


class IdleOriginRefusal(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise IdleOriginRefusal(reason)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_native_proof():
    """Check the exact source/build/binary/library on disk; not a process map."""
    for relative, digest in SOURCE_PINS.items():
        require(sha(PACKET / relative) == digest, 'native proof source drift: ' + relative)
    build = json.loads((PACKET / 'evidence/build-compile-only.json').read_text())
    device = [row for row in build['plans'] if row['target'] == 'device']
    require(build['passed'] is True and len(device) == 1 and
            device[0]['binary'] == str(BINARY) and device[0]['binary_sha256'] == BINARY_SHA256,
            'native build identity mismatch')
    require(sha(BINARY) == BINARY_SHA256, 'native binary drift')
    require(CLOCK_LIBRARY.resolve() == CLOCK_LIBRARY and sha(CLOCK_LIBRARY) == CLOCK_SHA256,
            'clock implementation library drift')
    info = time.get_clock_info('monotonic')
    require(info.implementation == 'clock_gettime(CLOCK_MONOTONIC)' and info.monotonic and not info.adjustable,
            'Python monotonic clock differs from proof')


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_cold_start(owner_output, *, expected_owner_identity):
    """Read <=512 bytes under the coordinator's trusted held owner identity.

    Return bytes and hashes, not an assertion that a particular PID wrote them.
    The directory must already belong to the fresh run; never discover/adopt a
    historical output by content or infer ownership from this helper's result.
    """
    root = Path(owner_output)
    require(root.is_absolute() and root.resolve(strict=True) == root, 'real absolute owner output required')
    require(type(expected_owner_identity) is tuple and len(expected_owner_identity) == 2 and
            all(type(v) is int and v >= 0 for v in expected_owner_identity), 'trusted directory dev/ino required')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened = os.fstat(directory)
        require((opened.st_dev, opened.st_ino) == expected_owner_identity and opened.st_uid == os.getuid(),
                'owner directory identity changed')
        fd = os.open('cold-start.json', os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
                    and 0 < before.st_size <= MAX_COLD_BYTES, 'bounded regular private-owner cold-start file required')
            raw = b''
            while len(raw) <= MAX_COLD_BYTES:
                piece = os.read(fd, MAX_COLD_BYTES + 1 - len(raw))
                if not piece:
                    break
                raw += piece
            after = os.fstat(fd)
            named = os.stat('cold-start.json', dir_fd=directory, follow_symlinks=False)
            current = os.stat(root, follow_symlinks=False)
            require(_signature(before) == _signature(after) == _signature(named) and
                    len(raw) == before.st_size and len(raw) <= MAX_COLD_BYTES,
                    'cold-start file changed during read')
            require(root.resolve(strict=True) == root and stat.S_ISDIR(current.st_mode) and
                    (current.st_dev, current.st_ino) == expected_owner_identity, 'owner output replaced during read')
            return dict(raw=raw, sha256=hashlib.sha256(raw).hexdigest(), path=str(root/'cold-start.json'),
                        owner_identity=expected_owner_identity, file_identity=_signature(after))
        finally:
            os.close(fd)
    finally:
        os.close(directory)


def derive_initial_idle_origin(*, launch_monotonic, observed_monotonic,
        cold_start_bytes, cold_start_sha256, admitted_binary_sha256,
        mapped_clock_library_path, mapped_clock_library_sha256):
    """Return a lower bound, conditional on the coordinator provenance above.

    For L<=S<=E<=I, native reports D≈E-S. Taking a lower bound d<=D gives
    L+d<=E<=I. The1ms allowance exceeds six-decimal-ms formatting and bounded
    double conversion error; flooring whole seconds and nextafter protect the
    Python float addition. No clock epoch is borrowed from the native report.
    """
    verify_native_proof()
    require(admitted_binary_sha256 == BINARY_SHA256, 'different admitted owner binary')
    require(str(mapped_clock_library_path) == str(CLOCK_LIBRARY) and
            mapped_clock_library_sha256 == CLOCK_SHA256, 'different admitted mapped clock library')
    require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 2**40
                for x in (launch_monotonic, observed_monotonic)) and observed_monotonic >= launch_monotonic,
            'bounded same-boot monotonic timestamps required')
    require(type(cold_start_bytes) is bytes and 0 < len(cold_start_bytes) <= MAX_COLD_BYTES,
            'bounded native cold-start bytes required')
    require(type(cold_start_sha256) is str and hashlib.sha256(cold_start_bytes).hexdigest() == cold_start_sha256,
            'cold-start byte hash mismatch')
    match = _NATIVE_COLD.fullmatch(cold_start_bytes)
    require(match is not None, 'cold-start grammar differs from exact native emitter')
    milliseconds = Decimal(match.group(1).decode('ascii'))
    require(Decimal(0) <= milliseconds <= Decimal(7_200_000), 'cold load outside admitted duration bound')
    reported_seconds = milliseconds / Decimal(1000)
    elapsed = Decimal.from_float(float(observed_monotonic)) - Decimal.from_float(float(launch_monotonic))
    require(reported_seconds <= elapsed + ROUNDING_MARGIN_SECONDS, 'cold interval exceeds observed launch interval')
    seconds = max(0, int((reported_seconds - ROUNDING_MARGIN_SECONDS).to_integral_value(rounding=ROUND_FLOOR)))
    origin = float(launch_monotonic) if seconds == 0 else math.nextafter(float(launch_monotonic) + seconds, -math.inf)
    require(launch_monotonic <= origin <= observed_monotonic, 'derived origin outside trusted observation')
    return dict(schema='ownrt.initial-idle-origin.v1', scope='conditional conservative initial idle lower bound',
        last_native_activity=origin, whole_seconds_added=seconds, launch_monotonic=launch_monotonic,
        observed_monotonic=observed_monotonic, reported_load_and_pin_ms=str(milliseconds),
        rounding_margin_seconds=str(ROUNDING_MARGIN_SECONDS), cold_start_sha256=cold_start_sha256,
        native_binary_sha256=BINARY_SHA256, clock_library_path=str(CLOCK_LIBRARY), clock_library_sha256=CLOCK_SHA256,
        absolute_origin_monotonic=launch_monotonic, absolute_deadline_changed=False,
        fresh_owner_provenance_verified=False, process_mapping_verified=False, live_admission_ready=False)
