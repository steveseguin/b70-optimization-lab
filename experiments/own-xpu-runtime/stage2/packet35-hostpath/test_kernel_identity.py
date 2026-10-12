"""Negative-control CPU tests for the SPIR-V byte/name identity parser."""
import json,struct,tempfile
from pathlib import Path
from kernel_identity import BASE,HERE,spirv,offload_section

def main():
 original=BASE/'build/device/own-rt-iq3';before=spirv(original);data=bytearray(original.read_bytes());section=offload_section(data)
 first=data.find(section);assert first>=0
 start=first+section.find(b'\x03\x02\x23\x07');i=start+20
 while True:
  word=struct.unpack_from('<I',data,i)[0];count,op=word>>16,word&65535
  assert count
  if op==43 and count>=4: # OpConstant literal: keep kernel names unchanged.
   data[i+12]^=1;break
  i+=count*4
 scratch=HERE/'build';scratch.mkdir(exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='identity-negative-',dir=scratch) as d:
  p=Path(d)/'mutated.elf';p.write_bytes(data);after=spirv(p)
  assert before['kernel_names']==after['kernel_names']
  assert before['modules']!=after['modules']
  p.write_bytes(b'not an ELF executable')
  try:spirv(p)
  except AssertionError:pass
  else:raise AssertionError('non-ELF accepted')
 r=dict(passed=True,device_executed=False,checks=3,baseline_modules=len(before['modules']),baseline_entry_points=len(before['kernel_names']),same_names_do_not_hide_constant_mutation=True,non_elf_rejected=True)
 (HERE/'kernel-identity-tests.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
if __name__=='__main__':main()
