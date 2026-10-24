"""Offline compile-only closure checks. Never calls the native executable."""
import hashlib,json
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[1];ROOT=P.parents[3]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
class NativeAuthority(unittest.TestCase):
    def test_native_source_objects_and_cpu_shared_headers_exact(self):
        b=read(P/'evidence/build-compile-only.json');self.assertTrue(b['passed'] and b['compile_only'] and b['public_entry_disabled'])
        for key in ('fixture_executed','device_enumerated','device_executed','model_executed'):self.assertFalse(b[key])
        for group in ('artifact_sha256','source_sha256'):
            for path,want in b[group].items():self.assertEqual(sha(ROOT/path),want,path)
        plan=b['plan'];self.assertEqual(len(plan['repository_dependencies']),103);self.assertEqual(len(plan['objects']),38)
        for path,want in plan['repository_dependencies'].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in plan['objects'].items():self.assertEqual(sha(path),want,path)
        for name in ('object','binary'):self.assertEqual(sha(plan[name]),plan[name+'_sha256'])
        cpu=read(P/'evidence/cpu-build.json')
        for name in ('production_control.hpp','cache_transition.hpp'):
            key=str((P/name).relative_to(ROOT));self.assertEqual(plan['repository_dependencies'][key],cpu['source_sha256'][key])
        for key in ('parent_source_sha256','source_sha256'):
            for path,want in b['generated'][key].items():self.assertEqual(sha(ROOT/path),want,path)
        for path,want in b['generated']['outputs'].items():self.assertEqual(sha(P/path),want,path)
    def test_disabled_main_and_offline_kernel_identity(self):
        b=read(P/'evidence/build-compile-only.json');entry=(P/'build/native/entry-main.cpp').read_text();public=entry[entry.index('int main(int,char**)'):]
        self.assertIn('return 64;',public);self.assertNotIn('p213_future_entry(',public);self.assertNotIn('p213_model_body(',public)
        logs=[ROOT/path for path in b['artifact_sha256'] if path.endswith('public-main-disassembly.log')];self.assertEqual(len(logs),1)
        assembly=logs[0].read_text();self.assertIn('<main>:',assembly);self.assertIn('$0x40,%eax',assembly);self.assertNotIn('p213_future_entry',assembly)
        image=b['offline_image'];self.assertTrue(image['linked_qualification_symbol'] and image['linked_sycl_registration'])
        self.assertTrue({'_ZTSN4p20816NativePairKernelILj10240EEE','_ZTSN4p20816NativePairKernelILj6144EEE'}<=set(image['kernel_entries']))
        self.assertEqual(sha(P/'build/native/pair-device.bc'),image['bitcode_sha256'])
        for path,want in image['symbol_files'].items():self.assertEqual(sha(ROOT/path),want,path)
if __name__=='__main__':unittest.main()
