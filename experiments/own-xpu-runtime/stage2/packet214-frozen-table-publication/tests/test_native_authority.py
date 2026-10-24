"""Offline compile-only evidence; never invokes the production executable."""
import hashlib,json
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class NativeAuthority(unittest.TestCase):
    def test_native_closure_reuses_parent_and_actual_cpu_publisher(self):
        b=read(P/'evidence/build-compile-only.json');self.assertTrue(b['passed'] and b['compile_only'] and b['public_entry_disabled'])
        for key in ('fixture_executed','device_enumerated','device_executed','model_executed'):self.assertFalse(b[key])
        for group in ('artifact_sha256','source_sha256'):
            for path,want in b[group].items():self.assertEqual(sha(ROOT/path),want,path)
        plan=b['plan'];parent=read(P.parent/'packet213-production-prefill-control/evidence/build-compile-only.json')
        self.assertEqual(plan['objects'],parent['plan']['objects'])
        for path,want in plan['repository_dependencies'].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in plan['objects'].items():self.assertEqual(sha(path),want,path)
        for name in ('object','binary'):self.assertEqual(sha(plan[name]),plan[name+'_sha256'])
        key=str((P/'publication.hpp').relative_to(ROOT));cpu=read(P/'evidence/cpu-build.json');self.assertEqual(plan['repository_dependencies'][key],cpu['source_sha256'][key])
        for key in ('parent_source_sha256','source_sha256'):
            for path,want in b['generated'][key].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in b['generated']['outputs'].items():self.assertEqual(sha(P/path),want,path)
        publication=next(path for path in plan['repository_dependencies'] if path.endswith('/native/publish.hpp'))
        self.assertIn(publication,cpu['repository_dependencies']);self.assertEqual(plan['repository_dependencies'][publication],cpu['repository_dependencies'][publication])
    def test_same_binary_reinspection_preserves_compilation_lineage(self):
        b=read(P/'evidence/build-compile-only.json');self.assertTrue(b['inspection_only']);self.assertFalse(b['compiled'])
        provenance=b['compilation_provenance'];oldpath=ROOT/provenance['receipt'];self.assertEqual(sha(oldpath),provenance['receipt_sha256']);old=read(oldpath)
        self.assertFalse(old['passed']);self.assertEqual(old['error'],provenance['original_error']);self.assertIn('shared publication helper missing',old['error'])
        self.assertEqual(provenance['commands'],old['plan']['commands']);self.assertEqual(provenance['commands'],b['plan']['commands'])
        for name in ('binary_sha256','object_sha256'):self.assertEqual(old['plan'][name],b['plan'][name])
        for path,want in old['artifact_sha256'].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in provenance['source_sha256'].items():
            self.assertEqual(sha(oldpath.parent/Path(path).name),want,path)
        logs=[ROOT/path for path in b['artifact_sha256'] if path.endswith('/publisher-disassembly.log')];self.assertEqual(len(logs),1);assembly=logs[0].read_text()
        self.assertIn('Engine::publish_cache_table',assembly);self.assertIn('ownrt::CopyEngine::copy',assembly);self.assertIn('ownrt::Device::compute(ownrt::Operation const&',assembly)
        self.assertTrue(any('p58v7Publish' in name for name in b['offline_image']['kernel_entries']))
    def test_public_main_refuses_and_offline_sycl_registration(self):
        b=read(P/'evidence/build-compile-only.json');entry=(P/'build/native/entry-main.cpp').read_text();public=entry[entry.index('int main(int,char**)'):]
        self.assertIn('return 64;',public);self.assertNotIn('p214_future_entry(',public);self.assertNotIn('p214_model_body(',public)
        logs=[ROOT/path for path in b['artifact_sha256'] if path.endswith('public-main-disassembly.log')];self.assertEqual(len(logs),1)
        assembly=logs[0].read_text();self.assertIn('<main>:',assembly);self.assertIn('$0x40,%eax',assembly);self.assertNotIn('p214_future_entry',assembly)
        image=b['offline_image'];self.assertTrue(image['linked_qualification_symbol'] and image['linked_sycl_registration'])
        self.assertTrue({'_ZTSN4p20816NativePairKernelILj10240EEE','_ZTSN4p20816NativePairKernelILj6144EEE'}<=set(image['kernel_entries']))
        self.assertEqual(sha(P/'build/native/pair-device.bc'),image['bitcode_sha256'])
        for path,want in image['symbol_files'].items():self.assertEqual(sha(ROOT/path),want,path)
if __name__=='__main__':unittest.main()
