"""A ready marker binds completed CPU gates, not an unmeasured device result."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
CAPABILITIES=['publication-split','resident-miss-partitions','serialized-miss-delay','resident-overlap-window','in-load-off-on-bracket']

def verify_ready():
    row=json.loads((P/'READY-FOR-DEVICE.json').read_text())
    if row.get('ready_for_device') is not True or row.get('cpu_preparation_complete') is not True:
        raise ValueError('packet58af CPU readiness incomplete')
    if row.get('capabilities')!=CAPABILITIES:raise ValueError('measurement capability mismatch')
    if row.get('build_receipt_sha256')!=hashlib.sha256((P/'build-receipt.json').read_bytes()).hexdigest():
        raise ValueError('readiness build binding mismatch')
    proposal=P.parents[1]/'ops/lane-queue/proposed-p58af-measure-A.txt'
    for path,key in ((proposal,'proposal_sha256'),(P/'evidence/queue-plan.json','queue_plan_sha256')):
        if row.get(key)!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError('readiness proposal/plan binding mismatch')
    from cpu_seal import verify
    verify()
    return row
