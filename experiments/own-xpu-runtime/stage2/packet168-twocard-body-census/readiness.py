from census_contract import P,read,require
from build_engine import sha
def verify_ready(preplan=False,**unused):
    if preplan:return
    require((P/'READY-FOR-DEVICE.json').is_file(),'packet168 READY marker absent; device launch refused')
    ready=read(P/'READY-FOR-DEVICE.json')
    require(ready.get('ready_for_device')is True,'packet168 CPU preparation incomplete; device launch refused')
    require(ready.get('seal_sha256')==sha(P/'seal.json'),'READY marker does not bind the current seal')
    for name,digest in ready['evidence_sha256'].items():
        require(sha(P/name)==digest,'READY evidence changed: '+name)
    return ready
