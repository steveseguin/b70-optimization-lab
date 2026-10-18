#!/usr/bin/env python3
"""Unchanged 58g host/VRAM bounds, with tile16-only whole-host exclusion."""
import importlib.util
import json
from pathlib import Path
import memory_plan as M
import onecard_admission as A
import queue_runner as Q
from startup_gate import sha

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def main():
    f = P.parent/'packet58g-onecard/memory_plan.py'
    spec = importlib.util.spec_from_file_location('frozen58g_memory', f)
    parent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parent)
    rows = []
    for window in Q.ORDER:
        budget = M.window_plan(window)
        assert parent.window_plan(window) == budget
        assert A.window_scope(window) == 'whole-host'
        required = budget['host_required_available_bytes']
        assert M.admit({'MemAvailable':required}, budget)['passed']
        try:
            M.admit({'MemAvailable':required-1}, budget)
        except ValueError:
            pass
        else:
            raise AssertionError('short host budget admitted')
        assert budget['device_margin_bytes'] >= 0 and budget['kv_dtype'] == 'BF16'
        rows.append(dict(window=window, scope='whole-host', host_required_available_bytes=required,
            peak_host_bound_bytes=required-M.HOST_RESERVE, host_reserve_bytes=M.HOST_RESERVE,
            device_owned_bound_bytes=budget['device_owned_bound_bytes'], device_margin_bytes=budget['device_margin_bytes'],
            arena_limit_bytes=budget['arena_limit_bytes'], equal_58g=True, shortage_refused=True))
    paths = (Path(__file__), P/'memory_plan.py', P/'onecard_admission.py', P/'lane_admission.py', f)
    result = dict(passed=True, device_executed=False, model_reads=False, records=rows,
        sources={str(x.relative_to(ROOT)):sha(x) for x in paths},
        warning='No live host admission is claimed. All seven windows exclude lane B; WS128 needs 118308908048 bytes available.')
    (P/'evidence/budget-cpu.json').write_text(json.dumps(result,indent=2)+'\n')
    print('7 unchanged 58g budgets, whole-host scopes and shortage refusals PASS')


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
