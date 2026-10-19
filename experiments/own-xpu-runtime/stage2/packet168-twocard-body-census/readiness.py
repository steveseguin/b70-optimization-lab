from census_contract import P,read,require
def verify_ready(preplan=False,**unused):
    if preplan:return
    ready=read(P/'READY-FOR-DEVICE.json')
    require(ready.get('ready_for_device')is True,'packet168 CPU preparation incomplete; device launch refused')
    raise ValueError('packet168 has no qualified full census orchestrator')
