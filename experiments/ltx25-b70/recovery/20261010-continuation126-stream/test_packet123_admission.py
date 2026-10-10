"""CPU launch admission and immutable parent identity; never invoke a launcher."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import runtime_packet as rp

class Admission(unittest.TestCase):
    def env(self):
        return dict(rp.CONTROL_ENVIRONMENT, LTX_STREAM_FRAMES='121', LTX_ANCHOR='frame',
                    LTX_SAMPLER_PLACEMENT='two-way20-28', LTX_STREAM_TEXT_REUSE='1',
                    LTX_DECODER_GRAPH='1', LTX_ANCHOR_DECODE='cone', LTX_BENCODE_OVERLAP='1',
                    LTX_PREP_AHEAD='1', LTX_SNAPSHOT_MODE='fingerprint', LTX_DECODER_GRAPH_POOL_CAP_GB='1.0',
                    LTX_DISPLAY_SCHEDULE='eager-display', LTX_ANCHOR_READ_AHEAD='0',
                    LTX_SNAPSHOT_SCHEDULE='full', LTX_DISPLAY_DEVICE='xpu:2')
    def test_explicit_replica_and_unique_run_name(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,self.env(),clear=True):
            rp.check_control_environment(Path(d))
            self.assertTrue(rp.expected_run_name().endswith('-dseager-display-ra0-ssfull-ddxpu2'))
    def test_default_device_keeps_parent_schedule_suffix(self):
        env=self.env();env.pop('LTX_DISPLAY_DEVICE')
        with patch.dict(os.environ,env,clear=True):
            self.assertTrue(rp.expected_run_name().endswith('-dseager-display-ra0-ssfull'))
    def test_invalid_scope_refused_before_any_launch(self):
        for key,value in [('LTX_DISPLAY_DEVICE','xpu:1'),('LTX_STREAM_FRAMES','97'),
                          ('LTX_DISPLAY_SCHEDULE','sampler-a'),('LTX_ANCHOR_DECODE','full'),
                          ('LTX_ANCHOR','mixed')]:
            env=self.env();env[key]=value
            with self.subTest(key=key),tempfile.TemporaryDirectory() as d,patch.dict(os.environ,env,clear=True):
                with self.assertRaises(RuntimeError):rp.check_control_environment(Path(d))
    def test_replica_latch_refuses_without_archiving_it(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,self.env(),clear=True):
            p=Path(d)/'display-replica-120-refused.json';p.write_text('{}')
            with self.assertRaises(RuntimeError):rp.check_control_environment(Path(d))
            self.assertEqual(p.read_text(),'{}')
            os.environ['LTX_DISPLAY_DEVICE']='xpu:3'
            rp.check_control_environment(Path(d))
    def test_parent_is_the_latest_sealed_125(self):
        self.assertEqual(rp.PARENT.name,'prepared-continuation-stream-125')
        self.assertEqual(rp.PARENT_SHA,'3c2ed91975343ceb1acd2c4fe06e0fe1d7b768e0fff594865a8ec3bbbb565421')
