"""Exercise the documented preparation entry with same-packet receipts."""
import contextlib
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import prepare_resume as resume


@pytest.mark.parametrize('schema', ['packet91.window.v1', 'packet70.window.v1', 'packet75.window.v1'])
def test_prepare_resume_receipt_identity(tmp_path, schema):
    packet = tmp_path / 'packet'
    build = packet / 'build'
    source, dest = build / 'device-cards01-a', build / 'device-cards01-b'
    (packet / 'evidence').mkdir(parents=True)
    (packet / 'build-receipt.json').write_text('{}')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    seal = dict(artifacts_sha256='a' * 64, screen_seal_sha256='b' * 64)
    row = dict(schema=schema, boot_id=boot, build_receipt_sha256='c' * 64, **seal)
    for name in resume.EARLY:
        (source / name).mkdir(parents=True)
        (source / name / 'window.json').write_text(json.dumps(row))
    with contextlib.ExitStack() as stack:
        for name, value in [('P', packet), ('B', build)]:
            stack.enter_context(patch.object(resume, name, value))
        stack.enter_context(patch.object(resume.sys, 'argv', ['prepare_resume.py', '--source', str(source), '--destination', str(dest)]))
        stack.enter_context(patch.object(resume.os, 'getpriority', return_value=19))
        stack.enter_context(patch.object(resume.os, 'sched_getaffinity', return_value={8}))
        stack.enter_context(patch.object(resume, 'digest', return_value='c' * 64))
        stack.enter_context(patch.object(resume, 'file_inventory', return_value={}))
        verify = stack.enter_context(patch('chain_seal.verify', return_value=seal))
        validate = stack.enter_context(patch('queue_runner.validate_success'))
        stack.enter_context(patch('window.prerequisites', return_value=row))
        launch = stack.enter_context(patch.object(resume.subprocess, 'run'))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        if schema != 'packet91.window.v1':
            with pytest.raises(AssertionError):
                resume.main()
            assert not (packet / 'resume-pins.json').exists()
            launch.assert_not_called()
        else:
            resume.main()
            assert validate.call_count == len(resume.EARLY)
            verify.assert_called_once()
            assert json.loads((packet / 'chain-registration.json').read_text()) == {'output': dest.name}
            pins = json.loads((packet / 'resume-pins.json').read_text())
            assert pins['source'] == str(source)
            assert pins['windows'] == list(resume.EARLY)
            assert launch.call_count == 2
            assert '--prepare-resume' in launch.call_args.args[0]
