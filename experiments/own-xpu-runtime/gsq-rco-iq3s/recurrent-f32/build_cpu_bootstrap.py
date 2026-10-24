#!/usr/bin/env python3
"""Additive bootstrap for the unchanged failed driver; root-operated only."""
from pathlib import Path
import hashlib,importlib.util,runpy,sys
P=Path(__file__).resolve().parent
LIMITS=P.parent/'dense-packed-block/build_cpu.py'
DRIVER=P/'build_cpu.py'
EXPECTED={
'/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/dense-packed-block/build_cpu.py':'b4bd96769e9009d5c75492d4e29099adea1688458d43c01a161f30ebecc9382d',
'/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/recurrent-f32/build_cpu.py':'07f557f28b630efa5da8461818f88617d17ac75fd01cb0fde591836dcddee5b5'
}
if __name__=='__main__':
 for name,digest in EXPECTED.items():
  assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
 assert not (P/'evidence/cpu-proof.json').exists(),'no repeated passing proof'
 spec=importlib.util.spec_from_file_location('build_engine',LIMITS)
 module=importlib.util.module_from_spec(spec);sys.modules['build_engine']=module;spec.loader.exec_module(module)
 # compile_turn imports this exact existing bounded limits() callback.
 runpy.run_path(str(DRIVER),run_name='__main__')
