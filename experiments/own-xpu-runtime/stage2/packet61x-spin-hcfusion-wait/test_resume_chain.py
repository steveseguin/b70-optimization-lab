"""CPU-only resume identity, copying and tamper checks; no real launches."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import resume_chain as r
import queue_runner as q
import window
from storage import digest


class Resume(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name); self.p=root/'a/b/c/packet';self.p.mkdir(parents=True)
        self.build=root/'output';self.source=self.build/'old';self.dest=self.build/'new'
        (self.p/'build/device').mkdir(parents=True);(self.p/'build/device/engine').write_text('engine')
        (self.p/'screen-seal.json').write_text('screen');(self.p/'dispatch-p45.json').write_text('dispatch')
        artifacts={'device/engine':digest(self.p/'build/device/engine')}
        old=dict(sources={},artifacts_sha256=artifacts,screen_seal_sha256=digest(self.p/'screen-seal.json'))
        (self.p/'old-seal.json').write_text(json.dumps(old));old_hash=digest(self.p/'old-seal.json')
        for name in r.EARLY:
            folder=self.source/name;folder.mkdir(parents=True)
            row=dict(window=name,passed=True,qualifying=True,device_executed=True,card=0,context=4096,draft_rank=1,target_split=23,
                     boot_id='boot',build_receipt_sha256=old_hash,screen_seal_sha256=old['screen_seal_sha256'],artifacts_sha256=artifacts,
                     dispatch_sha256=digest(self.p/'dispatch-p45.json'),receipts={})
            (folder/'window.json').write_text(json.dumps(row))
        (self.source/'K2/run0').mkdir();(self.source/'K2/run0/dispatch-measured.json').write_text('dispatch')
        pin=dict(source=str(self.source),windows=list(r.EARLY),boot_id='boot',old_seal_path='old-seal.json',old_seal_sha256=old_hash,
                 screen_seal_sha256=old['screen_seal_sha256'],artifacts_sha256=artifacts,dispatch_sha256=digest(self.p/'dispatch-p45.json'),
                 candidate_dispatch_sha256=digest(self.p/'dispatch-p45.json'),files=r.file_inventory(self.source))
        (self.p/'resume-pins.json').write_text(json.dumps(pin))
        current=copy.deepcopy(old);current['sources'][str((self.p/'resume-pins.json').relative_to(self.p.parents[3]))]=digest(self.p/'resume-pins.json')
        (self.p/'build-receipt.json').write_text(json.dumps(current))
        for target,value in [('P',self.p),('B',self.build),('REGISTERED_CHAIN','new')]:
            m=patch.object(r,target,value);m.start();self.addCleanup(m.stop)
        for target,kwargs in [('boot_id',dict(return_value='boot')),('admit',dict(return_value={}))]:
            m=patch.object(r,target,**kwargs);m.start();self.addCleanup(m.stop)
        m=patch.object(window,'prerequisites',side_effect=lambda path,*args:json.loads(path.read_text()));m.start();self.addCleanup(m.stop)

    def test_copy_exact_bytes_and_fresh_models(self):
        before=r.file_inventory(self.source);manifest=r.prepare(self.source,self.dest)
        self.assertEqual(r.file_inventory(self.dest),before)
        self.assertEqual(r.file_inventory(self.source),before)
        self.assertFalse(any((self.dest/n).exists() for n in r.LATE))
        self.assertNotEqual((self.dest/'K0/window.json').stat().st_ino,(self.source/'K0/window.json').stat().st_ino)
        r.validate(self.source,self.dest,prepared=True)
        self.assertEqual(manifest['fresh_windows'],list(r.LATE))
        with self.assertRaises(ValueError):r.prepare(self.source,self.dest)

    def test_every_identity_mutation_refuses(self):
        cases=[self.p/'build/device/engine',self.p/'screen-seal.json',self.p/'old-seal.json',self.p/'dispatch-p45.json',
               self.source/'K2/run0/dispatch-measured.json',self.source/'K1a/window.json']
        for path in cases:
            with self.subTest(path=path):
                raw=path.read_bytes();path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError):r.validate(self.source,self.dest)
                path.write_bytes(raw)
        with patch.object(r,'boot_id',return_value='different'):
            with self.assertRaisesRegex(ValueError,'boot'):r.validate(self.source,self.dest)

    def test_destination_receipt_manifest_and_new_file_tampering_refuse(self):
        r.prepare(self.source,self.dest)
        for path in [self.dest/'K0/window.json',self.dest/'resume-manifest.json']:
            raw=path.read_bytes();path.write_text('{}')
            with self.assertRaises(ValueError):r.validate(self.source,self.dest,prepared=True)
            path.write_bytes(raw)
        (self.dest/'K0/new-file').write_text('x')
        with self.assertRaises(ValueError):r.validate(self.source,self.dest,prepared=True)

    def test_imported_prerequisite_seal_exception_is_narrow(self):
        r.prepare(self.source,self.dest)
        identity=dict(build_receipt_sha256=digest(self.p/'build-receipt.json'),boot_id='boot')
        self.assertEqual(r.prerequisite_seal(self.dest/'K0/window.json',identity),r.pins()['old_seal_sha256'])
        with self.assertRaisesRegex(ValueError,'model receipts'):r.prerequisite_seal(self.dest/'KD/window.json',identity)
        with self.assertRaises(ValueError):r.prerequisite_seal(self.source/'K0/window.json',identity)
        with self.assertRaises(ValueError):r.prerequisite_seal(self.dest/'K0/window.json',dict(identity,build_receipt_sha256='changed'))

    def test_non_wrapper_seal_change_refuses(self):
        path=self.p/'build-receipt.json';row=json.loads(path.read_text());row['arithmetic']='changed'
        path.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError,'non-wrapper'):r.validate(self.source,self.dest)

    def test_missing_and_symlink_receipts_refuse(self):
        path=self.source/'K0/window.json';raw=path.read_bytes();path.unlink()
        with self.assertRaises(ValueError):r.validate(self.source,self.dest)
        outside=self.build/'outside.json';outside.write_bytes(raw);path.symlink_to(outside)
        with self.assertRaises(ValueError):r.validate(self.source,self.dest)

    def test_resume_queue_starts_at_kd_only(self):
        for phase in ('all','model'):
            self.assertEqual(q.selected_windows(SimpleNamespace(phase=phase,resume_from=self.source)),r.LATE)
        with self.assertRaises(ValueError):q.selected_windows(SimpleNamespace(phase='early',resume_from=self.source))
