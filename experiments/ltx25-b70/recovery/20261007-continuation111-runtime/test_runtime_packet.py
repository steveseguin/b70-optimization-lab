"""CPU source-assembly controls. Never materialize a packet or call a launcher."""
import ast
import copy
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('continuation111_packet_tests',HERE/'runtime_packet.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)


def literal(raw,name):
    tree=ast.parse(raw)
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))


class PacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=json.loads((B.PARENT/'manifest.json').read_bytes())
        cls.plan_raw=B.PLAN.read_bytes()
        cls.changed=B.successor_files(HERE,cls.plan_raw)
        cls.inventory=B.input_inventory()

    def test_parent_and_banked_helper_bytes(self):
        self.assertEqual(B.digest((B.PARENT/'manifest.json').read_bytes()),B.PARENT_SHA)
        origins={'continuation_anchor.py':HERE.parent/'20261007-continuation111-reference/anchor.py',
                 'conditioning_guard.py':HERE.parent/'20261007-continuation111-safety/conditioning_guard.py',
                 'encode_safety.py':HERE.parent/'20261007-continuation111-safety/encode_safety.py',
                 'capture_adapter.py':HERE.parent/'20261007-continuation111-safety/capture_adapter.py'}
        for name,path in origins.items():
            with self.subTest(name=name):self.assertEqual((HERE/name).read_bytes(),path.read_bytes())
        self.assertEqual(B.NODES,B.BASE.NODES)
        self.assertEqual(B.NODES.count('ltx_resolution_lab'),1)

    def test_all_components_and_runtime_aliases_are_bound(self):
        for name in B.COMPONENTS:
            raw=(HERE/name).read_bytes()
            self.assertEqual(self.changed['resolution/components/'+name],raw)
            self.assertEqual(self.inventory[name],B.digest(raw))
            if name in B.MODULES:self.assertEqual(self.changed['source/scripts/'+B.MODULES[name]],raw)
        self.assertEqual(self.changed[B.COMMON],(HERE/'runtime_packet.py').read_bytes())
        self.assertNotIn('source/scripts/runtime_packet.py',self.changed)
        self.assertEqual(self.changed['source/scripts/ltx_resolution_session.py'],(HERE/'session.py').read_bytes())
        self.assertNotIn('source/scripts/session.py',self.changed)
        self.assertNotIn('torch',sys.modules)

    def test_launcher_changes_only_fixed_identity_not_lifecycle_or_safety(self):
        parent=(B.PARENT/B.LAUNCHER).read_bytes()
        expected=parent.replace(
            b"run_name == 'encoder-server-duration-full-110-two-way20-28-w2-b1-p1-dxpu2-s640x384-f49'",
            ('run_name == '+repr(B.RUN_NAME)).encode(),1).replace(
            b'Packet101 admits only the reviewed W2 same-size reference experiment',
            b'Packet111 admits only the fixed native continuation reference',1)
        self.assertEqual(self.changed[B.LAUNCHER],expected)
        tree=ast.parse(expected)
        names={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute) and
               isinstance(n.value,ast.Name) and n.value.id=='common'}
        for name in names:
            with self.subTest(common_attribute=name):self.assertIsNotNone(getattr(B,name))
        self.assertEqual(B.RUN_ALLOWANCE,4*2**30)
        self.assertEqual(B.BUILD_ALLOWANCE,384*2**20)

    def test_inherited_loader_keeps_single_registration_and_new_mapping(self):
        loader=(B.PARENT/'source/custom_nodes/ltx_resolution_lab/__init__.py').read_bytes()
        self.assertEqual(loader,b'from integration import NODE_CLASS_MAPPINGS, install_routes\ninstall_routes()\n')
        tree=ast.parse(self.changed['source/scripts/integration.py'])
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and
                  any(isinstance(t,ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in n.targets))
        self.assertIsInstance(node.value,ast.DictComp)
        self.assertEqual({n.id for n in node.value.generators[0].iter.elts},
            {'LTXResolutionPrepareNative','LTXContinuationAnchor111','LTXContinuationCondition111'})
        self.assertNotIn('source/custom_nodes/ltx_resolution_lab/__init__.py',self.changed)

    def test_geometry_changes_only_plan_and_workload_identity(self):
        path='source/scripts/ltx_output_size_98.py';parent=(B.PARENT/path).read_bytes()
        oldplan=b'cafb272fcb182d80022a0e73eff838dc7fd0aeb5001704d0b9ccbd37fadeccab'
        oldqid=b'28ad14c062af8e5bf80b904a895f422a76ccf6c95c176d5630b23a4027097560'
        self.assertEqual(self.changed[path],parent.replace(oldplan,B.PLAN_SHA.encode(),1).replace(oldqid,B.QID.encode(),1))
        self.assertEqual(literal(self.changed[path],'_RESOLUTION_PLAN_SHA256'),B.PLAN_SHA)
        self.assertEqual(literal(self.changed[path],'_RESOLUTION_QUALIFICATION_ID'),B.QID)
        self.assertEqual(literal(self.changed[path],'_RESOLUTION_MODE'),'same-size-native-v1')

    def test_encode_decode_refusals_and_decoder_pin_mirrors(self):
        raw=self.changed['source/comfy/sd.py'];tree=ast.parse(raw)
        vae=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='VAE')
        for name in ('encode','decode'):
            fn=next(n for n in vae.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                                 and n.func.attr=='reject_oom' for n in ast.walk(fn)),1)
        canonical=self.changed['source/scripts/na_axis_decode_node.py']
        self.assertEqual(canonical,self.changed['source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'])
        self.assertEqual(literal(canonical,'SD_SHA'),B.digest(raw))
        for path in ('source/scripts/capture_node.py','source/custom_nodes/ltx_baseline_capture/__init__.py'):
            self.assertNotIn(path,self.changed)

    def test_capture_helper_six_full_roles_and_no_tensor_arithmetic_delta(self):
        raw=self.changed['source/scripts/ltx_duration_guard.py'];namespace={}
        exec(compile(raw,'synthetic_guard_source','exec'),namespace)
        self.assertEqual(namespace['RAW_CAPTURE_BUDGET'],877383216)
        self.assertEqual(namespace['WRITE_ALLOWANCE'],4*2**30)
        plan=json.loads(self.plan_raw)['plan']
        rows=[{'name':r['name'],'graph_sha256':r['graph_sha256'],'role':'full'}
              for r in plan['requests'] if r['capture_role']=='full']
        guard=namespace['CaptureGuard'](B.PLAN_SHA,rows,lambda:None)
        self.assertEqual(guard.receipt()['capture_cap'],6)
        with self.assertRaises(RuntimeError):namespace['CaptureGuard'](B.PLAN_SHA,rows[:-1],lambda:None)

    def test_manifest_preserves_every_replaced_original_and_updates_active_pins(self):
        files=B.manifest_files(self.parent,self.changed)
        for path,raw in self.changed.items():
            self.assertEqual(files[path],B.digest(raw))
            if path in self.parent['files']:
                self.assertEqual(files['provenance/packet110/'+path],self.parent['files'][path])
        untouched=set(self.parent['files'])-set(self.changed)
        self.assertTrue(all(files[p]==self.parent['files'][p] for p in untouched))
        change=B.transition(self.parent,self.changed,self.inventory,{'admitted':True})
        manifest=B.semantic_manifest(self.parent,files,change)
        self.assertEqual(manifest['runtime'],self.parent['runtime'])
        self.assertEqual(manifest['model_verification_sha256'],self.parent['model_verification_sha256'])
        self.assertEqual(manifest['startup_tools'],{Path(k).name:files[k] for k in (B.COMMON,B.LAUNCHER)})
        self.assertEqual(manifest['output_size']['module_sha256'],files['source/scripts/ltx_output_size_98.py'])
        for name in B.MODULES.values():self.assertEqual(manifest['extension_sha256s'][name],files['source/scripts/'+name])
        self.assertEqual(manifest['resolution101']['control']['requests'],8)
        self.assertEqual(manifest['resolution101']['control']['full_captures'],6)
        self.assertFalse(manifest['resolution101']['qualification'])

    def test_inherited_activation_preserves_serializer_and_original_baseline(self):
        activate=Mock(return_value='activated')
        with patch.object(B.BASE.BASE,'activate_dependencies',activate), \
             patch.object(B.BASE,'sha',side_effect=lambda p:B.BASE.SERIALIZER_FILES[str(p)]):
            self.assertEqual(B.activate_dependencies(B.PACKET,self.parent),'activated')
        supplied=activate.call_args.args[1]
        self.assertEqual(supplied['runtime'],B.BASE._parent_manifest['runtime'])
        self.assertTrue(set(B.BASE.SERIALIZER_FILES)<=set(self.parent['runtime']['files']))

    def test_run_storage_override_is_four_not_inherited_nine_gib(self):
        inspect=Mock(return_value={'admitted':True})
        with patch.object(B,'module',return_value=SimpleNamespace(inspect_destination=inspect)):
            self.assertEqual(B.admit_storage(B.PACKET,B.ROOT/B.RUN_NAME),{'admitted':True})
        inspect.assert_called_once_with(B.ROOT/B.RUN_NAME,50*2**30,4*2**30)

    def test_build_refuses_unreviewed_inventory_before_any_writes(self):
        with patch.object(B,'inspect_assembly',return_value={'input_inventory_sha256':'a'*64}), \
             patch.object(B,'write_new',side_effect=AssertionError('must not write')):
            with self.assertRaisesRegex(RuntimeError,'Reviewed111 inputs differ'):B.build('b'*64)

    def test_build_storage_refusal_precedes_materialization(self):
        inspect=Mock(return_value={'admitted':False})
        result={'input_inventory_sha256':'a'*64,'input_inventory':self.inventory}
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'never-created'
            with patch.object(B,'PACKET',target),patch.object(B,'inspect_assembly',return_value=result), \
                 patch.object(B.BASE,'verify_packet',return_value=self.parent), \
                 patch.object(B,'successor_files',return_value=self.changed), \
                 patch.object(B,'input_inventory',return_value=self.inventory), \
                 patch.object(B,'module',return_value=SimpleNamespace(inspect_destination=inspect)), \
                 patch.object(B,'write_new',side_effect=AssertionError('must not write')):
                with self.assertRaisesRegex(RuntimeError,'384MiB'):B.build('a'*64)
            self.assertFalse(target.exists())
        inspect.assert_called_once_with(target,54*2**30,384*2**20)

    def test_rehashed_plan_and_changed_source_anchor_refused(self):
        envelope=json.loads(self.plan_raw);envelope['plan']['budget']['max_captures']=7
        envelope['plan_sha256']=B.digest(B.canonical(envelope['plan']))
        with self.assertRaises(RuntimeError):B.check_plan(B.canonical(envelope))
        with self.assertRaises(RuntimeError):B.replace_once(b'xx',b'x',b'y')

    def verify_virtual(self, *, mutate=None, bad_file=None, extra_file=False):
        """Exercise verifier with metadata and hash observations, never a packet copy."""
        files=B.manifest_files(self.parent,self.changed)
        change=B.transition(self.parent,self.changed,self.inventory,{'admitted':True})
        manifest=B.semantic_manifest(self.parent,files,change)
        if mutate:mutate(manifest)
        raw=B.canonical(manifest);manifest_sha=B.digest(raw)
        hashes={B.PACKET/p:h for p,h in manifest['files'].items()}
        hashes[B.PACKET/'manifest.json']=manifest_sha
        if bad_file:hashes[B.PACKET/bad_file]='0'*64
        payloads={B.PACKET/'manifest.json':raw,B.PACKET/'STATUS.txt':B.STATUS,
                  B.PACKET/'resolution/candidate-plan.json':self.plan_raw}
        inventory=set(files)|{'manifest.json','STATUS.txt'}
        if extra_file:inventory.add('source/scripts/unbound.py')
        rebuild=Mock(return_value=self.changed)
        with ExitStack() as stack:
            stack.enter_context(patch.object(B,'sha',side_effect=lambda p:hashes[Path(p)]))
            stack.enter_context(patch.object(B,'regular',side_effect=lambda p:payloads[Path(p)]))
            stack.enter_context(patch.object(B.BASE,'verify_packet',return_value=self.parent))
            stack.enter_context(patch.object(B,'successor_files',rebuild))
            stack.enter_context(patch.object(B,'module',return_value=SimpleNamespace(inventory=lambda p:inventory)))
            try:return B.verify_packet(B.PACKET,manifest_sha)
            finally:
                if bad_file:rebuild.assert_not_called()

    def test_verify_reconstructs_exact_semantics_and_source_closure(self):
        result=self.verify_virtual()
        self.assertEqual(result['resolution101']['parent_manifest_sha256'],B.PARENT_SHA)
        self.assertEqual(result['resolution101']['input_inventory'],self.inventory)

    def test_verify_refuses_source_drift_before_loading_helpers(self):
        with self.assertRaisesRegex(RuntimeError,'before component import'):
            self.verify_virtual(bad_file='resolution/components/encode_safety.py')

    def test_verify_refuses_rehashed_false_closure_unbound_files_and_semantics(self):
        mutations=[lambda m:m['files'].__setitem__('source/scripts/proof.py','0'*64),
                   lambda m:m['resolution101']['control'].__setitem__('requests',9),
                   lambda m:m['resolution101']['storage_admission'].__setitem__('admitted',False),
                   lambda m:m['extension_sha256s'].__setitem__('ltx_resolution_session.py','0'*64)]
        for mutate in mutations:
            with self.subTest(mutation=mutate),self.assertRaises(RuntimeError):self.verify_virtual(mutate=mutate)
        with self.assertRaisesRegex(RuntimeError,'Unbound111 packet file'):self.verify_virtual(extra_file=True)


if __name__=='__main__':unittest.main()
