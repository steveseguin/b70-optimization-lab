import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('closure_subject', Path.cwd()/'tools/public-closure-scanner.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for failure in (subprocess.CalledProcessError(17, ['gh']), FileNotFoundError('fixture: missing gh')):
    cache = {}; errors = io.StringIO()
    with patch.object(m.subprocess, 'run', side_effect=failure) as query, contextlib.redirect_stderr(errors):
        first = m.release_assets('v-fixture',cache)
        assert first is None, 'RELEASE_UNKNOWN: failed release lookup must not masquerade as an empty release'
        assert m.release_assets('v-fixture',cache) is None
    assert query.call_count == 1, 'Cache unavailable lookup within one audit'
    assert 'v-fixture' in errors.getvalue() and 'unavailable' in errors.getvalue().lower()
for stdout,expected in [('',set()), ('runtime.whl\nbuild.txt\n', {'runtime.whl','build.txt'})]:
    cache = {}; errors = io.StringIO()
    with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess(['gh'],0,stdout,'')) as query, contextlib.redirect_stderr(errors):
        assert m.release_assets('v-ok',cache) == expected
        assert m.release_assets('v-ok',cache) == expected
    assert query.call_count == 1 and not errors.getvalue(), 'Valid empty/nonempty release remains authoritative'
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    guide = root/'repro/fixture/README.md'; guide.parent.mkdir(parents=True)
    guide.write_text('Download https://github.com/steveseguin/b70-optimization-lab/releases/download/v-fixture/runtime.whl\n')
    package = {'id':'fixture', 'guide':'repro/fixture/README.md', 'manifest':'packages/fixture/package.json'}
    with patch.object(m, 'ROOT', root), patch.object(m.subprocess, 'run',
            side_effect=subprocess.CalledProcessError(17,['gh'])), contextlib.redirect_stderr(io.StringIO()):
        unknown = m.scan_package(package, {'repro/fixture/README.md'}, {})
    assert not unknown['findings'].get('missing_release_asset'), 'Query failure cannot prove asset absence'
    assert unknown.get('release_assets_unavailable') and unknown.get('warnings'), 'Package report must expose incomplete lookup'
    with patch.object(m, 'ROOT', root), patch.object(m.subprocess, 'run',
            return_value=subprocess.CompletedProcess(['gh'],0,'','')):
        empty = m.scan_package(package, {'repro/fixture/README.md'}, {})
    assert len(empty['findings'].get('missing_release_asset',[])) == 1, 'Authoritatively absent asset still fails closure'
print('PASS: failed/unavailable distinction, visible warning, cache behavior and package-report integration')
