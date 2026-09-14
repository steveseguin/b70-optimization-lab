"""CPU-only framed, sequenced fail-closed TP2 channel. No torch import."""
import array
import json
import os
import socket
import struct
import time


class Channel:
    def __init__(self, sock, rank, timeout=10.0):
        if rank not in (0, 1) or timeout <= 0:
            raise ValueError("invalid channel parameters")
        self.sock, self.rank, self.timeout = sock, rank, timeout
        self.seq, self.poisoned = 0, False
        self.phase = "READY"

    def _read(self, count, deadline):
        out = bytearray()
        while len(out) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("TP2 peer deadline")
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(count - len(out))
            if not chunk:
                raise ConnectionError("TP2 peer closed; no result is valid")
            out.extend(chunk)
        return bytes(out)

    def exchange(self, phase, **identity):
        if self.poisoned:
            raise RuntimeError("poisoned TP2 channel")
        if phase != self.phase:
            self.poisoned = True
            raise RuntimeError("invalid local phase transition")
        if {"rank", "seq", "phase"} & identity.keys():
            self.poisoned = True
            raise ValueError("reserved TP2 identity key")
        data = {"rank": self.rank, "seq": self.seq, "phase": phase, **identity}
        encoded = json.dumps(data, sort_keys=True).encode()
        if len(encoded) > 4096:
            self.poisoned = True
            raise ValueError("TP2 frame too large")
        deadline = time.monotonic() + self.timeout
        try:
            self.sock.settimeout(self.timeout)
            self.sock.sendall(struct.pack("!I", len(encoded)) + encoded)
            length = struct.unpack("!I", self._read(4, deadline))[0]
            if length > 4096:
                raise ValueError("oversized TP2 peer frame")
            peer = json.loads(self._read(length, deadline))
            expected = dict(data, rank=1 - self.rank)
            if peer != expected:
                raise ValueError(f"TP2 identity/sequence/phase mismatch: {peer!r}")
            self.phase = "COPIED" if phase == "READY" else "READY"
            if phase == "COPIED":
                self.seq += 1
        except BaseException:
            self.poisoned = True
            raise


def exchange_ipc(sock, local_handle):
    """One Linux L0 memory FD, exchanged via SCM_RIGHTS, never integer reuse."""
    if len(local_handle) != 64:
        raise ValueError("expected 64-byte Linux Level Zero IPC handle")
    fd = struct.unpack_from("i", local_handle)[0]
    if fd < 0:
        raise ValueError("invalid exported fd")
    if sock.sendmsg([local_handle], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [fd]))]) != 64:
        raise ConnectionError("partial IPC send")
    data, ancillary, flags, _ = sock.recvmsg(64, socket.CMSG_SPACE(4), socket.MSG_WAITALL)
    fds = []
    for level, kind, value in ancillary:
        if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
            received = array.array("i")
            received.frombytes(value[:len(value) - len(value) % received.itemsize])
            fds.extend(received)
    try:
        if len(data) != 64 or len(fds) != 1 or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise ConnectionError("invalid/truncated IPC fd transfer")
        os.set_inheritable(fds[0], False)
        remote = bytearray(data)
        struct.pack_into("i", remote, 0, fds[0])
        return bytes(remote), fds[0]
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise
