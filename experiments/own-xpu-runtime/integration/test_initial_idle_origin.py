"""CPU-only source proof, retained bytes, filesystem and rounding refusals."""
from decimal import Decimal, localcontext, ROUND_CEILING
import hashlib
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import initial_idle_origin as origin


def cold(ms='215480.035061'):
    return ('{"load_and_pin_ms":'+ms+',"initial_cache_fill_bytes":0,"initial_cache_policy":'
            '"empty-content-independent","first_prompt_fills_charged_in_request":true}\n').encode()


class OriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        origin.verify_native_proof()  # Real source/build/ELF/library hashes; no execution.

    def setUp(self):
        mock = patch.object(origin, 'verify_native_proof', return_value=None)
        mock.start(); self.addCleanup(mock.stop)

    def derive(self, raw=None, **edits):
        raw = cold() if raw is None else raw
        args = dict(launch_monotonic=1000.125, observed_monotonic=1216.0,
            cold_start_bytes=raw, cold_start_sha256=hashlib.sha256(raw).hexdigest(),
            admitted_binary_sha256=origin.BINARY_SHA256,
            mapped_clock_library_path=str(origin.CLOCK_LIBRARY), mapped_clock_library_sha256=origin.CLOCK_SHA256)
        args.update(edits)
        return origin.derive_initial_idle_origin(**args)

    def test_real_retained_p199_cold_file_and_no_live_claim(self):
        path = origin.HERE.parent/'stage2/packet199-chat-parking/evidence/device-p199-chat-A-a/owner/cold-start.json'
        row = self.derive(path.read_bytes())
        self.assertEqual(row['whole_seconds_added'], 215)
        self.assertLessEqual(row['last_native_activity'], 1215.125)
        self.assertEqual(row['absolute_origin_monotonic'],1000.125)
        for key in ('absolute_deadline_changed','fresh_owner_provenance_verified','process_mapping_verified','live_admission_ready'):
            self.assertIs(row[key],False)

    def test_round_up_at_integer_boundaries_stays_below_true_interval(self):
        # Model a report rounded upward by its full six-decimal-ms error unit.
        for reported in ('0.000000','0.000001','0.999999','1.000000','999.999999',
                         '1000.000000','1000.999999','1001.000000','215000.000000','7200000.000000'):
            raw=cold(reported); ms=Decimal(reported)
            for launch in (0.0, 0.125, 1000000.1, float(2**39)):
                with self.subTest(ms=reported,launch=launch):
                    row=self.derive(raw,launch_monotonic=launch,observed_monotonic=launch+7201)
                    actual_seconds=max(Decimal(0),(ms-Decimal('0.000001'))/1000)
                    ceiling=Decimal.from_float(launch)+actual_seconds
                    self.assertLessEqual(Decimal.from_float(row['last_native_activity']),ceiling)
                    self.assertGreaterEqual(row['last_native_activity'],launch)

    def test_caller_decimal_precision_cannot_erase_rounding_margin(self):
        with localcontext() as context:
            context.prec=3;context.rounding=ROUND_CEILING
            row=self.derive(cold('215000.000000'),launch_monotonic=0.0)
        self.assertEqual(row['whole_seconds_added'],214)
        self.assertLess(row['last_native_activity'],215)

    def test_subsecond_interval_keeps_launch_origin(self):
        row=self.derive(cold('999.999999'))
        self.assertEqual(row['whole_seconds_added'],0)
        self.assertEqual(row['last_native_activity'],1000.125)

    def test_malformed_native_grammar_refused(self):
        for ms in ('NaN','Infinity','-0.000001','1e3','01.000000','1.0','7200000.000001','99999999.000000'):
            with self.subTest(ms=ms):
                with self.assertRaises(origin.IdleOriginRefusal):self.derive(cold(ms))
        for raw in (cold()+b' ',cold().replace(b'"initial_cache_fill_bytes":0',b'"initial_cache_fill_bytes":1'),
                    cold().replace(b'"load_and_pin_ms":',b'"extra":1,"load_and_pin_ms":'),b'x'*513):
            with self.assertRaises(origin.IdleOriginRefusal):self.derive(raw)

    def test_hash_binary_library_and_clock_inputs_refused(self):
        for edit in ({'cold_start_sha256':'0'*64},{'admitted_binary_sha256':'0'*64},
                     {'mapped_clock_library_sha256':'0'*64},{'mapped_clock_library_path':'/tmp/libstdc++.so.6'},
                     {'launch_monotonic':True},{'observed_monotonic':math.inf},
                     {'launch_monotonic':-1},{'launch_monotonic':2**41},
                     {'observed_monotonic':999},{'observed_monotonic':1100}):
            with self.subTest(edit=edit):
                with self.assertRaises(origin.IdleOriginRefusal):self.derive(**edit)


class ReadTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/'owner';self.root.mkdir(mode=0o700)
        self.path=self.root/'cold-start.json';self.path.write_bytes(cold())
        st=self.root.stat();self.identity=(st.st_dev,st.st_ino)

    def read(self):
        return origin.read_cold_start(self.root,expected_owner_identity=self.identity)

    def test_regular_file_stable_bytes_and_hash(self):
        row=self.read();self.assertEqual(row['raw'],cold());self.assertEqual(row['sha256'],hashlib.sha256(cold()).hexdigest())

    def test_symlink_hardlink_fifo_and_large_file_refused(self):
        target=self.root/'target';target.write_bytes(cold());self.path.unlink();self.path.symlink_to(target)
        with self.assertRaises((OSError,origin.IdleOriginRefusal)):self.read()
        self.path.unlink();os.link(target,self.path)
        with self.assertRaises(origin.IdleOriginRefusal):self.read()
        self.path.unlink();os.mkfifo(self.path)
        with self.assertRaises(origin.IdleOriginRefusal):self.read()
        self.path.unlink();self.path.write_bytes(b'x'*513)
        with self.assertRaises(origin.IdleOriginRefusal):self.read()

    def test_owner_directory_replaced_during_read_refused(self):
        real_read=os.read;changed=False
        def swap(fd,count):
            nonlocal changed
            data=real_read(fd,count)
            if not changed:
                changed=True;self.root.rename(self.root.parent/'old-owner');self.root.mkdir(mode=0o700)
            return data
        with patch.object(origin.os,'read',side_effect=swap):
            with self.assertRaises(origin.IdleOriginRefusal):self.read()

    def test_directory_identity_and_file_replacement_refused(self):
        with self.assertRaises(origin.IdleOriginRefusal):
            origin.read_cold_start(self.root,expected_owner_identity=(self.identity[0],self.identity[1]+1))
        real_read=os.read;changed=False
        def swap(fd,count):
            nonlocal changed
            data=real_read(fd,count)
            if not changed:
                changed=True;replacement=self.root/'replacement';replacement.write_bytes(cold());replacement.replace(self.path)
            return data
        with patch.object(origin.os,'read',side_effect=swap):
            with self.assertRaises(origin.IdleOriginRefusal):self.read()


if __name__=='__main__':unittest.main()
