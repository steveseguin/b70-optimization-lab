"""gemm_kernel device time grouped by the CPU op that launched it (via External id), per profiled step."""
import collections, json, sys
sys.path.insert(0, '/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('adt', '/home/steve/b70-optimization-lab/experiments/qwen38-27b-b70/scripts/analyze-decode-trace.py')
adt = importlib.util.module_from_spec(spec); spec.loader.exec_module(adt)
steps = int(sys.argv[2])
ops = collections.defaultdict(list)   # external id -> [(dur, name)] cpu ops
kern = []
for e in adt.load(sys.argv[1]):
    if e.get('ph') != 'X': continue
    a = e.get('args') or {}
    ext = a.get('External id')
    if e.get('cat') == 'cpu_op' and ext is not None:
        ops[ext].append((e.get('dur', 0), e['name']))
    elif e.get('cat') == 'kernel':
        kern.append((e['name'], e.get('dur', 0), ext, e.get('ts', 0)))
by = collections.defaultdict(lambda: [0.0, 0])
for name, dur, ext, ts in kern:
    if name != 'gemm_kernel': continue
    cands = ops.get(ext) or []
    # innermost op = shortest duration with this external id
    op = min(cands)[1] if cands else '?'
    outer = max(cands)[1] if cands else '?'
    k = op + ' <- ' + outer if outer != op else op
    by[k][0] += dur; by[k][1] += 1
for k, (d, n) in sorted(by.items(), key=lambda x: -x[1][0])[:20]:
    print('%8.2f ms/step %6.1f calls/step %7.1f us  %s' % (d / 1e3 / steps, n / steps, d / n, k[:150]))
