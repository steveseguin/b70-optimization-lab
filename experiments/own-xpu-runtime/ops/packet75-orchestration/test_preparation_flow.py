"""Preparation state transitions with synthetic decisions; never launches."""
import contextlib,io,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import orchestrate as o
from test_orchestrate import packet

class Preparation(unittest.TestCase):
    def exercise(self, p73, p74, failure=None):
        with tempfile.TemporaryDirectory(prefix='cpu-flow-',dir=o.O) as folder:
            dest=Path(folder);calls=[]
            (dest/'device-entry.sh').write_bytes((o.O/'device-entry.sh').read_bytes())
            def screen(argv,**kwargs):
                self.assertEqual(kwargs['stdin'],subprocess.DEVNULL)
                self.assertEqual(Path(argv[-2]).name,'read_screens.py')
                return subprocess.CompletedProcess(argv,0,json.dumps(p73 if argv[-1]=='73' else p74),'')
            def check(name,argv):
                calls.append(name)
                if name==failure:raise ValueError('injected '+name+' failure')
                (dest/(name+'.log')).write_text('CPU synthetic precheck '+name+'\n')
            with patch.object(o,'O',dest),patch.object(o.subprocess,'run',screen),patch.object(o,'run',check),patch('sys.argv',['orchestrate.py']),contextlib.redirect_stdout(io.StringIO()):
                rc=o.main()
            return rc,json.loads((dest/'ready.json').read_text()),calls
    def test_all_prechecks_required_in_order(self):
        rc,row,calls=self.exercise(packet('combined'),packet('combined'))
        self.assertEqual(rc,0);self.assertTrue(row['ready']);self.assertFalse(row['device_executed'])
        self.assertEqual(calls,['reseal','seal','inputs','storage','plans','queue-plan'])
        self.assertEqual(set(row['checks']),set(calls[1:]))
    def test_failure_never_marks_ready(self):
        for name in ('reseal','seal','inputs','storage','plans','queue-plan'):
            rc,row,calls=self.exercise(packet('combined'),packet('combined'),name)
            self.assertEqual(rc,2);self.assertFalse(row['ready']);self.assertEqual(calls[-1],name)
    def test_pending_never_reseals(self):
        rc,row,calls=self.exercise(packet('combined','pending'),packet('combined'))
        self.assertEqual(rc,2);self.assertFalse(row['ready']);self.assertEqual(calls,[])
    def test_no_change_never_reseals(self):
        rc,row,calls=self.exercise(packet('production','no-winner'),packet('production','no-winner'))
        self.assertEqual(rc,2);self.assertFalse(row['ready']);self.assertEqual(calls,[])
    def test_single_packet_flows(self):
        for left,right in ((packet('hc-wide'),packet('production','no-winner')),(packet('production','no-winner'),packet('head-packed'))):
            rc,row,calls=self.exercise(left,right)
            self.assertEqual(rc,0);self.assertTrue(row['ready']);self.assertEqual(calls[-1],'queue-plan')
if __name__=='__main__':unittest.main()
