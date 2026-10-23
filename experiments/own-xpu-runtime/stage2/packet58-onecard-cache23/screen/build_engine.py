"""CPU helper adapter; rebuilding is owned by the packet root."""
import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[4]
spec=importlib.util.spec_from_file_location('packet58aj_build',P.parent/'build_engine.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
B=P/'build';BASE=M.BASE
sha=M.sha;save=M.save;limits=M.limits;compiler_turn=M.compiler_turn
