"""Run actual-family prepared issue benchmark, CPU mock only."""
from pathlib import Path
import prepared_host_benchmark
if __name__=='__main__':
 prepared_host_benchmark.main()
 p=Path(__file__).resolve().parent
 (p/'host-issue-benchmark.json').write_bytes((p/'prepared-host-benchmark.json').read_bytes())
