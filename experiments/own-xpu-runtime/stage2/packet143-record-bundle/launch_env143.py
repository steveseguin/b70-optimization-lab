import importlib.util
from pathlib import Path
path=Path(__file__).resolve().parents[2]/'ops/launch_env.py'
spec=importlib.util.spec_from_file_location('shared_p143_launch_env',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
environment=module.environment
library_path=module.library_path
