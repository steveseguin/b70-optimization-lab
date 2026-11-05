#!/usr/bin/env python3
"""Compile CPU-only tests using the actual rank IPC functions; never opens a GPU."""
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
RANK = HERE.parents[1] / 'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp'

def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    for end in range(opening + 1, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise RuntimeError('unterminated C++ function')

source = RANK.read_text()
with tempfile.TemporaryDirectory(prefix='ownrt-native-ipc-') as temporary:
    root = Path(temporary)
    (root / 'rank_transfer_under_test.hpp').write_text(
        function(source, 'static void pipeline_cancel_check() {') + '\n' +
        function(source, 'static void transfer(') + '\n')
    binary = root / 'test'
    subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread',
                    '-I', str(root), str(HERE / 'test_native_persistent_transport.cpp'),
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=15)
