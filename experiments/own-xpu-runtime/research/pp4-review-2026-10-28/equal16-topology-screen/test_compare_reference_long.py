"""Bounded real-plan identity guards; no payload/archive/GPU reads."""
from copy import deepcopy
from pathlib import Path
import unittest
import compare_reference_long as M

class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.reg=M.read(M.HERE/'reference-policy-long512-registration.json')
  cls.plans=[M.read(c['plan'])for c in cls.reg['cases']]
  cls.configs,cls.identities=zip(*(M.request_identity(p)for p in cls.plans))
 def check(self,plans=None,configs=None,identities=None):
  return M.identity_guards(self.reg,plans or self.plans,configs or self.configs,identities or self.identities)
 def test_actual_registered_configs_requests_roles(self):
  self.assertEqual(set(self.check()),{'boundaries','output'})
 def test_changed_math_flag_or_other_actor_policy_refused(self):
  for role,key,value in (('provider','OWNRT_REFERENCE_ROUTE_TIE_SORT','0'),('provider','OWNRT_DRAFT_KERNELS','route'),('target','OWNRT_MERGE_CHECKS','0')):
   with self.subTest(role=role,key=key):
    p=deepcopy(self.plans);owner=p[1]['provider']if role=='provider'else p[1]['stages'][1];owner['environment'][key]=value
    with self.assertRaises(ValueError):self.check(plans=p)
 def test_undeclared_config_or_semantic_differences_refused(self):
  c=deepcopy(self.configs);c[1]['lookup_storage']='view'
  with self.assertRaisesRegex(ValueError,'config differences'):self.check(configs=c)
  i=deepcopy(self.identities);i[1]['draft_route_policy']='modified'
  with self.assertRaisesRegex(ValueError,'semantic request'):self.check(identities=i)
 def test_wrong_cut_argv_or_physical_role_refused(self):
  p=deepcopy(self.plans);argv=p[1]['stages'][0]['argv'];argv[argv.index('--pipeline-boundaries')+1]='0,17,33,48'
  with self.assertRaisesRegex(ValueError,'argv cuts'):self.check(plans=p)
  p=deepcopy(self.plans);p[1]['provider']['bdf']='0000:27:00.0'
  with self.assertRaisesRegex(ValueError,'physical owner'):self.check(plans=p)
 def test_changed_shared_source_pin_or_extra_plan_treatment_refused(self):
  p=deepcopy(self.plans);key=next(k for k in p[0]['pins']if k in p[1]['pins']);p[1]['pins'][key]='0'*64
  with self.assertRaisesRegex(ValueError,'common runtime'):self.check(plans=p)
  p=deepcopy(self.plans);p[1]['extra_optimization']=True
  with self.assertRaisesRegex(ValueError,'other plan treatment'):self.check(plans=p)
 def test_forged_request_digest_refused(self):
  p=deepcopy(self.plans[1]);p['request_sha256']='f'*64
  with self.assertRaisesRegex(ValueError,'policy-bound request'):M.request_identity(p)
if __name__=='__main__':unittest.main()
