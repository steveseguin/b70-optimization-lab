"""Use the repository CPU compiler coordinator; runtime imports impose no caps."""
import importlib.util
from pathlib import Path
path=Path(__file__).resolve().parents[2]/'ops/compile_turn.py'
spec=importlib.util.spec_from_file_location('p136_shared_compile_turn',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
turn=module.turn
