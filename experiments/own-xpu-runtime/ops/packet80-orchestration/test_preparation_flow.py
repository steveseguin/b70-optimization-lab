"""One-shot transitions and every precheck; all external/native actions mocked."""
import contextlib,io,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import orchestrate as o
from test_orchestrate import packet

class Preparation(unittest.TestCase):
    def exercise(self,screens,failure=None):
        with tempfile.TemporaryDirectory(prefix='cpu-flow-',dir=o.O) as folder:
            dest=Path(folder);calls=[]
            (dest/'device-entry.sh').write_bytes((o.O/'device-entry.sh').read_bytes())
            def screen(argv,**kwargs):
                self.assertEqual(kwargs['stdin'],subprocess.DEVNULL)
                self.assertEqual(Path(argv[-2]).name,'read_screens.py')
                return subprocess.CompletedProcess(argv,0,json.dumps(screens.get(argv[-1],packet('production','pending'))),'')
            def check(name,argv):
                calls.append(name)
                if name==failure:raise ValueError('injected '+name+' failure')
                (dest/(name+'.log')).write_text('CPU synthetic precheck '+name+'\n')
            with patch.object(o,'sha',return_value='a'*64),patch.object(o,'O',dest),patch.object(o.subprocess,'run',screen),patch.object(o,'run',check),patch('sys.argv',['orchestrate.py']),contextlib.redirect_stdout(io.StringIO()):
                rc=o.main()
            return rc,json.loads((dest/'ready.json').read_text()),calls
    def test_checks_required(self):
        rc,row,calls=self.exercise({'73':packet('hc-wide')})
        self.assertEqual(rc,0);self.assertTrue(row['ready']);self.assertFalse(row['device_executed'])
        self.assertEqual(calls,['reseal','cpu-dry-run','seal','inputs','storage','plans','queue-plan'])
    def test_each_failure_blocks(self):
        for name in ('reseal','cpu-dry-run','seal','inputs','storage','plans','queue-plan'):
            rc,row,calls=self.exercise({'76':packet('ordered')},name)
            self.assertEqual(rc,2);self.assertFalse(row['ready']);self.assertEqual(calls[-1],name)
    def test_all_pending_does_not_reseal(self):
        rc,row,calls=self.exercise({})
        self.assertEqual(rc,2);self.assertFalse(row['ready']);self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
