"""CPU/device placement and inherited serialized graceful teardown."""
import os
from pathlib import Path
from common import require
CPU_CORES=set(range(8,16))|set(range(24,32))
LANES={'A':dict(cores=[0,1,2,3,16,17,18,19],cards=[0,1]),'B':dict(cores=[4,5,6,7,20,21,22,23],cards=[2,3])}
def cpu_gate():require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=CPU_CORES,'CPU preparation needs nice19 and assigned cores')
def lane_gate(lane):require(os.getpriority(os.PRIO_PROCESS,0)==0 and set(os.sched_getaffinity(0))==set(LANES[lane]['cores']),'exact lane timing affinity/nice required')
