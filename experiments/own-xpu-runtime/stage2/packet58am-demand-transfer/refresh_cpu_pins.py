"""Refresh current CPU receipt indexes for rehearsal; never grant device release."""
import json
from packet_io import P, ROOT, sha, save


def main():
    assert not json.loads((P/'READY-FOR-DEVICE.json').read_text())['ready_for_device']
    build=json.loads((P/'evidence/build.json').read_text())
    receipt=json.loads((P/'build-receipt.json').read_text())
    package=json.loads((P/'screen-packaging.json').read_text())
    for name in receipt['sources']:
        receipt['sources'][name]=sha(P/name)
    for name in package['files']:
        package['files'][name]=sha(ROOT/name)
    for target in (receipt,package):
        target['ready_for_device']=False
        # Rehearsal must not hash its own output while that file is being
        # rewritten. The final sealer restores these links after verification.
        target['proofs']={n:h for n,h in target['proofs'].items() if not
                          any(n.startswith('evidence/p58an-'+prefix) for prefix in ('checks','plan-','rehearse-'))}
        for name in target['proofs']:target['proofs'][name]=sha(P/name)
    receipt['artifacts'].update(build['artifacts'])
    for name in receipt['proposals']:receipt['proposals'][name]=sha(P/name)
    save(P/'screen-packaging.json',package)
    receipt['queue_packaging_sha256']=sha(P/'screen-packaging.json')
    save(P/'build-receipt.json',receipt)
    seal=json.loads((P/'seal.json').read_text())
    seal.update(build_receipt_sha256=sha(P/'build-receipt.json'),
                queue_packaging_sha256=sha(P/'screen-packaging.json'),
                proofs=receipt['proofs'],proposals=receipt['proposals'],artifacts=receipt['artifacts'])
    save(P/'seal.json',seal)
    print('Current CPU hashes refreshed; device release remains false')


if __name__=='__main__':main()
