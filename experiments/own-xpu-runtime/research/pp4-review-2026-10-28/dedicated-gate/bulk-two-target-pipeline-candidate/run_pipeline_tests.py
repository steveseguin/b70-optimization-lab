"""Apply candidate in a temporary overlay; never change the live package."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parent
runtime=root.parents[3];planning=runtime/'engine/planning';tools=runtime/'engine/tools'
for name,digest in json.loads((root/'base-pins.json').read_text()).items():
    if hashlib.sha256((runtime/name).read_bytes()).hexdigest()!=digest:
        raise SystemExit('Candidate base changed; review/rebase explicitly: '+name)
with tempfile.TemporaryDirectory(prefix='dedicated-pipeline-cpu-') as td:
    overlay=Path(td);destination=overlay/'engine/planning/rolling_provider'
    shutil.copytree(planning/'rolling_provider',destination,ignore=shutil.ignore_patterns('__pycache__'))
    overlaytools=overlay/'engine/tools';overlaytools.mkdir()
    for name in ('dedicated_provider_driver.py','dedicated_provider_lifecycle.py'):
        shutil.copy2(tools/name,overlaytools/name)
    subprocess.run(['patch','--batch','--forward','-p1','-i',str(root/'python.patch')],cwd=overlay,check=True,stdout=subprocess.DEVNULL)
    env=dict(os.environ,PYTHONPATH=os.pathsep.join(map(str,(destination.parent,overlaytools,planning,tools))))
    for name in ('test_pipeline.py','test_pipeline_plan.py'):
        subprocess.run([sys.executable,str(root/name)],env=env,check=True)
