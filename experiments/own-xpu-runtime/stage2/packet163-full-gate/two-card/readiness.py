from common import HERE,read,require,sha

def verify_ready(preplan=False,**unused):
 if preplan:return
 ready=read(HERE/'READY-FOR-DEVICE.json')
 require(ready.get('ready') is True and ready['seal_sha256']==sha(HERE/'seal.json'),'CPU readiness missing or stale')
