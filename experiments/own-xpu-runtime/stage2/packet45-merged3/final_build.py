import sys,subprocess,os
from pathlib import Path
p=Path(__file__).resolve().parent
for mode in sys.argv[1:]:
 subprocess.run(['nice','-n','19','ionice','-c','3','df','-B1','/'],check=True)
 subprocess.run(['nice','-n','19','ionice','-c','3',sys.executable,'-B',str(p/'build.py'),mode],check=True)
