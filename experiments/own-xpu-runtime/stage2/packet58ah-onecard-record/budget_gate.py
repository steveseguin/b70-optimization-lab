"""Seven windows use frozen 58u measured admission plus 58v async allowance."""
import json,resource
from pathlib import Path
import memory_plan as M
import onecard_admission as A
import queue_runner as Q
from seal import sha
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def main():
    rows=[]
    for window in Q.ORDER:
        budget=M.window_plan(window);required=budget['host_required_available_bytes']
        assert A.window_scope(window)=='whole-host' and M.HOST_RESERVE==8*1024**3
        assert required==(12*1024**3 if window.startswith('K1') else 98990252032)
        assert M.admit({'MemAvailable':required},budget)['passed']
        try:M.admit({'MemAvailable':required-1,'SwapFree':10**15},budget)
        except ValueError:pass
        else:raise AssertionError('shortage admitted')
        assert budget['device_margin_bytes']>=0 and budget['kv_dtype']=='BF16'
        assert M.window_plan(window,dict(peak_shadow_bytes=0))==budget
        rows.append(dict(window=window,scope='whole-host',required_available_bytes=required,reserve_bytes=M.HOST_RESERVE,shortage_refused=True,observations_cannot_lower_bound=True,plan=budget))
    sources={str(f.relative_to(ROOT)):sha(f) for f in (Path(__file__),P/'memory_plan.py',P/'legacy_memory_plan.py',P/'host-admission/seal.json')}
    (P/'evidence/budget-cpu.json').write_text(json.dumps(dict(passed=True,device_executed=False,records=rows,sources=sources),indent=2)+'\n')
    print('7 measured host budgets and one-byte shortage refusals PASS')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
