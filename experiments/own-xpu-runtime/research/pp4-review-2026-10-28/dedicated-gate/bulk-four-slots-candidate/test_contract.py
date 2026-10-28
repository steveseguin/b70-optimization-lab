"""CPU planner/layout/source authentication; no native build or device proof."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import dedicated_provider_driver as D
from rolling_provider import dedicated_prefill as P,prefill
from test_dedicated_bulk_plan import BulkPlanTests
from test_dedicated_prefill import model
from test_pipeline import record,ack

class ContractTests(unittest.TestCase):
    def test_planner_default_and_explicit_four_slots(self):
        with TemporaryDirectory() as td:
            config,c,plan,_=BulkPlanTests().fixture(Path(td));c['dedicated_prefill_pipeline']=True
            def make(values):
                config.write_text(json.dumps(values))
                with patch.object(D.base,'make_plan',side_effect=lambda _:deepcopy(plan)):return D.make_plan(config)
            default=make(c);four=make(dict(c,dedicated_prefill_slots=4))
            self.assertEqual(default['dedicated_prefill_slots'],2)
            self.assertNotEqual(default['request_sha256'],four['request_sha256'])
            for owner in four['stages']+[four['provider']]:self.assertEqual(D.base.option(owner['argv'],'--prefill-slots'),'4')
            for owner in default['stages']+[default['provider']]:self.assertNotIn('--prefill-slots',owner['argv'])
            self.assertNotIn('--prefill-rows',four['provider']['argv'])
            for bad in (True,False,None,0,1,3,8,'4'):
                with self.assertRaisesRegex(ValueError,'four transport slots'):make(dict(c,dedicated_prefill_slots=bad))
            for change in (dict(dedicated_prefill_pipeline=False),dict(dedicated_bulk_prefill=False)):
                with self.assertRaisesRegex(ValueError,'slots|authenticated bulk'):make(dict(c,dedicated_prefill_slots=4,**change))
    def test_real_host_layout_regions_and_strict_extent(self):
        for slots,header,version,token_offset in ((2,4096,1,16),(4,8192,2,32)):
            extent,raw=D.base.prefill_layout(256,32,slots)
            self.assertEqual(extent,prefill.map_bytes(256,32,slots));self.assertEqual(prefill.geometry(slots),(header,version,token_offset))
            mapping=bytearray(extent);mapping[:len(raw)]=raw
            self.assertEqual(struct.unpack('<4I',raw[:16]),(D.base.PREFILL_MAGIC,version,256,32))
            if slots==4:self.assertEqual(struct.unpack('<4I',raw[16:]),(8192,4,0,0))
            self.assertLessEqual(P.RECORD_OFFSET+slots*P.RECORD_BYTES,header)
            self.assertLess(token_offset+256*4,P.RECORD_OFFSET)
            for kind,group in (('forward',0),('reverse',slots)):
                for slot in range(slots):
                    region=prefill.region(mapping,kind,slot,256,32,slots=slots);region[:]=bytes([group+slot+1])*len(region)
                    start=header+(group+slot)*256*32
                    self.assertEqual(mapping[start:start+256*32],bytes([group+slot+1])*(256*32))
            with self.assertRaisesRegex(ValueError,'extent'):prefill.region(mapping[:-1],'reverse',0,256,32,slots=slots)
            with self.assertRaisesRegex(ValueError,'region'):prefill.region(mapping,'reverse',slots,256,32,slots=slots)
        for rows in (1,255,257):
            with self.assertRaisesRegex(ValueError,'geometry'):D.base.prefill_layout(rows,32,4)
    def test_record_ack_version_slot_and_every_field_bound(self):
        m=model(prompt=[i%90 for i in range(898)])
        start,count,sequence=768,128,4;rawsha=sha256(b'actual-shaped-hidden').digest()
        seed=record(m,1,start,count,sequence,slots=4)
        final=record(m,2,start,count,sequence,raw_sha=rawsha,slots=4)
        common=dict(stages=2,start=start,count=count,rows=256,stream=32,parity=3,epoch=m.epoch,request=m.request,
            prompt_sha=sha256(struct.pack('<898i',*m.prompt)).digest(),before=m.proposals.hashes[start],after=m.proposals.hashes[start+count],prompt=m.prompt,raw_sha=rawsha,slots=4)
        seedsha=P.chunk_record(seed,role=1,stage=0,sequence=4,**common)
        finalsha=P.chunk_record(final,role=2,stage=1,sequence=4,**common)
        for i in range(23):
            fields=list(P.RECORD.unpack(seed[:256]));v=fields[i];fields[i]=v+1 if type(v)is int else bytes([v[0]^1])+v[1:]
            with self.assertRaises(ValueError):P.chunk_record(P.RECORD.pack(*fields)+seed[256:],role=1,stage=0,sequence=4,**common)
        a=ack(m,start,count,4,seed,final,rawsha,slots=4)
        arguments=dict(sequence=4,start=start,count=count,parity=3,rows=256,stream=32,stages=2,seed_sequence=4,final_sequence=4,
            epoch=m.epoch,request=m.request,prompt_sha=common['prompt_sha'],seed_sha=seedsha,final_sha=finalsha,raw_sha=rawsha,slots=4)
        self.assertEqual(P.chunk_ack(a,**arguments),896)
        for i in range(24):
            fields=list(P.ACK.unpack(a));v=fields[i];fields[i]=v+1 if type(v)is int else bytes([v[0]^1])+v[1:]
            with self.assertRaises(ValueError):P.chunk_ack(P.ACK.pack(*fields),**arguments)
        with self.assertRaises(ValueError):P.chunk_record(seed,role=1,stage=0,sequence=4,**dict(common,slots=2))
        with self.assertRaises(ValueError):P.chunk_ack(a,**dict(arguments,slots=2))
    def test_comparer_propagates_actual_plan_slots_default_strict_two(self):
        path=Path(__file__).resolve().parent.parent/'compare.py'
        spec=importlib.util.spec_from_file_location('four_slot_compare',path);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
        plan=dict(dedicated_bulk_prefill=True,stages=[{},{}],request_sha256='00'*32,prompt_tokens=[i%90 for i in range(260)],
            max_new=2,context=1024,vocab=97,eos_token_ids=[96],speculative_depth=3,output='/unused',provider=dict(native_output='/unused'),prefill_rows=256)
        for slots in (2,4):
            selected=dict(plan)
            if slots==4:selected['dedicated_prefill_slots']=4
            with patch.object(P,'prefix_evidence',return_value={'actual':'spy'}) as ingest,patch.object(C,'canonical_pairs',return_value=[]):
                C.plan_pairs(selected,[],0)
                self.assertEqual(ingest.call_args.kwargs,dict(rows=256,slots=slots))

if __name__=='__main__':unittest.main()
