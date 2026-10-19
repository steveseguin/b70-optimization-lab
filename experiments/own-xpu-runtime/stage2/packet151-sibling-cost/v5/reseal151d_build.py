"""One arbiter turn for the p151d production rebuild and numeric CPU gates."""
import contextlib,importlib.util,json,resource,sys
from pathlib import Path
import freeze_safe
freeze_safe.install()
import p151_v5_build_engine as build
import state_gate
from p151_v5_build_engine import P,LOCAL,ROOT,save,sha

def main():
 with state_gate.compiler_turn():
  build.compiler_turn=contextlib.nullcontext
  state_gate.compiler_turn=contextlib.nullcontext
  build.main()
  spec=importlib.util.spec_from_file_location('p151_pair',LOCAL/'pair_cpu.py');pair=importlib.util.module_from_spec(spec);spec.loader.exec_module(pair)
  pair.compiler_turn=contextlib.nullcontext;pair.main()
  path=P/'evidence/pair-cpu.json';row=json.loads(path.read_text())
  row['sources']={str((LOCAL/n).relative_to(ROOT)):sha(LOCAL/n) for n in ('pair_cpu.py','batch_fixture.cpp','batched_experts.hpp','batched_rows.hpp','production_rows.hpp','production_expert_chains.hpp','production65.hpp')}
  row['layout']='bundle8 halfcache gate/up and tile16 down';save(path,row)
  state_gate.main()
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
