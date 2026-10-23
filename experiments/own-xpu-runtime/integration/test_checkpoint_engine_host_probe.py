"""Fixture regression checks only; never start a host owner or native tool."""
import hashlib
import unittest
import uuid
from unittest.mock import patch

import checkpoint_engine_host_probe as P


class HostFixtureTests(unittest.TestCase):
    def test_empty_identity_that_failed_attempt_a_is_refused(self):
        with self.assertRaisesRegex(RuntimeError,'three distinct synthetic shard rows'):
            P.synthetic_model_identity(b'')

    def test_exact_three_row_bytes_bind_complete_expected_model_identity(self):
        model=P.synthetic_model_identity(P.SYNTHETIC_IDENTITY)
        self.assertEqual(model['identity_tsv_sha256'],hashlib.sha256(P.SYNTHETIC_IDENTITY).hexdigest())
        self.assertEqual(len(model['shard_stat_rows']),3)
        for n,row in enumerate(model['shard_stat_rows']):
            self.assertEqual(row,dict(name=f'synthetic-host-shard-{n}',size=0,dev=0,ino=0,mtime=0,ctime=0))

    def test_new_plan_cannot_execute_and_preserves_failed_output(self):
        output=P.PACKET/'build'/('engine-integration-test-'+uuid.uuid4().hex)
        with patch.object(P.subprocess,'Popen',side_effect=AssertionError('no owner')), \
             patch.object(P.subprocess,'run',side_effect=AssertionError('no native tools')):
            row=P.plan(output)
        self.assertEqual(P.DEFAULT_OUTPUT.name,'engine-integration-b')
        self.assertFalse(output.exists())
        self.assertEqual(row['expected_identity']['model'],P.synthetic_model_identity(P.SYNTHETIC_IDENTITY))
        output.mkdir()
        try:
            with self.assertRaisesRegex(RuntimeError,'output exists'):P.plan(output)
        finally:
            output.rmdir()


if __name__=='__main__':unittest.main()
