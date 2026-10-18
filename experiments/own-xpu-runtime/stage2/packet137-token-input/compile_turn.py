import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'ops/compile_turn.py'
s=importlib.util.spec_from_file_location('p137_compile_admission',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
turn=m.turn
