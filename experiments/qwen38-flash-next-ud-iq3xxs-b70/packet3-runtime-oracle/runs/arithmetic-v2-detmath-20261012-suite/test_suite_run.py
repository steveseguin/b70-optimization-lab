"""CPU supervisor tests; no numerical or device binary is executed."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import suite_run as run

class SupervisorChecks(unittest.TestCase):
    def test_disk_floor(self):
        for free,passes in ((7999999999,False),(8000000000,True)):
            text=f"Filesystem 1B-blocks Used Available Use% Mounted on\n/dev/mock 10000000000 1 {free} 20% /\n"
            with patch.object(run.subprocess,'check_output',return_value=text):
                if passes:run.disk_guard()
                else:
                    with self.assertRaisesRegex(RuntimeError,'less than 8 GB'):run.disk_guard()

    def test_parallel_parent_seals_and_publishes(self):
        sealed=[];published=[];parent=os.getpid()
        def worker(row,*args,**kwargs):
            assert kwargs['defer_finalize']
            assert os.getpid()!=parent
            return (row['id'],os.getpid())
        def finalize(prompt,pid):
            self.assertEqual(os.getpid(),parent)
            self.assertNotEqual(pid,parent)
            sealed.append(prompt)
        with patch.object(run,'run_prompt',worker),patch.object(run,'finalize_prompt',finalize),patch.object(run,'publish',published.append),patch.object(run,'disk_guard'):
            run.remaining_parallel([{'id':str(i)} for i in range(5)],{},None,[],True)
        self.assertEqual(set(sealed),set(map(str,range(5))))
        self.assertEqual(sealed,published)

    def test_failed_worker_stops(self):
        def worker(*args,**kwargs):raise ValueError('mock failure')
        with patch.object(run,'run_prompt',worker),patch.object(run,'disk_guard'):
            with self.assertRaisesRegex(RuntimeError,'mock failure'):
                run.remaining_parallel([{'id':'one'}],{},None,[],False)

    def test_atomic_json(self):
        with tempfile.TemporaryDirectory(prefix='.test.partial-',dir=run.HERE) as d:
            path=Path(d)/'value.json';run.save(path,{'ok':True})
            self.assertEqual(run.read(path),{'ok':True})
            self.assertEqual(list(Path(d).iterdir()),[path])

if __name__=='__main__':unittest.main()
