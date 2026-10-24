import copy
import json
import unittest
from unittest.mock import patch
import contract as K


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        b=json.loads((K.P/'target-bindings.json').read_text())
        cls.old=json.loads((K.ROOT/b['old']).read_text())
        cls.new=json.loads((K.ROOT/b['new']).read_text())

    def test_bound_real_census_contract(self):
        r=K.bound_contract()
        self.assertTrue(r['metadata_compatible'])
        self.assertFalse(r['native_admitted'])
        self.assertEqual(r['hidden_bytes_bf16'],20480)
        self.assertFalse(r['embedding_payload_equality_claimed'])

    def test_geometry_and_tokenizer_refusals(self):
        for key in ('qwen4exp.embedding_length','qwen4exp.hyper_connection.count',
                    'qwen4exp.block_count','tokenizer.ggml.tokens',
                    'tokenizer.ggml.merges','tokenizer.chat_template',
                    'tokenizer.ggml.eos_token_id'):
            x=copy.deepcopy(self.new)
            x['metadata'][key]['canonical_json_sha256']='0'*64
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,'mismatch'):
                K.validate_contract(self.old,x)

    def test_missing_tokenizer_key(self):
        x=copy.deepcopy(self.new)
        del x['metadata']['tokenizer.ggml.tokens']
        with self.assertRaisesRegex(ValueError,'key set'):
            K.validate_contract(self.old,x)

    def test_shared_head_embedding_shape_refusal(self):
        for name in ('output.weight','token_embd.weight'):
            for key,value in [('shape',[2560,248320]),('payload_extent_validated',False),
                              ('dimensions',[248320,2560])]:
                x=copy.deepcopy(self.new);x['tensors'][name][key]=value
                with self.subTest(name=name,key=key),self.assertRaises(ValueError):
                    K.validate_contract(self.old,x)

    def test_format_not_silently_changed(self):
        x=copy.deepcopy(self.new);x['tensors']['token_embd.weight']['type']='BF16'
        with self.assertRaisesRegex(ValueError,'embedding format'):
            K.validate_contract(self.old,x)

    def test_both_changed_geometry_not_admitted(self):
        a,b=copy.deepcopy(self.old),copy.deepcopy(self.new)
        for c in (a,b):c['metadata']['qwen4exp.embedding_length']['value']=1280
        with self.assertRaisesRegex(ValueError,'fixed draft geometry'):
            K.validate_contract(a,b)

    def test_pinned_artifact_change_refuses(self):
        with patch.object(K,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'binding changed'):
                K.bound_contract()

    def test_real_draft_metadata_and_exact_manifest_copy(self):
        r=K.draft_inventory()
        self.assertEqual((r['tensor_count'],r['file_count'],r['tensor_bytes']),
                         (3101,28,2698026496))
        self.assertFalse(r['payload_hashes_recomputed'])
        self.assertEqual(r['tensor_payload_bytes_read'],0)
        audit=json.loads((K.P/'source-audit.json').read_text())
        self.assertEqual((K.P/'draft-manifest.tsv').read_bytes(),
                         (K.ROOT/audit['draft_manifest']).read_bytes())

    def test_changed_draft_manifest_refused(self):
        with patch.object(K,'sha',return_value='0'*64):
            with self.assertRaisesRegex(ValueError,'manifest changed'):
                K.draft_inventory()


if __name__=='__main__':
    unittest.main()
