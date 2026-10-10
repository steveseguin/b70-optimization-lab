"""CPU-only checks that changed tensor identities cannot silently reconcile."""
import copy
import unittest
from admit import differences


class Reconciliation(unittest.TestCase):
    def setUp(self):
        self.t = dict(name='bank',type='IQ2_S',type_id=22,dimensions=[256,512],
                      shape=[512,256],data_offset=0,file_offsets=[32,42016],bytes=41984,
                      shard='UD-IQ3_XXS/shard.gguf')

    def test_each_identity_field_rejects_mutation(self):
        for field in self.t:
            t = copy.deepcopy(self.t)
            if isinstance(t[field],str): t[field]+='changed'
            elif isinstance(t[field],list): t[field][0]+=1
            else: t[field]+=1
            with self.subTest(field=field):
                self.assertTrue(differences([t],[self.t]))

    def test_missing_and_unexpected_tensors(self):
        self.assertTrue(differences([],[self.t]))
        self.assertTrue(differences([self.t],[]))

    def test_order_is_not_identity(self):
        other = dict(self.t,name='other')
        self.assertEqual(differences([self.t,other],[other,self.t]),[])


if __name__=='__main__': unittest.main(verbosity=2)
