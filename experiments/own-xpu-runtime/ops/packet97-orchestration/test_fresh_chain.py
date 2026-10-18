import json
from pathlib import Path
import pytest
import fresh_chain as f

def test_new_outputs_and_spent_directory(tmp_path,monkeypatch):
    monkeypatch.setattr(f.o,'P',tmp_path)
    (tmp_path/'build/device-cards01-a').mkdir(parents=True)
    (tmp_path/'build/device-cards01-a/history').write_text('untouched')
    for name in ('device-cards01-b','device-cards01-c'):
        assert str(tmp_path/'build'/name) in f.command(name)
        assert '--unit=packet97-chain-'+name[-1] in f.command(name)
    with pytest.raises(AssertionError,match='already exists'):f.output('device-cards01-a')
    for name in ('../device-cards01-b','device-cards23-b','/tmp/b','device-cards01-b/child'):
        with pytest.raises(AssertionError):f.output(name)
    assert (tmp_path/'build/device-cards01-a/history').read_text()=='untouched'
