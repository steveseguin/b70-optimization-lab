"""Fresh folder for exactly the same frozen packet97 decision and binaries."""
import gzip,json,re,shlex
from pathlib import Path
import orchestrate as o

def output(name):
    assert re.fullmatch(r'device-cards01-[a-z]',name), 'expected device-cards01-a/b/c/...'
    path=o.P/'build'/name
    assert not path.exists(), 'fresh chain output already exists: '+str(path)
    return path

def command(name):
    output(name)
    base=o.command()
    # A spent systemd unit must not prevent a new manual chain attempt.
    base=base.replace('--unit=packet97-chain ', '--unit=packet97-chain-'+name.rsplit('-',1)[1]+' ')
    return base.removesuffix(' </dev/null')+' '+shlex.quote(str(o.P/'build'/name))+' </dev/null'

def startup():
    from startup_receipt97e import verify
    return verify()


def prepare(config,name):
    path=output(name)
    from bundle_selection import selected
    actual=selected()
    assert all(actual[k]==v for k,v in config['candidate'].items()), 'fresh chain cannot change frozen selection'
    startup()
    # Original screen seals and binaries remain byte-for-byte frozen. Only the
    # current chain closure and output registration change, with old seal saved.
    receipt=o.P/'build-receipt.json'
    archive=o.P/'evidence'/('prior-chain-seal-'+o.sha(receipt)+'.json')
    if not archive.exists():archive.write_bytes(receipt.read_bytes())
    o.save(o.P/'chain-registration.json',dict(output=name))
    # storage is normally imported while checking the old screen. Refresh just
    # its registration, never its budgets or evidence.
    import storage
    storage.REGISTERED_CHAIN=name
    from chain_seal import checked,verify
    o.save(receipt,checked())
    from packet56_submission import pin_resealed_packet56
    pin_resealed_packet56();verify()
    return path
