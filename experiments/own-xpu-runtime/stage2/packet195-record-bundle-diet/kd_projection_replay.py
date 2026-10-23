"""Strict portable KD projection evidence; native owner hashes stay unmodified."""
import hashlib,json
from kd_reference import project,TARGET_ONLY,TARGET_ONLY_REMOVED

def validate(e,target_hash,window):
    def read(leaf):
        assert leaf in window['receipts'], 'unbound KD projection receipt: '+leaf
        return e.read('KD/'+leaf,window['receipts'][leaf])
    binding=read('draft-reference-binding.json')
    ref=read('draft-reference-selection.json')
    raw=e.raw('KD/draft-reference-selection.json',window['receipts']['draft-reference-selection.json'])
    digest=hashlib.sha256(raw).hexdigest()
    assert binding['passed'] is True and binding['schema']=='packet103.kd-draft-projection.v1'
    assert binding['selection_sha256']==binding['target_selection_sha256']==target_hash
    assert binding['reference_selection_sha256']==digest and binding['target_executed'] is False
    assert binding['target_only']==TARGET_ONLY and binding['target_only_removed']==list(TARGET_ONLY_REMOVED)
    target=e.read('selection.json',target_hash)
    assert ref==project(target) and binding['draft']==target['draft']
    host=read('host-reference-identity.json')
    assert host['selection_sha256']==target_hash and host['reference_selection_sha256']==digest
    proofs=[host['draft_reference']]+[read(f'owner{i}/draft-reference-identity.json') for i in (0,1)]
    for proof in proofs:
        assert proof['passed'] is True and proof['selection_sha256']==target_hash
        assert proof['reference_selection_sha256']==digest
        choices=proof['draft_kernel_choices']
        assert choices['selection_sha256']==digest and choices['choices']==target['draft']
        assert choices['target_mutable_aliases']==0
        assert choices==proofs[0]['draft_kernel_choices'], 'KD host/device draft kernel identity differs'
    return digest
