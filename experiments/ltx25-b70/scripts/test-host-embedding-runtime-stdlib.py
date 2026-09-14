#!/usr/bin/env python3
"""No sealing: test graph, receipt closure, and checker source transformations."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

LANE = Path(__file__).resolve().parents[1]
path = LANE / 'scripts/prepare-host-embedding-runtime.py'
spec = importlib.util.spec_from_file_location('host_builder_under_test', path)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
CPU_PATH = builder.ROOT / 'host-embedding-cpu-integration-native-01/result.json'
RESIDENT_PATH = LANE / 'data/host-embedding-resident-source-01.json'
PACKET_EXISTED = builder.OUTPUT.exists()

class Tests(unittest.TestCase):
    def setUp(self):
        self.cpu = json.loads(CPU_PATH.read_text())
        self.resident = json.loads(RESIDENT_PATH.read_text())
        self.pins = {name: builder.sha(LANE / source) for name, source in builder.INPUTS.items()}
        self.control = json.loads((builder.PARENT / 'graphs/control.json').read_text())
    def test_actual_admissions_match_current_sources(self):
        builder.validate_admissions(self.cpu,self.resident,self.pins)
    def test_source_only_cpu_pass_rejected(self):
        self.cpu.update(status='passed-stdlib-source-check',native_cpu_tests_executed=False)
        with self.assertRaises(RuntimeError): builder.validate_admissions(self.cpu,self.resident,self.pins)
    def test_every_added_source_must_match_its_admission(self):
        for name in self.pins:
            with self.subTest(name=name):
                pins=dict(self.pins);pins[name]='0'*64
                with self.assertRaises(RuntimeError): builder.validate_admissions(self.cpu,self.resident,pins)
    def test_failures_skips_and_partial_tests_rejected(self):
        for field,value in [('test_errors',['error']),('test_failures',['failure']),('test_skips',['skip']),('tests_run',5)]:
            with self.subTest(field=field):
                cpu=copy.deepcopy(self.cpu);cpu[field]=value
                with self.assertRaises(RuntimeError): builder.validate_admissions(cpu,self.resident,self.pins)
    def test_accelerator_or_guard_failures_rejected(self):
        for field,value in [('xpu_initialized',True),('cuda_initialized',True),('native_gpu_requests',1),('final_guards_intact',False),('accelerator_guard_attempts',['blocked'])]:
            with self.subTest(field=field):
                cpu=copy.deepcopy(self.cpu);cpu[field]=value
                with self.assertRaises(RuntimeError): builder.validate_admissions(cpu,self.resident,self.pins)
    def test_missing_or_repeated_import_omission_rejected(self):
        for omissions in ([],self.cpu['cpu_comfy_import_omissions']*2):
            cpu=copy.deepcopy(self.cpu);cpu['cpu_comfy_import_omissions']=omissions
            with self.assertRaises(RuntimeError): builder.validate_admissions(cpu,self.resident,self.pins)
    def test_graphs_change_only_two_node_classes_and_mode_fields(self):
        original=copy.deepcopy(self.control)
        for mode in ('control','host-table'):
            graph=builder.graph_source(self.control,mode)
            self.assertEqual(set(graph),set(original))
            self.assertEqual({name for name in graph if graph[name]!=original[name]}, {'420','421'})
            for name,clazz in [('420','LTXHostEmbeddingComponents'),('421','LTXHostEmbeddingPlacementCheck')]:
                self.assertEqual(graph[name]['class_type'],clazz)
                self.assertEqual(graph[name]['inputs'].pop('encoder_mode'),mode)
                graph[name]['inputs']['encoder_variant']='control'
                graph[name]['class_type']=original[name]['class_type']
            self.assertEqual(graph,original)
        self.assertEqual(self.control,original)
    def test_graph_wrong_original_recipe_refused(self):
        self.control['420']['inputs']['placement']='single'
        with self.assertRaises(RuntimeError): builder.graph_source(self.control,'host-table')
    def test_checker_preserves_ancestry_and_na_closure(self):
        original=(builder.PARENT/builder.CHECKER).read_text()
        updated=builder.checker_source(original,{'fixture':'source-generation-only'})
        ast.parse(updated)
        self.assertIn("manifest['na_axis_parent_manifest_sha256'] == '"+builder.NA_PARENT_SHA+"'",updated)
        self.assertIn("manifest['parent_manifest_sha256'] == '"+builder.PARENT_SHA+"'",updated)
        def function(text,name):
            return ast.dump(next(node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef) and node.name==name))
        self.assertEqual(function(original,'verify_na_source_closure'),function(updated,'verify_na_source_closure'))
        self.assertIn("'ltx_host_embedding_lab': 'host_embedding_resident_node.py'",updated)
        self.assertEqual(updated.count("'ltx_host_embedding_lab':"),1)
    def test_changed_checker_context_fails_closed(self):
        original=(builder.PARENT/builder.CHECKER).read_text()
        with self.assertRaises(RuntimeError): builder.checker_source(original.replace('import ast\n',''),{})
    def test_no_native_import_and_no_packet_created(self):
        self.assertNotIn('torch',sys.modules)
        self.assertEqual(builder.OUTPUT.exists(), PACKET_EXISTED)

if __name__=='__main__': unittest.main()
