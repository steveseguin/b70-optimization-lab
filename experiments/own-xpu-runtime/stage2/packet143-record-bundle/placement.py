"""Exact selected composition and unchanged TP2 memory gate."""
import importlib.util,json
from pathlib import Path
from types import SimpleNamespace
from compositions import P,ROOT,read,sha

def admission_gate(root):
 path=P/'memory_gate.py';spec=importlib.util.spec_from_file_location('p143_memory_gate',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return path,m

def admit(root,seal,receipt,dispatch,name):
 from compositions import native,validate
 assert name=='1' and root.parent==P/'selections'
 selection=read(root/'composition.json');validate(selection);assert read(root/'selection.json')==native(selection)
 path,gate=admission_gate(root);configuration=gate.configuration(read(root/'memory-plan.json'),4096,1,0)
 return dict(name='1',draft_rank=1,target_split=0,layer_boundary=24,target_layers=[24,24],context=4096,memory_admitted=True,supported=True,reason='fixed bundle8 plus drained class relocation, unchanged arena and reserve',configuration=configuration,memory_gate=str(path),memory_gate_sha256=sha(path))
def verify_identity(identity):
 from common import sealed
 args=SimpleNamespace(lineage=Path(identity['lineage']),seal=Path(identity['seal']),binary=Path(identity['binary']),dispatch=Path(identity['dispatch']),profile=identity['profile'],timing=identity['timing'],placement='1')
 expected=sealed(args);assert all(identity.get(k)==v for k,v in expected.items()),'smoke identity changed'
 return expected['placement'],admission_gate(args.lineage)[1]
