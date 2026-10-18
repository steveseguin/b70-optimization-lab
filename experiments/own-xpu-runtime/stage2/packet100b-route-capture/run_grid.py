"""CPU-only --plan; packet100 grids with the p100b qualification provider.

The frozen packet100 driver, all its seals, exactness checks, B/A bracket
selection and candidate binaries remain verified verbatim. Only the input
qualification provider is replaced in this process, before the driver imports.
"""
import argparse,importlib.util,sys
from pathlib import Path
P=Path(__file__).resolve().parent
BASE=P.parent/'packet100-down-locality'

def main():
 # Explicit declaration permits lanequeue's AST-based CPU-plan check.
 parser=argparse.ArgumentParser(add_help=False)
 parser.add_argument('--plan',action='store_true')
 args,_=parser.parse_known_args()
 from capture_identity import verify
 verify()
 from qualification import require_qualified
 spec=importlib.util.spec_from_file_location('screen_jobs',BASE/'screen_jobs.py')
 jobs=importlib.util.module_from_spec(spec);sys.modules['screen_jobs']=jobs;spec.loader.exec_module(jobs)
 jobs.qualified_candidates=lambda:require_qualified(P)
 # Parent bootstrap must resolve from the frozen packet100 root.
 sys.path.insert(0,str(BASE))
 spec=importlib.util.spec_from_file_location('p100_grid_driver',BASE/'run_screens.py')
 driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
 return driver.main()

if __name__=='__main__':raise SystemExit(main())
