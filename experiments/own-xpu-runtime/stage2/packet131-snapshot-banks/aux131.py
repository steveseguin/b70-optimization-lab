"""Bounded CPU auxiliary gates while state fixtures run; compilers stay serial."""
import resource
from build131 import cpu_main
def main():
 import extra131
 extra131.main()
 # Full K2 CPU startup needs more than this auxiliary cap. qualify131 runs
 # startup131 only after all four concurrent state workers have exited.
if __name__=='__main__':
 cpu_main()
 # Four state workers reserve at most 6 GiB. Bound each auxiliary CPU process
 # at 1.5 GiB and run one auxiliary operation at a time. No device exec here.
 resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2));main()
