"""CPU launch-name contract: read shell source, never execute a launcher."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

AUTHOR=Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261010-continuation138-stream')
sys.path.insert(0,str(AUTHOR))
import runtime_packet as packet
import text_residency133 as text


def candidate():
    return dict(packet.CONTROL_ENVIRONMENT, **text.SCOPE, LTX_TEXT_RESIDENCY='split36',
        LTX_GC_INTERVAL_SECONDS='60', LTX_STORAGE_SCAN_MODE='background',
        LTX_SNAPSHOT_DIGEST_CACHE='1', LTX_MAINTENANCE_MODE='idle')

class LaunchIdentity133(unittest.TestCase):
    def test_full_split36_name_matches_prepared_shell_command(self):
        env=candidate()
        self.assertEqual(text.validate_scope(env),'split36')
        change=packet.transition({'files': {}}, {}, {}, {})
        self.assertEqual(change['cone_graph_memory']['choices'], ['off', 'replica-release', 'text-shift'])
        self.assertEqual(change['text_residency']['default'], 'legacy')
        self.assertEqual(change['text_residency']['oracle_sha256'], text.ORACLE_SHA256)
        expected=('encoder-server-continuation-stream-138-frame-dg1-adcone-bo1-pa1-smfp-'
            'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-'
            'gc60-ssbackground-sdc1-mi-cmtext-shift-textsplit36')
        self.assertEqual(packet.expected_run_name(env),expected)
    def test_legacy_off_name_equals_parent137_after_namespace_change(self):
        env=dict(candidate(),LTX_TEXT_RESIDENCY='legacy',LTX_CONE_GRAPH_MEMORY='off',
            LTX_DECODER_GRAPH='0',LTX_DISPLAY_SCHEDULE='sampler-a')
        self.assertEqual(packet.expected_run_name(env),packet.BASE.expected_run_name(env).replace('continuation-stream-137-','continuation-stream-138-'))
        absent=dict(env);del absent['LTX_TEXT_RESIDENCY']
        self.assertEqual(packet.expected_run_name(env),packet.expected_run_name(absent))
    def test_legacy_replica_name_equals_parent137_after_namespace_change(self):
        env=dict(candidate(),LTX_TEXT_RESIDENCY='legacy',LTX_CONE_GRAPH_MEMORY='replica-release',
            LTX_DISPLAY_DEVICE='xpu:2',LTX_AUDIO_RESIDENCY='xpu2')
        self.assertEqual(packet.expected_run_name(env),packet.BASE.expected_run_name(env).replace('continuation-stream-137-','continuation-stream-138-'))
        self.assertTrue(packet.expected_run_name(env).endswith('-cmreplica-release-audioxpu2'))
    def test_prepared_shell_uses_selected_mode_then_audio_then_text(self):
        source=(AUTHOR/'launch-138.sh').read_text()
        cone='[ "$CM" = off ] || NAME=${NAME}-cm${CM}'
        audio='[ "$AUDIO" = legacy ] || NAME=${NAME}-audioxpu2'
        text='[ "$TEXT" = legacy ] || NAME=${NAME}-textsplit36'
        self.assertLess(source.index(cone),source.index(audio))
        self.assertLess(source.index(audio),source.index(text))
