"""Imported only after explicit admission in the matching container runtime."""
import triton
import triton.language as tl


@triton.jit
def indirect_gather(resident_base, offset_table, output):
    row = tl.program_id(0)
    col = tl.arange(0, 4096).to(tl.int64)
    delta = tl.load(offset_table + row)
    values = tl.load(resident_base + delta + col)
    tl.store(output + row * 4096 + col, values)


@triton.jit
def direct_gather(resident_base, host_uva_base, local_rows, host_selector, output):
    row = tl.program_id(0)
    col = tl.arange(0, 4096).to(tl.int64)
    local_row = tl.load(local_rows + row).to(tl.int64)
    use_host = tl.load(host_selector + row) != 0
    base = tl.where(use_host, host_uva_base, resident_base)
    values = tl.load(base + local_row * 4096 + col)
    tl.store(output + row * 4096 + col, values)
