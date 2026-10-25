import copy
import hashlib
import sys
from pathlib import Path
import unittest

import finalize_ring_live_proof as proof
sys.path.insert(0,str(proof.HERE.parents[1]/'engine/tools'))
import ring_live_wire as wire


def fixture():
    request='a'*64;inputs=[3,5,7,9];prompt=3
    parents=[dict(row_sequence=2*p+1,commit_sequence=2*p+2) for p in range(4)]
    pairs=[];depths=[];batches=[];native=[]
    prefix=hashlib.sha256(b'ownrt.ring-request.v1\0'+bytes.fromhex(request)+bytes(8)).digest()
    prefix=wire.wire.append_prefix(prefix,0,inputs[0])
    for p in range(1,4):
        head=p>=2;hidden=hashlib.sha256(bytes([p])).hexdigest();guesses=[20+p,30+p] if head else []
        prefix=wire.wire.append_prefix(prefix,p,inputs[p])
        pairs.append(dict(position=p,token=inputs[p],head=head,hidden_sha256=hidden,proposal=guesses[0] if head else -1))
        if head:depths.append(dict(seed_position=p,guesses=guesses))
        batches.append(dict(epoch=0,request_sha256=request,seed_prefix_sha256=prefix.hex(),seed_position=p,
            restored_position=p,seed_row=p+1,parent_row=p,provider_serial=p,guesses=guesses,available_depth=len(guesses),
            parent_hidden_sha256=hidden,restored=True,speculative_target_use=False,final_commit=parents[p-1]['commit_sequence'],sequence=3*p+2))
        native.append(dict(sequence=3*p+2,provider_serial=p,seed_row=p+1,parent_row=p,seed_position=p,confirmed_token=inputs[p],
            fixture=max(0,p-prompt+2),parent_final_ticket=parents[p-1]['row_sequence'],parent_final_commit=parents[p-1]['commit_sequence'],
            hidden_sha256=hidden,guesses=guesses,restored_position=p,mutable_bytes_verified=head,snapshot_bytes=100 if head else 0,
            canonical_ms=1.0,capture_ms=0.1,recursive_ms=1.0,restore_ms=0.1))
    reference=dict(canonical_pairs=pairs,depth2_rows=depths,expected_recursive_captures=2,expected_recursive_restores=2,
                   canonical_draft_input_identity=dict(pair_sequence_sha256=proof.token_hash([[r[k] for k in ('position','token','head','hidden_sha256')] for r in pairs])))
    att=dict(provider_trace_records=3,provider_trace_omitted=0,provider_private_bytes=100,
             provider_snapshot_captures=2,provider_snapshot_restores=2,provider_byteverified_restore_count=2)
    return [batches,native,reference,inputs,prompt,parents,att,request]


class RingLiveProofTests(unittest.TestCase):
    def test_actual_recursive_prefix_and_true_pairs_match(self):
        result=proof.audit_pairs(*fixture());self.assertEqual((result['pairs'],result['depth2_pairs']),(3,2))

    def test_hidden_parent_guess_and_restore_mutations_refuse(self):
        for index,field,value in [(0,'seed_prefix_sha256','b'*64),(0,'guesses',[1,2]),(0,'restored',False),
                                  (0,'parent_hidden_sha256','b'*64),(0,'final_commit',99),
                                  (1,'confirmed_token',1),(1,'parent_final_ticket',99),
                                  (1,'mutable_bytes_verified',False),(1,'snapshot_bytes',99),
                                  (1,'canonical_ms',float('nan'))]:
            with self.subTest(field=field):
                args=fixture();args[index][1][field]=value
                with self.assertRaises(ValueError):proof.audit_pairs(*args)

    def test_missing_pairs_and_unverified_restores_refuse(self):
        args=fixture();args[0].pop()
        with self.assertRaises(ValueError):proof.audit_pairs(*args)
        args=fixture();args[6]['provider_byteverified_restore_count']=1
        with self.assertRaises(ValueError):proof.audit_pairs(*args)


if __name__=='__main__':unittest.main()
