"""Verify the current CPU-qualified handoff without changing its READY marker."""
import json
from packet_io import P,ROOT,sha

def main():
    ready=json.loads((P/'READY-FOR-DEVICE.json').read_text())
    assert ready['ready_for_device'] and not ready['device_executed']
    assert sha(P/'seal.json')==ready['seal_sha256']
    assert sha(P/'build-receipt.json')==ready['build_receipt_sha256']
    assert sha(P/'screen-packaging.json')==ready['packaging_sha256']
    package=json.loads((P/'screen-packaging.json').read_text())
    for name,h in package['files'].items():assert sha(ROOT/name)==h,name
    for name,h in ready['proofs'].items():assert sha(P/name)==h,name
    for name,h in ready['artifacts'].items():assert sha(P/name)==h,name
    print('Resident-parent CPU handoff seal PASS; device result pending')
if __name__=='__main__':main()
