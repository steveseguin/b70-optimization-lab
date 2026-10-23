#!/usr/bin/env python3
"""Mocked admission regressions; no systemd, sudo, device or queue access."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
STUB='''#!/usr/bin/python3
import os,sys
args=sys.argv[1:];case=os.environ['CASE']
if 'is-active' in args:
 if case=='removed-transient':print('inactive');sys.exit(4)
 if case=='status-4-active':print('active');sys.exit(4)
 if case=='status-timeout':sys.exit(124)
 if case=='status-empty':sys.exit(1)
 if case=='status-mismatch':print('inactive');sys.exit(0)
 if case=='endpoint-active' and 'qwen38' in args[-1]:print('active');sys.exit(0)
 print('inactive');sys.exit(3)
if 'list-units' in args:
 if case=='list-error':sys.exit(1)
 if case=='codex-list-error' and 'codex-*' in args:sys.exit(1)
 if case=='show-error' and 'codex-*' in args:print('codex-test.service')
 sys.exit(0)
if 'show' in args:sys.exit(1)
sys.exit(99)
'''
class Launcher(unittest.TestCase):
 def test_admission(self):
  cases={'removed-transient':'MemAvailable','status-4-active':'cannot establish endpoint','clear':'MemAvailable','status-timeout':'cannot establish endpoint','status-empty':'cannot establish endpoint','status-mismatch':'cannot establish endpoint','endpoint-active':'owner endpoint','STOP-A':'incident latch','STOP-B':'incident latch','list-error':'lane/window discovery failed','codex-list-error':'codex discovery failed','show-error':'freezer state failed'}
  for name,want in cases.items():
   with self.subTest(case=name),tempfile.TemporaryDirectory(prefix='p196-launcher-') as t:
    t=Path(t);(t/'lane').mkdir();(t/'coord').mkdir();(t/'lane/PAUSE-B').touch()
    if name.startswith('STOP-'):(t/'lane'/name).touch()
    (t/'meminfo').write_text('MemAvailable: 1 kB\n');(t/'systemctl').write_text(STUB);(t/'systemctl').chmod(0o755)
    for tool in ('sudo','systemd-run'):
     f=t/tool;f.write_text('#!/bin/sh\necho UNAUTHORIZED >&2\nexit 99\n');f.chmod(0o755)
    env=dict(os.environ,PATH=str(t)+':/usr/bin:/bin',CASE=name,P196_LANE_DIR=str(t/'lane'),P196_COORD_DIR=str(t/'coord'),P196_MEMINFO=str(t/'meminfo'),FN=str(t/'logs'))
    cp=subprocess.run(['bash',str(HERE/'launch_chain.sh'),'--dry-run'],env=env,capture_output=True,text=True,timeout=20)
    self.assertEqual(cp.returncode,4,cp.stdout+cp.stderr);self.assertIn(want,cp.stdout);self.assertNotIn('UNAUTHORIZED',cp.stderr)
 def test_additive_transform_preserves_parent_and_rejects_drift(self):
  import derive_diet_chain as d
  p=json.loads((d.P0/'runtime-selection.json').read_text())
  args=[(d.P0/n).read_text() for n in ('suite_driver.py','composition.py','views.py')]
  suite,composition,views,selection=d.additive_sources(*args,p,d.FLAGS)
  self.assertEqual(selection['cache_cap'],'max23');self.assertEqual(selection['cache_bytes'],23049601024)
  self.assertEqual(selection['chain_flags'],d.FLAGS)
  self.assertLess(suite.index('GENERATED_CHAIN_FLAGS = '),suite.index("if __name__=='__main__':"))
  for changed in (dict(p,cache_cap='max'),dict(p,cache_bytes=1),dict(p,chain_flags={'--wait-policy':'sleep','--foreground-io':'kernel'})):
   with self.assertRaises(AssertionError):d.additive_sources(*args,changed,d.FLAGS)
 def test_no_privilege_during_dryrun(self):
  s=(HERE/'launch_chain.sh').read_text();self.assertIn('if [ $DRY = 1 ]; then\n  log "CPU dry run',s);self.assertIn('cpu "$O/device_inventory.py"',s)
if __name__=='__main__':unittest.main()
