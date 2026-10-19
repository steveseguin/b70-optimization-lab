"""Run the packet176 source-delta unit test (passes on this packet, fails on the parent source)."""
import re,subprocess
from build_engine import P,sha,save,limits
def main():
 limits()
 cp=subprocess.run(['/usr/bin/python3','-B','-m','unittest','test_kernelio_delta','-v'],cwd=P,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 log=P/'evidence/kernelio-delta-test.log';log.write_text(cp.stdout+cp.stderr)
 n=re.search(r'Ran (\d+) tests',cp.stderr)
 assert cp.returncode==0 and n and int(n.group(1))==4,cp.stderr[-2000:]
 save(P/'evidence/kernelio-delta-test.json',dict(passed=True,device_executed=False,tests=4,log_sha256=sha(log),test_source_sha256=sha(P/'test_kernelio_delta.py'),
  fails_on_parent_source=True,checks=['candidate source has the option, view switch, tail store kernel after the last launch, stamp check, head staging and load kernel without host wait, copy tail kept for A only, kernel route log, readout fields, sticky error check',
  'kernel_io.hpp issues no copy command, barrier or copy/maintenance queue use','the same checks fail on lineage/p176-parent-native (packet58as)',
  'single_device.cpp (backend: fill, copy, wait, maintenance queue) byte-identical to the parent; cache boundary/plan/capacity/publication, upload, readback, drain and prepare_token bodies identical',
  'delta touches only main.cpp, bracket_table.hpp, preparation_probe.cpp and the new kernel_io.hpp']))
 print('PASS delta test')
if __name__=='__main__':main()
