"""Synthetic report failures and actual recorder guard; no device backend."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import summarize as S

P=Path(__file__).resolve().parent


def event(where,rank,fixture,cls,number=1,spec=False):
    label = where+'.'+cls
    if cls=='moe_experts' and where in S.LAYERS: label=where+'.ffn.combine'
    return dict(schema='packet57.event.v1',rank=rank,fixture=fixture,position=100+fixture,
                layer_boundary=S.BOUNDARIES.get(label,(None,''))[1],
                speculative=spec,label=label,**{'class':cls},event=number,
                start_ns=number*100000,end_ns=number*100000+10000,device_ms=.01)


def events():
    out=[]
    for f in range(9,17):
        for where in ('draft',*S.LAYERS):
            rank=1 if where=='draft' else S.LAYERS[where][0]
            for cls in sorted(S.DRAFT_CLASSES if where=='draft' else S.TARGET_CLASSES):
                out.append(event(where,rank,f,cls,len(out)+1))
    return out


class AttributionTests(unittest.TestCase):
    def test_event_rank_schema_window_duration(self):
        good=event('blk.23',0,9,'attention')
        S.validate_event(good,0)
        for field,value in [('rank',1),('fixture',8),('fixture',17),('start_ns',0),('end_ns',1),('device_ms',float('nan')),('device_ms',2)]:
            bad=dict(good);bad[field]=value
            with self.assertRaises(ValueError):S.validate_event(bad,0)
        with self.assertRaises(ValueError):S.validate_event(event('blk.23',1,9,'attention'),1)

    def test_every_index_and_both_layer_types_required(self):
        rows=events();pairs={i:({}, {}) for i in range(100,130)}
        groups,touched=S.event_groups(rows,pairs)
        self.assertEqual(len(touched),8)
        self.assertEqual(len(groups),40)
        for predicate in (lambda e:e['fixture']!=12,lambda e:S.scope(e)!='blk.27',
                          lambda e:e['class']!='argmax',lambda e:e['label']!='blk.22.ffn.combine'):
            with self.assertRaises(ValueError):S.event_groups([e for e in rows if predicate(e)],pairs)

    def test_cross_cycle_mapping(self):
        rows=events();extra=event('blk.22',0,9,'attention',999,True);rows.append(extra)
        _,touched=S.event_groups(rows,{i:({}, {}) for i in range(100,130)})
        self.assertIn(108,touched)

    def test_recorder_compiled_cpu_only(self):
        with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
            src=Path(tmp)/'test.cpp';binary=Path(tmp)/'test'
            src.write_text('''#include "attribution.hpp"
#include <cassert>
int main(){using namespace p57;
assert(!sample(8)&&sample(9)&&sample(16)&&!sample(17));
for(auto s:{"blk.22.gdn","blk.23.qsa","blk.24.gdn","blk.27.qsa","draft.logits","transfer.upload"})assert(selected(s));
assert(!selected("blk.19.attention"));
Recorder r;r.current={"draft.argmax",9,100,false};r.record(1);assert(r.events.empty());
r.enabled=true;r.record(2);assert(r.events.size()==1);r.current.fixture=17;r.record(3);assert(r.events.size()==1);
assert(category("draft.transfer.proposal")=="transfers");assert(category("blk.23.hc.a.low")=="hc_norm_merge");}
''')
            subprocess.run(['/usr/bin/g++','-std=c++20','-O0','-I',str(P),str(src),'-o',str(binary)],check=True,stdin=subprocess.DEVNULL)
            subprocess.run([str(binary)],check=True,stdin=subprocess.DEVNULL)

    def test_full_report_and_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=P/'build') as tmp:
            root=Path(tmp)
            # Boundary and cancellation costs deliberately differ; incomplete
            # prefixes must never reduce complete per-layer class means.
            ev=events()
            for f in range(9,17):
                for where in ('blk.22','blk.23'):
                    for cls in S.TARGET_CLASSES:
                        ev.append(event(where,0,f,cls,len(ev)+1,True))
            ev.append(event('blk.22',0,9,'attention',99999,True))
            for f in range(9,17):
                for rank,spec in ((0,True),(0,False),(1,False)):
                    for label,(r,edge) in S.BOUNDARIES.items():
                        if r!=rank:continue
                        # End markers on selected layers are already present.
                        if label.startswith('blk.23.'):continue
                        e=event('blk.0' if rank==0 else 'blk.24',rank,f,'hc_norm_merge',len(ev)+1,spec)
                        e.update(label=label,layer_boundary=edge)
                        ev.append(e)
            for e in ev:
                if e.get('layer_boundary'):
                    e['start_ns']=1000000 if e['layer_boundary']=='begin' else 11000000
                    e['end_ns']=e['start_ns']+10000
            trace=[]
            for i in range(127):
                trace.append(dict(position=100+i,hit=bool(i%2),cycle_ms=20.,D_wall_ms=2.,
                    S_ms=16.,A_ms=16. if i%2==0 else 0.,B_ms=17.,rank0_finishes_last=False))
            for n in range(12):
                for arm in ('control','attribution'):
                    dest=root/arm/f'prompt{n}';dest.mkdir(parents=True)
                    receipt=dict(passed=True,exact_oracle=True,oracle_check={'passed':True},attribution_arm=arm,
                        cached_tokens=0,output_tokens=128,target_split=[24,24],prompt_id=f'prompt{n}',
                        prompt_token_sha256='prompt',output_token_sha256='output',binary_sha256='binary',
                        selection_sha256='selection',tokens=list(range(128)))
                    (dest/'receipt.json').write_text(json.dumps(receipt))
                    for rank in (0,1):
                        (dest/f'rank{rank}').mkdir()
                        (dest/f'rank{rank}/sites.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in ev if e['rank']==rank) if arm=='attribution' else '')
                        statuses={(e['position'],e['speculative']):dict(position=e['position'],speculative=e['speculative'],cancelled=False)
                                  for e in ev if e['rank']==rank}
                        (dest/f'rank{rank}/timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in statuses.values()))
            with patch.object(S,'extract',return_value=trace):
                report=S.base_summarize(root)
                self.assertTrue(report['passed'])
                self.assertEqual(len(report['outside_layers']),3)
                self.assertEqual(len(report['draft_breakdown']),8)
                self.assertFalse(report['submission_eligible'])
                self.assertIn('Measured outside layers',S.markdown(report))
                p=root/'control/prompt0/rank0/sites.jsonl';p.write_text(json.dumps(ev[8])+'\n')
                with self.assertRaisesRegex(ValueError,'control arm'):S.base_summarize(root)
                p.write_text('')
                p=root/'control/prompt0/receipt.json';r=json.loads(p.read_text());r['output_token_sha256']='bad';p.write_text(json.dumps(r))
                with self.assertRaisesRegex(ValueError,'identity/output'):S.base_summarize(root)

if __name__=='__main__':unittest.main()
