import copy
import unittest
from rolling_provider_trace_audit import audit_controller
from test_rolling_ring_socket import exercise


class RollingTraceTests(unittest.TestCase):
    def audit(self,data,count):
        return audit_controller(data['commands'],data['records'],data['batches'],[3,5,8,11],data['output_ids'],
            data['commands'][0]['row']['request'],count,16,97,128,500)

    def test_real_fragmented_codec_witnesses_two_four_six(self):
        for count in (2,4,6):
            data,_=exercise(count,maximum=16,first_options=dict(miss_first=(4,9),miss_second=(6,11),provider_delay=0.0004))
            result=self.audit(data,count)
            self.assertGreater(result['actual_proposal_rows'],0)
            self.assertEqual(len(result['providers']),data['input_position']-1)
            self.assertEqual(result['observed_miss_depths'],sorted({r['depth'] for r in data['rejected_proposals']}))

    def test_raw_witness_proposal_lineage_and_duplicate_completion_refused(self):
        original,_=exercise(4,maximum=6,first_options=dict(miss_first=(4,)))
        for kind in ('proposal','raw','duplicate','source','final-record','omit-provider'):
            data=copy.deepcopy(original)
            if kind=='proposal':
                item=next(v for v in data['commands'] if v['event']=='issued' and v['op']==24 and v['tentative'])
                item['proposal']['batch_ticket']+=1
            elif kind=='raw':
                item=next(v for v in data['commands'] if v['event']=='completed' and v['op']==27)
                item['metadata_hex']='00'+item['metadata_hex'][2:]
            elif kind=='duplicate':
                index=next(i for i,v in enumerate(data['commands']) if v['event']=='completed')
                data['commands'].insert(index+1,copy.deepcopy(data['commands'][index]))
            elif kind=='source':
                item=next(v for v in data['commands'] if v['event']=='issued' and v.get('source'))
                item['source']['sha256']='f'*64
            elif kind=='final-record':data['records'][0]['record_sha256']='f'*64
            else:data['batches'].pop()
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.audit(data,4)

    def test_final_parent_lease_starts_before_provider_reservation(self):
        data,_=exercise(2,maximum=6)
        commands=data['commands']
        provider=next(i for i,e in enumerate(commands) if e['event']=='issued' and e['op']==27)
        seed=commands[provider]['row']['id']
        final=next(i for i,e in enumerate(commands) if e['event']=='issued' and e['op']==24 and e['stage']==1 and e['row']['id']==seed)
        self.assertGreater(final,provider)
        commands.insert(provider,commands.pop(final))
        with self.assertRaisesRegex(ValueError,'lease'):
            self.audit(data,2)

    def test_verified_old_proposal_cannot_be_reissued_as_tentative(self):
        data,_=exercise(4,maximum=8)
        event=next(e for e in data['commands'] if e['event']=='issued' and e['op']==24 and e['stage']>0
                   and not e['tentative'] and e['proposal'] is not None)
        event['tentative']=True
        with self.assertRaisesRegex(ValueError,'verified input frontier'):
            self.audit(data,4)


if __name__=='__main__':unittest.main()
