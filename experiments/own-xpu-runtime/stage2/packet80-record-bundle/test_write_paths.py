"""CPU-only scratch escape and KD external-build regression checks."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import write_paths as w
import draft_window


class Paths(unittest.TestCase):
    def test_external_build_kd_is_admitted_and_archived_there(self):
        with tempfile.TemporaryDirectory() as d:
            build=Path(d)/'external-build'; out=build/'chain/KD'
            root=out/'host-reference';root.mkdir(parents=True)
            (root/'receipt.json').write_text('{}')
            self.assertEqual(w.kd_scratch(out,build),root)
            with patch('storage.B',build), patch('storage.archive_files',return_value={'passed':True}) as archive:
                self.assertEqual(draft_window.archive_host_reference(out),{'passed':True})
                self.assertEqual(archive.call_args.args[1],out/'host-reference.jsonl.gz')

    def test_outside_and_symlink_ancestor_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'build'; root.mkdir(); outside=Path(d)/'other';outside.mkdir()
            for target in (outside,root):
                link=root/'link';link.symlink_to(target,target_is_directory=True)
                with self.assertRaises(ValueError):w.inside(link/'future',root)
                link.unlink()
            with self.assertRaises(ValueError):w.kd_scratch(outside/'KD',root)

    def test_existing_tree_symlink_and_external_hardlink_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'build';root.mkdir();secret=Path(d)/'outside';secret.write_text('sentinel')
            (root/'nested').mkdir();link=root/'nested/file';link.symlink_to(secret)
            with self.assertRaises(ValueError):w.inside(root,root,tree=True)
            link.unlink();os.link(secret,link)
            with self.assertRaisesRegex(ValueError,'hardlink'):w.inside(root,root,tree=True)
            self.assertEqual(secret.read_text(),'sentinel')

    def test_internal_fixture_hardlinks_are_contained(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'first').write_text('x');os.link(root/'first',root/'second')
            self.assertEqual(w.inside(root,root,tree=True),root)

    def test_all_windows_roles_and_legacy_wrong_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);packet=root/'packet61-spin-hcfusion';(packet/'build').mkdir(parents=True)
            build=root/'external';build.mkdir()
            rows, errors=w.inventory(packet,build,build/'new',('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128'),['prose'])
            self.assertEqual(len(errors),3)
            self.assertTrue(all('KD/host-reference' in e for e in errors))
            self.assertTrue({'owner/fixture scratch','receipt/retention','driver cache','suite input/fixture/state retention'} <= {r['role'] for r in rows})
