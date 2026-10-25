import copy
from pathlib import Path
import tempfile
import unittest

from finalize_portable_live_proof import identity, verify_authority


class AuthorityTests(unittest.TestCase):
    def test_profile_binding_and_tensor_identity_are_separate_authorities(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,data in [('profile.json','profile'),('binding.json','binding'),('shard-auth.tsv','target'),
                              ('draft-manifest.tsv','draft'),('include/bound.hpp','header')]:
                path=root/name;path.parent.mkdir(exist_ok=True);path.write_text(data)
            hashes={name:identity(root/name)['sha256'] for name in ['profile.json','binding.json','shard-auth.tsv','draft-manifest.tsv','include/bound.hpp']}
            profile,binding=hashes['profile.json'],hashes['binding.json']
            binary='f'*64
            config=dict(deployment=str(root),profile_sha256=profile,binding_sha256=binding)
            plan=dict(model_profile_sha256=profile,deployment_binding_sha256=binding,
                stages=[dict(argv=['--identity',str(root/'shard-auth.tsv'),'--draft-manifest',str(root/'draft-manifest.tsv')])],
                pins={str(root/name):sha for name,sha in hashes.items()})
            plan['pins']['native-binary']=binary
            receipt=dict(binary='native-binary',binary_sha256=binary,
                generated_authority=dict(profile_sha256=profile,binding_sha256=binding,include=str(root/'include'),
                    header='bound.hpp',header_sha256=hashes['include/bound.hpp'],artifacts=hashes),
                generated_dependencies={str(root/'include/bound.hpp'):hashes['include/bound.hpp']})
            target=dict(input_identity=dict(model_sha256=hashes['shard-auth.tsv']))
            draft=dict(input_identity=dict(draft_model_sha256=hashes['draft-manifest.tsv']))
            verify_authority(plan,config,receipt,target,draft)
            wrong=copy.deepcopy(target);wrong['input_identity']['model_sha256']=profile
            with self.assertRaisesRegex(ValueError,'target tensor authority'):
                verify_authority(plan,config,receipt,wrong,draft)
            wrong_receipt=copy.deepcopy(receipt)
            wrong_receipt['generated_dependencies'][str(root/'include/bound.hpp')]='0'*64
            with self.assertRaisesRegex(ValueError,'header authority'):
                verify_authority(plan,config,wrong_receipt,target,draft)
            (root/'draft-manifest.tsv').write_text('changed')
            with self.assertRaisesRegex(ValueError,'draft tensor authority'):
                verify_authority(plan,config,receipt,target,draft)


if __name__=='__main__':unittest.main()
