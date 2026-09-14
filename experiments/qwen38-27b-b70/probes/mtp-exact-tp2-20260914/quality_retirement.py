"""Inactive coordinated retirement helper; CPU-tested, never GPU-qualified.

For a mutually acknowledged quality rejection AFTER every local copy and kernel
event completed. Never use this for a device fault, timeout, poisoned channel,
unknown peer status or unfinished work. See quality-retirement.patch.
"""
import os


def retire_completed_allocations(native, channel, queue, peer, remote_fd,
                                 export_handle, output, local, rows, *,
                                 completed_and_agreed=False, close_fd=os.close):
    if not completed_and_agreed or native.poisoned or channel.poisoned:
        raise RuntimeError("retirement admission requires completed work and healthy peer agreement")
    if channel.phase != "READY":
        raise RuntimeError("retirement admission requires completed protocol generation")
    # No new device kernel, copy or wait is submitted here. These are CPU
    # rendezvous and release calls; the outer controller still bounds teardown.
    channel.exchange("READY", retiring_rows=rows)
    channel.exchange("COPIED", retiring_rows=rows)
    native.call("close", queue, peer)
    close_fd(remote_fd)
    channel.exchange("READY", importers_closed=rows)
    channel.exchange("COPIED", importers_closed=rows)
    # Only after BOTH mappings close may either exporter release storage.
    native.call("put_export", queue, export_handle)
    native.call("free", queue, output)
    native.call("free", queue, local)
