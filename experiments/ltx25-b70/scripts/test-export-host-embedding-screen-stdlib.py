#!/usr/bin/env python3
"""Synthetic text-only exporter checks; never inspect or export active evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

path=Path(__file__).with_name('export-host-embedding-screen.py')
spec=importlib.util.spec_from_file_location('host_export_test',path)
exporter=importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def prereg():
    return {'campaign':exporter.CAMPAIGN,'max_requests':15,'packet_manifest_sha256':exporter.PACKET_SHA,
        'client_sha256':exporter.CLIENT_SHA,'validator_sha256':exporter.VALIDATOR_SHA,
        'registered_contract_sha256':exporter.CONTRACT_SHA,
        'inherited_v3_sha256':exporter.HELPERS['run-multiblock-screen-v3.py'],
        'frozen_helpers':{n:exporter.HELPERS[n] for n in ('profile-clip.py','compare-clip.py','run-stability.py')},
        'schedule':exporter.expected_schedule()}


def progress():
    return {'status':'passed','completed_requests':15,'speed_promotion':False,'streaming_qualification':False,
        'rows':[{**r,'status':'passed'} for r in exporter.expected_schedule()]}


class Tests(unittest.TestCase):
    def test_exact_fifteen_terminal_schedule(self):
        plan,rows=exporter.terminal_rows(progress(),prereg())
        self.assertEqual(len(rows),15)
        self.assertEqual([r['fixture'] for r in plan],['boat','boat','marble','bird','boat']*3)
        self.assertEqual(sum(r['initialization'] for r in plan),3)
    def test_running_and_incomplete_pass_rejected(self):
        for status,count in [('running',2),('passed',14)]:
            p=progress();p['status']=status;p['rows']=p['rows'][:count]
            with self.assertRaises(RuntimeError):exporter.terminal_rows(p,prereg(),True)
    def test_failed_requires_explicit_flag(self):
        p=progress();p['status']='failed';p['rows']=p['rows'][:2];p['rows'][-1]['status']='failed'
        with self.assertRaises(RuntimeError):exporter.terminal_rows(p,prereg())
        self.assertEqual(len(exporter.terminal_rows(p,prereg(),True)[1]),2)
    def test_old_schedule_or_source_refused(self):
        for field,value in [('max_requests',18),('client_sha256','0'*64),('schedule',[])]:
            r=prereg();r[field]=value
            with self.assertRaises(RuntimeError):exporter.terminal_rows(progress(),r)
    def test_prefix_order_refused(self):
        p=progress();p['rows'][1],p['rows'][2]=p['rows'][2],p['rows'][1]
        with self.assertRaises(RuntimeError):exporter.terminal_rows(p,prereg())
    def test_safe_path_rejects_symlinks_and_traversal(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'target').write_text('text');(root/'linked').symlink_to(root/'target')
            for p in (root/'linked',root/'..'/'escape'):
                with self.assertRaises(RuntimeError):exporter.read_stable(p)
    def test_tree_selects_text_only(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name in ('receipt.json','client.log','weights.safetensors','preview.mp4','kernel.so','cache.bin'):
                (root/name).write_text('x')
            selected=set();exporter.shared.add_tree(selected,root)
            self.assertEqual({p.name for p in selected},{'receipt.json','client.log'})
    def test_stable_read_is_bounded(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.json';p.write_text('12345')
            with self.assertRaises(RuntimeError):exporter.read_stable(p,limit=4)
            self.assertEqual(exporter.read_stable(p,limit=5)[0],b'12345')
    def test_partial_failure_json_preserved_as_text(self):
        p=exporter.ROOT/exporter.CAMPAIGN/'partial.json'
        text={exporter.archive_name(p):'{"incomplete":'}
        self.assertIn('export_parse_error',exporter.document(text,p,optional=True))
        with self.assertRaises(ValueError):exporter.document(text,p)
    def test_duplicate_json_and_nan_rejected(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}'):
            with self.assertRaises(RuntimeError):exporter.unique_json(text)
    def test_passed_retention_needs_exactly_three_previews_and_all_raw_deletions(self):
        plan=exporter.expected_schedule();inv={};receipts=[]
        for ordinal,row in enumerate(plan):
            run=row['run'];entries=[]
            for relative in (f'output/validation/{run}/tensors.safetensors',f'output/{run}/preview.mp4'):
                entry={'run':run,'relative_path':relative,'path':str(exporter.ROOT/relative),
                       'bytes':1,'sha256':'1'*64,'device':1,'inode':len(receipts)+1}
                entries.append(entry)
                if relative.endswith('.safetensors') or ordinal<12:
                    deletion={**entry,'action':'delete','parity_passed':True,'utc':'fixture'}
                    receipts.extend([{**deletion,'phase':'intent'},{**deletion,'phase':'completed'}])
            inv[run]=entries
        p=progress();p['retained_outputs']=[inv[row['run']][1] for row in plan[-3:]]
        text={exporter.archive_name(exporter.ROOT/exporter.CAMPAIGN/'output-inventory.json'):json.dumps(inv),
            exporter.archive_name(exporter.ROOT/exporter.CAMPAIGN/'deletion-receipts.jsonl'):'\n'.join(json.dumps(r) for r in receipts)}
        self.assertEqual(exporter.retention_summary(p,text,plan)['retained_preview_count'],3)
        p['retained_outputs'].append(inv[plan[0]['run']][0])
        with self.assertRaises(RuntimeError):exporter.retention_summary(p,text,plan)
    def test_failed_partial_retention_receipt_supported(self):
        text={exporter.archive_name(exporter.ROOT/exporter.CAMPAIGN/'deletion-receipts.jsonl'):'{"interrupted":'}
        report=exporter.retention_summary({'status':'failed'},text,exporter.expected_schedule())
        self.assertEqual(len(report['partial_text_parse_errors']),1)
    def test_no_native_import(self):
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main()
