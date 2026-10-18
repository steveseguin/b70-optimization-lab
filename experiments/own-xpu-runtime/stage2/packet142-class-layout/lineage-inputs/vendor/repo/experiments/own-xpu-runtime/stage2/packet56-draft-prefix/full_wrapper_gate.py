#!/usr/bin/env python3
"""Compatibility entry for the current packet45 full coordinator rehearsal.

The inherited packet40 harness used context256, dispatch-p38, and obsolete
capture/seal fields. The maintained chain is defined only by coordinator_windows.sh.
"""
from coordinator_cpu_gate import run
if __name__=='__main__':run()
