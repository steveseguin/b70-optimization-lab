"""Tiny authenticated fixtures only: no real model reads or device execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import prepare as prep


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = self.root/'profile'; self.assets.mkdir()
        self.model = self.root/'model'; self.model.mkdir()
        self.draft = self.root/'draft'; self.draft.mkdir()
        self.out = self.root/'deployment'
        self.target_bytes = b'HEADER00' + b'abcdefgh'
        self.draft_bytes = b'prefix00' + b'\x00\x01\x02\x03'
        (self.model/'a.gguf').write_bytes(self.target_bytes)
        (self.draft/'a.safetensors').write_bytes(self.draft_bytes)
        (self.draft/'tokenizer.json').write_bytes(b'{"tiny":true}')
        placement = b'a.gguf blk.0.weight gdn 0 0 8 0 1 1 2\n'
        tensors = ('mtp.weight a.safetensors 8 4 BF16 2 1 '+prep.digest(self.draft_bytes[8:])+'\n').encode()
        template = b'{{ message }}'
        for name, raw in [('placement.tsv',placement),('draft-tensors.tsv',tensors),('chat-template.jinja',template)]:
            (self.assets/name).write_bytes(raw)
        asset = lambda name:dict(file=name,sha256=prep.digest((self.assets/name).read_bytes()))
        self.profile = dict(schema='ownrt.portable-model-profile.v1',id='tiny-test',architecture='qwen4exp',native_context=4096,activation_dtype='F32',
            target=dict(shards=[dict(name='a.gguf',bytes=len(self.target_bytes),sha256=prep.digest(self.target_bytes),header_bytes=8,header_sha256=prep.digest(self.target_bytes[:8]),data_start=8)],placement=dict(**asset('placement.tsv'),tensor_count=1)),
            draft=dict(shards=[dict(name='a.safetensors',bytes=len(self.draft_bytes),sha256=prep.digest(self.draft_bytes))],tensors=dict(**asset('draft-tensors.tsv'),tensor_count=1)),
            tokenizer=dict(file='tokenizer.json',sha256=prep.digest((self.draft/'tokenizer.json').read_bytes()),chat_template=asset('chat-template.jinja')))
        self.profile_path = self.assets/'profile.json'
        self.pin()

    def pin(self):
        self.profile_path.write_bytes(prep.encoded(self.profile))
        self.sha = prep.digest(self.profile_path.read_bytes())

    def run_prepare(self, **kwargs):
        return prep.prepare(self.profile_path,self.sha,self.model,self.out,**kwargs)

    def validate(self):
        return prep.validate_overlay(self.out/'include',self.sha,prep.digest((self.out/'binding.json').read_bytes()))

    def test_target_draft_tokenizer_rebind_and_overlay(self):
        result=self.run_prepare(draft_root=self.draft,tokenizer_root=self.draft)
        self.assertFalse(result['device_executed'])
        self.assertEqual(result['profile_sha256'],self.sha)
        self.assertEqual(result['shards']['target']['a.gguf']['ino'],(self.model/'a.gguf').stat().st_ino)
        fields=(self.out/'draft-manifest.tsv').read_text().split()
        self.assertEqual(len(fields),13)
        self.assertEqual(int(fields[10]),(self.draft/'a.safetensors').stat().st_ino)
        checked=self.validate()
        self.assertEqual(checked['header_sha256'],result['artifacts']['include/'+prep.HEADER])
        self.assertEqual((self.out/'placement.tsv').read_bytes(),(self.assets/'placement.tsv').read_bytes())

    def test_wrong_independent_digest_refused_before_output(self):
        with self.assertRaisesRegex(ValueError,'trusted profile'):
            prep.prepare(self.profile_path,'0'*64,self.model,self.out)
        self.assertFalse(self.out.exists())

    def test_candidate_placement_cannot_replace_trusted_descriptors(self):
        (self.assets/'placement.tsv').write_text('untrusted candidate')
        with self.assertRaisesRegex(ValueError,'asset hash'):
            self.run_prepare()
        self.assertFalse(self.out.exists())

    def test_corrupt_shard_and_header_refused(self):
        (self.model/'a.gguf').write_bytes(self.target_bytes[:-1]+b'X')
        with self.assertRaisesRegex(ValueError,'full shard'):
            self.run_prepare()
        (self.model/'a.gguf').write_bytes(self.target_bytes)
        self.profile['target']['shards'][0]['header_sha256']='0'*64;self.pin()
        with self.assertRaisesRegex(ValueError,'header SHA'):
            self.run_prepare()
        self.assertFalse(self.out.exists())

    def test_draft_payload_independently_verified(self):
        (self.assets/'draft-tensors.tsv').write_text('mtp.weight a.safetensors 8 4 BF16 2 1 '+'0'*64+'\n')
        self.profile['draft']['tensors']['sha256']=prep.digest((self.assets/'draft-tensors.tsv').read_bytes());self.pin()
        with self.assertRaisesRegex(ValueError,'draft payload'):
            self.run_prepare(draft_root=self.draft)
        self.assertFalse(self.out.exists())

    def test_symlink_model_and_symlink_directory_refused(self):
        original=self.model/'a.gguf';original.rename(self.model/'real.gguf');original.symlink_to('real.gguf')
        with self.assertRaises(OSError):self.run_prepare()
        original.unlink();(self.model/'real.gguf').rename(original)
        linked=self.root/'linked';linked.symlink_to(self.model,target_is_directory=True)
        with self.assertRaises(OSError):prep.prepare(self.profile_path,self.sha,linked,self.out)

    def test_path_replacement_during_held_hash_refused(self):
        read=prep.HeldFile.read; replaced=False
        def substitute(held,offset,size,deadline):
            nonlocal replaced
            raw=read(held,offset,size,deadline)
            if held.name=='a.gguf' and not replaced:
                replacement=self.model/'replacement';replacement.write_bytes(self.target_bytes)
                replacement.replace(self.model/'a.gguf');replaced=True
            return raw
        with mock.patch.object(prep.HeldFile,'read',substitute):
            with self.assertRaisesRegex(ValueError,'changed|replaced'):self.run_prepare()
        self.assertFalse(self.out.exists())

    def test_content_mutation_during_held_hash_refused(self):
        read=prep.HeldFile.read; changed=False
        def mutate(held,offset,size,deadline):
            nonlocal changed
            raw=read(held,offset,size,deadline)
            if held.name=='a.gguf' and not changed:
                with (self.model/'a.gguf').open('r+b') as stream:stream.write(b'X')
                changed=True
            return raw
        with mock.patch.object(prep.HeldFile,'read',mutate):
            with self.assertRaisesRegex(ValueError,'changed'):self.run_prepare()
        self.assertFalse(self.out.exists())

    def test_bounded_timeout_and_existing_output(self):
        with prep.Directory(self.model) as directory, prep.HeldFile(directory,'a.gguf') as held:
            with self.assertRaisesRegex(ValueError,'deadline'):held.hash_range(0,16,0)
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError,'fresh'):self.run_prepare()

    def test_offline_plan_reads_no_payload_and_creates_nothing(self):
        read=prep.HeldFile.read
        def metadata_only(held,*args):
            self.assertNotIn(held.name,('a.gguf','a.safetensors','tokenizer.json'))
            return read(held,*args)
        with mock.patch.object(prep.HeldFile,'read',metadata_only):
            result=prep.plan(self.profile_path,self.sha,self.model,self.out,self.draft,self.draft)
        self.assertEqual(result['model_payload_bytes_read'],0)
        self.assertEqual(result['full_file_hash_bytes'],16+12+len(b'{"tiny":true}'))
        self.assertEqual(result['additional_prefix_and_payload_hash_bytes'],8+4)
        self.assertFalse(self.out.exists())

    def test_fifo_and_bad_descriptor_refused(self):
        (self.model/'a.gguf').unlink();os.mkfifo(self.model/'a.gguf')
        with self.assertRaisesRegex(ValueError,'regular file'):self.run_prepare()
        (self.model/'a.gguf').unlink();(self.model/'a.gguf').write_bytes(self.target_bytes)
        (self.assets/'placement.tsv').write_text('a.gguf blk.0.weight gdn 0 7 8 0 1 1 2\n')
        self.profile['target']['placement']['sha256']=prep.digest((self.assets/'placement.tsv').read_bytes());self.pin()
        with self.assertRaisesRegex(ValueError,'placement range'):self.run_prepare()

    def test_extra_overlay_or_changed_header_refused(self):
        self.run_prepare();self.validate()
        extra=self.out/'include'/'poison.hpp';extra.write_text('#error poisoned')
        with self.assertRaisesRegex(ValueError,'extra generated'):self.validate()
        extra.unlink()
        header=self.out/'include'/prep.HEADER;header.write_text('untrusted')
        with self.assertRaisesRegex(ValueError,'artifact hash'):self.validate()

    def test_authority_generation_never_reopens_artifacts_unbounded(self):
        with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('unbounded pathname reopen')):
            result=self.run_prepare()
            checked=prep.validate_overlay(self.out/'include',self.sha,prep.digest(prep.read_small(self.out/'binding.json')))
        self.assertEqual(checked['header_sha256'],result['artifacts']['include/'+prep.HEADER])
        self.assertNotIn('binding.json',result['artifacts'])

    def test_edited_binding_needs_independent_pin(self):
        self.run_prepare();binding=self.out/'binding.json';pin=prep.digest(binding.read_bytes())
        binding.write_text(binding.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'binding SHA'):
            prep.validate_overlay(self.out/'include',self.sha,pin)

    def test_relocation_retains_portable_profile_but_changes_local_authority(self):
        first=self.run_prepare();other=self.root/'copy';shutil.copytree(self.model,other)
        second_out=self.root/'deployment2'
        second=prep.prepare(self.profile_path,self.sha,other,second_out)
        self.assertEqual(first['profile_sha256'],second['profile_sha256'])
        self.assertNotEqual(first['target_root'],second['target_root'])
        self.assertNotEqual(first['artifacts']['include/'+prep.HEADER],second['artifacts']['include/'+prep.HEADER])

    @unittest.skipUnless(shutil.which('g++'),'g++ not installed')
    def test_generated_header_compiles_with_actual_loader_declarations(self):
        self.run_prepare()
        engine=prep.HERE.parent
        source=self.root/'authority.cpp'
        source.write_text('#include "stage2/packet2/loader/gguf.hpp"\n#include "'+prep.HEADER+'"\nint main(){return gsq::bound::expected_plan().size()!=1;}\n')
        result=subprocess.run(['g++','-std=c++20','-DOWN_RT_HOST_ONLY','-fsyntax-only','-I',str(self.out/'include'),'-I',str(engine/'src'),str(source)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr[-5000:])

    @unittest.skipUnless(shutil.which('g++') and Path('/usr/include/openssl/evp.h').exists(),'CPU compiler/OpenSSL headers unavailable')
    def test_native_authority_accepts_rebinding_and_refuses_mutated_input(self):
        self.run_prepare();engine=prep.HERE.parent
        source=self.root/'authenticate.cpp';binary=self.root/'authenticate'
        source.write_text('#include "stage2/packet2/loader/gguf.hpp"\n#include "'+prep.HEADER+'"\n#include <openssl/evp.h>\n'
            'std::string hash(const std::vector<uint8_t>& b){unsigned char d[32];unsigned n=0;if(!EVP_Digest(b.data(),b.size(),d,&n,EVP_sha256(),nullptr)||n!=32)throw std::runtime_error("sha");std::string s;for(auto x:d){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}\n'
            'int main(){try{auto r=gsq::bound::authenticate(gsq::bound::placement_path,gsq::bound::auth_path,gsq::bound::model_root,hash);return r.admission.expected.size()!=1;}catch(...){return 9;}}\n')
        result=subprocess.run(['g++','-std=c++20','-DOWN_RT_HOST_ONLY','-I',str(self.out/'include'),'-I',str(engine/'src'),str(source),'-lcrypto','-o',str(binary)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr[-3000:])
        self.assertEqual(subprocess.run([str(binary)],timeout=3).returncode,0)
        with (self.out/'placement.tsv').open('a') as stream:stream.write('untrusted candidate\n')
        self.assertEqual(subprocess.run([str(binary)],timeout=3).returncode,9)
        (self.out/'placement.tsv').write_bytes((self.assets/'placement.tsv').read_bytes())
        (self.model/'a.gguf').unlink();os.mkfifo(self.model/'a.gguf')
        self.assertEqual(subprocess.run([str(binary)],timeout=3).returncode,9)
        (self.model/'a.gguf').unlink();(self.model/'a.gguf').write_bytes(self.target_bytes)
        (self.out/'placement.tsv').unlink();os.mkfifo(self.out/'placement.tsv')
        self.assertEqual(subprocess.run([str(binary)],timeout=3).returncode,9)

    def test_checked_in_current_profile_has_no_local_bindings(self):
        path=prep.HERE.parent/'profiles/sc117-iq3s/profile.json'
        raw=path.read_bytes();expected=(path.parent/'profile.sha256').read_text().split()[0]
        profile,_,_,rows,draft,_=prep.load_profile(path,expected)
        self.assertEqual(len(rows),1224);self.assertEqual(len(draft),3101)
        self.assertEqual(sum(s['bytes'] for s in profile['target']['shards']),83863586496)
        self.assertEqual(sum(s['bytes'] for s in profile['draft']['shards']),30047461616)
        for forbidden in (b'/home/',b'/mnt/',b'"ino"',b'"mtime_ns"',b'"dev"'):
            self.assertNotIn(forbidden,raw)


class BuildTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('ownrt_build',prep.HERE.parent/'build.py')
        self.build=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.build)

    def test_default_flags_unchanged_and_overlay_precedes_source(self):
        manifest=dict(compiler='icpx');unit=dict(object='a.o',source='a.cpp',flags=['-O3'])
        baseline=self.build.compile_command(manifest,unit,Path('/tmp/build'))
        generated=self.build.compile_command(manifest,unit,Path('/tmp/build'),Path('/tmp/deployment/include'))
        self.assertEqual(baseline[:4],['icpx','-O3','-I',str(self.build.SRC)])
        self.assertEqual(generated[2:6],['-I','/tmp/deployment/include','-I',str(self.build.SRC)])

    def test_depfile_distinguishes_overlay_and_source_with_spaces(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'a.d';overlay=Path(td)/'space include'
            canonical=self.build.SRC/'some.hpp';header=overlay/prep.HEADER
            escape=lambda x:str(x).replace(' ','\\ ')
            f.write_text('a.o: '+escape(canonical)+' \\\n '+escape(header)+'\n')
            self.assertEqual(self.build.dependencies(f,overlay),({canonical},{header}))


if __name__=='__main__':unittest.main()
