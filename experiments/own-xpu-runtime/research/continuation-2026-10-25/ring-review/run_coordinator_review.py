#!/usr/bin/env python3
"""Additional deterministic CPU event-order/request-shape review; no device calls."""
import hashlib
import json
from pathlib import Path
import random
import sys

OWNRT=Path(__file__).resolve().parents[3]
PLANNING=OWNRT/'engine/planning'
sys.path.insert(0,str(PLANNING))
from test_ring_coordinator import fixture,Publisher,run,RingCoordinatorTests


def main():
    randomizer=random.Random(919919)
    check=RingCoordinatorTests()
    counts={2:0,4:0,6:0}
    for index in range(500):
        count=randomizer.choice([2,4,6]);length=randomizer.randint(1,40)
        maximum=randomizer.randint(1,40)
        prompt=[randomizer.randrange(97) for _ in range(length)]
        eos=(96,randomizer.randrange(96))
        misses=[p for p in range(length,length+maximum) if randomizer.randrange(2)]
        coordinator,workers=fixture(count,Publisher(misses,fresh_disagree=bool(index%2)),
            prompt=prompt,maximum=maximum,eos=eos,wire=randomizer.randrange(999))
        run(coordinator,workers,index)
        check.check_exact(coordinator,workers,prompt,maximum,eos)
        counts[count]+=1
    sources={str(p.relative_to(OWNRT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
        PLANNING/name for name in ('ring_coordinator.py','test_ring_coordinator.py','ring_contract.py','wavefront_ring.py')]}
    sources[str(Path(__file__).resolve().relative_to(OWNRT))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    print(json.dumps(dict(schema='ownrt.independent-ring-coordinator-cpu-review.v1',passed=True,
        cases=500,seed=919919,stage_cases=counts,sources=sources,
        scope='Exact synthetic Ring physical state and outputs versus sequential gold with randomized reply ordering, prompt/cap/EOS/miss shapes and immutable fresh proposal disagreement. Not native transport, actual model, GPU concurrency or performance qualification.'),indent=2))


if __name__=='__main__':main()
