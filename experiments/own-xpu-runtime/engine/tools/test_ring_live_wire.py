from dataclasses import replace
from hashlib import sha256
import struct
import unittest

import ring_live_wire as codec

wire,ring=codec.wire,codec.ring


def final_fixture():
    request=sha256(b'fixture').digest();before=sha256(b'ownrt.ring-request.v1\0'+request+struct.pack('<Q',0)).digest()
    row=ring.Row(0,1,0,0,7,1,request,before,wire.append_prefix(before,0,7))
    original=ring.Command(3,ring.ROW,1,row,False)
    accepted=ring.Command(3,ring.ACCEPT,2,row,False,1)
    metadata,_=wire.row_metadata(accepted,final=True,stream_bytes=16)
    fields=list(wire.ROW_META.unpack(metadata));fields[14]=1
    hidden=bytes(range(16))
    h=codec.handoff_codec.HEADER.pack(codec.handoff_codec.MAGIC,1,16,0,3,4,1,2,7,11,1,0,sha256(hidden).hexdigest().encode())
    raw=codec.FINAL_HEADER.pack(codec.FINAL_MAGIC,1,360,3,2)+wire.ROW_META.pack(*fields)+h
    shared=bytearray(266304);shared[codec.FINAL_OFFSET:codec.FINAL_OFFSET+360]=raw
    shared[codec.handoff_codec.HIDDEN_OFFSET:codec.handoff_codec.HIDDEN_OFFSET+16]=hidden
    parent=codec.final_record(shared,original,accepted,11,stages=4,stream_bytes=16,vocab=97)
    seed=ring.Row(0,2,1,1,11,2,request,row.after,wire.append_prefix(row.after,1,11))
    command=codec.ProviderCommand(5,ring.Command(0,ring.ROW,3,seed,False),parent,1)
    return shared,original,accepted,command


class LiveWireTests(unittest.TestCase):
    def test_final_record_every_byte_and_hidden_bound_to_actual_commit(self):
        shared,row,accept,_=final_fixture()
        for offset in range(360):
            bad=bytearray(shared);bad[codec.FINAL_OFFSET+offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):
                codec.final_record(bad,row,accept,11,stages=4,stream_bytes=16,vocab=97)
        shared[codec.handoff_codec.HIDDEN_OFFSET]^=1
        with self.assertRaises(ValueError):codec.final_record(shared,row,accept,11,stages=4,stream_bytes=16,vocab=97)
    def test_owned_final_record_survives_shared_reuse(self):
        shared,_,_,command=final_fixture();before=command.parent.handoff.hidden
        shared[:]=bytes(len(shared))
        self.assertEqual(command.parent.handoff.hidden,before)
        codec.seed_metadata(command,stream_bytes=16)
    def test_verified_seed_parent_not_hypothetical(self):
        _,_,_,command=final_fixture()
        for seed in (replace(command.seed,tentative=True),replace(command.seed,row=replace(command.seed.row,token=12)),
                     replace(command.seed,row=replace(command.seed.row,parent=44)),replace(command.seed,row=replace(command.seed.row,before=bytes(32)))):
            with self.assertRaises(ValueError):codec.seed_metadata(replace(command,seed=seed),stream_bytes=16)
    def test_proposal_provenance_and_guess_extent(self):
        _,_,_,command=final_fixture();seed=command.seed.row
        raw=codec.PROPOSAL.pack(0x44525032,1,192,3,0,5,2,1,2,1,1,1,2,2,18,32,0,1,
                                seed.request,seed.after,sha256(command.parent.handoff.hidden).digest())
        result=codec.decode_proposal(raw,command,vocab=97,context=64)
        self.assertEqual(result['guesses'],[18,32])
        # Guess bytes may legitimately differ; every identity/restore byte may not.
        for offset in list(range(80))+list(range(88,192)):
            bad=bytearray(raw);bad[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):codec.decode_proposal(bytes(bad),command,vocab=97,context=64)
        fields=list(codec.PROPOSAL.unpack(raw));fields[14]=97
        with self.assertRaises(ValueError):codec.decode_proposal(codec.PROPOSAL.pack(*fields),command,vocab=97,context=64)
