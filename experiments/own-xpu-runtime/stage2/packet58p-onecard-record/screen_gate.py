#!/usr/bin/env python3
"""Read frozen 58n with its own import namespace; never write its evidence."""
import json
import importlib.abc
import importlib.util
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
K = P.parent/'packet58n-onecard-loo'
# Execute private frozen source bytes. __file__ retains the original location
# solely to resolve 58n's original evidence and sealed input paths. No writes or
# native calls are made by this reader. Parent results are live readiness inputs,
# never part of 58p's immutable build seal.
class FrozenReader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        file = P/'screen-reader'/(fullname+'.py')
        if '.' not in fullname and file.is_file():
            return importlib.util.spec_from_loader(fullname, self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__name__+'.py'
        module.__file__ = str(K/name)
        exec(compile((P/'screen-reader'/name).read_bytes(), str(K/name), 'exec'), module.__dict__)


sys.meta_path.insert(0, FrozenReader())
import compare_screen as C
import queue_runner as Q


def main():
    C.W.build_gate()
    rows, pins, boots = [], {}, []
    for name, view in Q.STAGES:
        row, sources, boot = C.verify_arm(Q.ROOT/name, view)
        requests = row['requests']
        C.W.require(len(requests) == 12 and all(r.get('passed') is True and r.get('exact_oracle') is True
                    and len(r['tokens']) == 128 for r in requests), '12/12 exact screen required')
        rows.append(row)
        pins.update(sources)
        boots.append(boot)
    C.W.require(len(set(boots)) == 1, 'screen boot changed')
    C.W.require(len({tuple(x) for r in rows for x in r['owners']}) == 9, 'screen owners reused')
    decision = C.decision(rows)
    print(json.dumps(dict(passed=True, device_executed=False, rows=rows, sources=pins,
                         boot_id=boots[0], inherited_decision=decision,
                         screen_build_sha256=C.D.sha(K/'build-receipt.json'),
                         screen_selection_sha256=C.digest('down-tile16'),
                         screen_native_artifacts={n:h for n,h in C.D.read(K/'build-receipt.json')['artifacts'].items()
                                                  if n.startswith('build/device/')})))


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
