"""Recognise the known model-load GPU fault and decide whether one bounded recovery is allowed. CPU only.

The fault (notes/2026-10-04-gpu-fault-mtp-start.md): while a server loads its weights the copy engine reads a small
buffer at GPU address 0x800400200000 that is not mapped at that instant, the kernel answers -EINVAL and resets the
engine. Four saved incidents, both cards, two kernels: always this address range, always `bcs`, always before the
server is ready, so no request and no measurement is ever involved.

The owner's rule (AGENTS.md): one fault does not end the session; stop, run one health probe, carry on if it passes;
a second fault on the same boot stops GPU work. `decide` applies exactly that, and only to this signature.
"""
import re

LOAD_FAULT_RANGE = (0x800400200000, 0x800400240000)
RECORD = re.compile(r'ASID: (\d+)\s+Faulted Address: (0x[0-9a-fA-F]+)\s+FaultType: (\d+)\s+AccessType: (\d+)\s+'
                    r'FaultLevel: (\d+)\s+EngineClass: \d+ (\w+)')


def parse_records(text):
    """Page-fault records from `journalctl -k -o cat` text (each record is one multi-line kernel message)."""
    return [{'asid': int(m[1]), 'address': int(m[2], 16), 'fault_type': int(m[3]), 'access': int(m[4]),
             'level': int(m[5]), 'engine': m[6]} for m in RECORD.finditer(text)]


def is_known_load_fault(records):
    low, high = LOAD_FAULT_RANGE
    return bool(records) and all(r['engine'] == 'bcs' and r['access'] == 0 and low <= r['address'] < high for r in records)


def decide(server_ready, records_since_start, fault_lines_since_start, fault_lines_this_boot):
    """Return ('recover' | 'halt', reason). Lines are kernel-log fault lines; records are parse_records() output."""
    if server_ready:
        return 'halt', 'the server was already serving; only a fault during model load is recoverable'
    if fault_lines_this_boot > fault_lines_since_start:
        return 'halt', 'an earlier GPU fault is already in this boot\'s log: second fault on the boot'
    if not is_known_load_fault(records_since_start):
        return 'halt', 'not the known model-load signature (copy-engine reads at 0x800400200000)'
    return 'recover', 'known model-load fault, first fault on this boot'
