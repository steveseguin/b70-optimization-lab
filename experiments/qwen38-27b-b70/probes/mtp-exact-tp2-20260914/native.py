"""ctypes adapter; import is CPU only. Construct Native only in an admitted gate."""
import ctypes as C
from pathlib import Path
import re
import subprocess
import time

U = C.c_size_t
P = C.POINTER(U)
# Kernel formulations; codes are the et_add_mode ABI (see exact_tp2.cpp).
ADD_MODES = {"m0": 0, "m1": 1, "m2": 2, "m3": 3}
SIGNATURES = {
    "device_uuid": [U, C.c_void_p], "admit_peer": [U, C.c_void_p],
    "validate_fd": [U, C.c_void_p],
    "allocate": [U, U, P], "free": [U, U],
    "export": [U, U, C.c_void_p], "put_export": [U, C.c_void_p],
    "open": [U, C.c_void_p, P], "close": [U, U],
    "marker": [U, P], "copy": [U, U, U, U, P],
    "add": [U, U, U, U, C.c_int, P],
    "add_mode": [U, U, U, U, C.c_int, C.c_int, P],  # Required: refuses pre-2026-09-15 builds.
    "poll": [U, C.POINTER(C.c_int)], "release_event": [U],
}


class Native:
    def __init__(self, library, queue_pointer, timeout=10):
        # A torch-owned sycl::queue must never cross a libsycl ABI major. Check
        # loaded libraries BEFORE loading ours, or a second major could coexist.
        needed = subprocess.check_output(["readelf", "-d", str(library)], text=True)
        majors = set(re.findall(r"libsycl\.so\.(\d+)", needed))
        loaded = set(re.findall(r"libsycl\.so\.(\d+)", Path("/proc/self/maps").read_text()))
        if len(majors) != 1 or loaded != majors:
            raise RuntimeError(f"SYCL ABI admission failed: binary={majors}, torch={loaded}; rebuild with matching compiler")
        self.lib = C.CDLL(str(library))
        self.q, self.timeout = queue_pointer, timeout
        self.lib.et_error.restype = C.c_char_p
        for name, args in SIGNATURES.items():
            f = getattr(self.lib, "et_" + name)
            f.argtypes, f.restype = args, C.c_int
        self.poisoned = False

    def call(self, name, *args):
        if self.poisoned:
            raise RuntimeError("native collective poisoned")
        if getattr(self.lib, "et_" + name)(*args):
            self.poisoned = True
            raise RuntimeError(self.lib.et_error().decode())

    def pointer(self, name, *args):
        out = U()
        self.call(name, self.q, *args, C.byref(out))
        return out.value

    def wait(self, event):
        deadline = time.monotonic() + self.timeout
        done = C.c_int()
        while True:
            self.call("poll", event, C.byref(done))
            if done.value:
                self.call("release_event", event)
                return
            if time.monotonic() >= deadline:
                self.poisoned = True
                raise TimeoutError("native local event deadline; do not free live buffers")
            # No device-side wait or busy peer loop. This host poll is bounded.
            time.sleep(0)

    def copy(self, dst, src, bytes_):
        self.wait(self.pointer("copy", dst, src, bytes_))


class Collective:
    """One owned slot; reads retire before either rank can reuse input.

    Callers must retain both exported inputs until normal close. Fault path
    terminates the worker without running potentially blocking GPU destructors.
    No graph, concurrent-stream or live-model integration is claimed.
    """
    def __init__(self, native, channel, count, local, peer, output, add_mode=None):
        if add_mode is not None and add_mode not in ADD_MODES:
            raise ValueError(f"unknown add mode {add_mode!r}")
        self.native, self.channel = native, channel
        self.count, self.local, self.peer, self.output = count, local, peer, output
        self.add_mode = add_mode  # None keeps the frozen et_add path.
        self.poisoned = False

    def run(self):
        if self.poisoned:
            raise RuntimeError("collective poisoned")
        try:
            n, ch = self.native, self.channel
            n.wait(n.pointer("marker"))  # Complete local producer before READY.
            ch.exchange("READY", elements=self.count, dtype="fp16")
            n.copy(self.output, self.peer, self.count * 2)
            # Both peer copies must retire BEFORE local kernel reads the input.
            # Thus even read/read concurrency to the same device allocation is
            # unnecessary. Unlike old peer mailboxes, no coherence flag is read.
            ch.exchange("COPIED", elements=self.count, dtype="fp16")
            if self.add_mode is None:
                n.wait(n.pointer("add", self.local, self.output, self.count, ch.rank))
            else:
                n.wait(n.pointer("add_mode", self.local, self.output, self.count, ch.rank, ADD_MODES[self.add_mode]))
            return self.output
        except BaseException:
            self.poisoned = True
            n.poisoned = True
            raise
