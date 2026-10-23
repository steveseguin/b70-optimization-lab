"""Private, source-pinned p196 safety import for the additive p201 driver."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def verify():
    pins=json.loads((HERE/'helper-pins.json').read_text())
    if pins.get('operational_entrypoint_enabled') is not False:
        raise RuntimeError('frozen scaffold scope changed')
    for name,digest in pins['files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('frozen helper changed: '+name)
    return pins


pins=verify()
PARENT=ROOT/pins['safety_parent']
spec=importlib.util.spec_from_file_location('_p201_driver_owned_safety',PARENT/'safety.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)
S.UNIT='packet201-streaming-serving-a'
RESTORE=PARENT/'restore.py'
