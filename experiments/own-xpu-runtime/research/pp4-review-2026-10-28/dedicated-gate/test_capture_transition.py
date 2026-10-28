"""Source-delta rejection fixtures; no parity proof manufactured for inference."""
from copy import deepcopy
import unittest
from capture_transition import validate_build_delta

class TransitionTests(unittest.TestCase):
    def inputs(self):
        old=dict(binary='/old/sc117-engine',binary_sha256='old',sources={'owner':'a','math':'m'},
            runtime_assets={'rope':'hash'},generated_authority=None,generated_dependencies={},
            build_script_sha256='script',commands={'entry':{'cmd':['compiler','-ffp-contract=off','-o','/old/entry.o'],'rc':0}})
        new=deepcopy(old);new.update(binary='/new/sc117-engine',binary_sha256='new');new['sources']['owner']='b'
        new['commands']['entry']['cmd'][-1]='/new/entry.o'
        catalog=dict(old_binary_sha256='old',sources={'owner':dict(before='a',after='b')})
        return old,new,catalog
    def test_exact_changed_bytes_and_build_paths(self):validate_build_delta(*self.inputs())
    def test_observed_build_duration_and_diagnostics_not_argv(self):
        old,new,catalog=self.inputs()
        old['commands']['entry'].update(seconds=6.2,stderr='warning A\nwarning B')
        new['commands']['entry'].update(seconds=6.3,stderr='warning B\nwarning A')
        validate_build_delta(old,new,catalog)
    def test_failed_build_refused(self):
        old,new,catalog=self.inputs();new['commands']['entry']['rc']=1
        with self.assertRaisesRegex(ValueError,'successful compiler/link'):validate_build_delta(old,new,catalog)
    def test_unlisted_arithmetic_source_refused(self):
        old,new,catalog=self.inputs();new['sources']['math']='changed'
        with self.assertRaisesRegex(ValueError,'outside exact capture patch'):validate_build_delta(old,new,catalog)
    def test_wrong_allowed_source_bytes_refused(self):
        old,new,catalog=self.inputs();new['sources']['owner']='another'
        with self.assertRaisesRegex(ValueError,'source bytes differ'):validate_build_delta(old,new,catalog)
    def test_compiler_arithmetic_option_refused(self):
        old,new,catalog=self.inputs();new['commands']['entry']['cmd'][1]='-ffast-math'
        with self.assertRaisesRegex(ValueError,'compiler/link commands'):validate_build_delta(old,new,catalog)
    def test_runtime_asset_refused(self):
        old,new,catalog=self.inputs();new['runtime_assets']['rope']='different'
        with self.assertRaisesRegex(ValueError,'runtime/compiler authority'):validate_build_delta(old,new,catalog)
if __name__=='__main__':unittest.main()
