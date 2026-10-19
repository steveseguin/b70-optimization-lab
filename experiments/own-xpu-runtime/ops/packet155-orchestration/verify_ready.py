"""Fail-closed stop marker: CPU preparation was interrupted by the disk floor.

This is deliberately not the requested completed bracket verifier. Do not replace
this refusal with a stored pass flag. Complete all CPU gates and recompute the
five-view packet153 decision before any coordinator admission.
"""
import json

def verify():
    raise ValueError('packet155 incomplete: root free space crossed the 30 GB stop floor; CPU gates and bracket verifier are unfinished')

if __name__ == '__main__':
    print(json.dumps(dict(ready_for_device=False,cpu_preparation_ready=False,
        reason='Disk stop; launch refused. Complete CPU gates and bracket verifier first.')))
    raise SystemExit(1)
