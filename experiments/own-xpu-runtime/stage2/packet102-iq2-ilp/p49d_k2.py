"""Retired record interface: packet102 qualifies only microbenchmarks and screens.

Copied legacy implementation retained under lineage-inputs/retired-record-tools.
"""
from record_scope import require_record_scope

def measured_coverage(root, selection):
    require_record_scope()
