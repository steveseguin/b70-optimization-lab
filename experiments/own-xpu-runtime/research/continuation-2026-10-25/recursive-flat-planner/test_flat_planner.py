import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import test_persistent_rolling as prior
spec=importlib.util.spec_from_file_location('flat_candidate',Path(__file__).with_name('persistent_rolling_driver.py'))
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
FLAG='--pipeline-ring-recursive-flat-copy'
class FlatPlannerTests(unittest.TestCase):
 def test_default_and_explicit_boolean_only_first_owner_two_four_six(self):
  for count in (2,4,6):
   for enabled in (None,False,True):
    with self.subTest(count=count,enabled=enabled),tempfile.TemporaryDirectory() as tmp:
     path,config,inputs,original=prior.PersistentPlanTests().fixture(Path(tmp),'measured',512)
     if enabled is not None:config['recursive_flat_copy']=enabled
     path.write_text(json.dumps(config))
     def baseline(p):
      value=original(p);template=value['stages'][0]
      value['stages']=[dict(copy.deepcopy(template),id=i,first=i==0,final=i==count-1) for i in range(count)]
      return value
     with patch.object(driver.base,'make_plan',side_effect=baseline):plan=driver.make_plan(path)
     self.assertEqual([s['argv'].count(FLAG) for s in plan['stages']],[int(enabled is True)]+[0]*(count-1))
     self.assertEqual(plan.get('recursive_flat_copy',False),enabled is True)
 def test_wrong_types_fail_before_base_plan(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,config,inputs,baseline=prior.PersistentPlanTests().fixture(Path(tmp))
   for value in (1,0,'true',None,[]):
    config['recursive_flat_copy']=value;path.write_text(json.dumps(config))
    with self.subTest(value=value),patch.object(driver.base,'make_plan') as base,self.assertRaisesRegex(ValueError,'boolean'):
     driver.make_plan(path)
    base.assert_not_called()
 def test_inherited_template_flag_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   path,config,inputs,original=prior.PersistentPlanTests().fixture(Path(tmp))
   config['recursive_flat_copy']=True;path.write_text(json.dumps(config))
   def baseline(p):
    value=original(p)
    for s in value['stages']:s['argv'].append(FLAG)
    return value
   with patch.object(driver.base,'make_plan',side_effect=baseline),self.assertRaisesRegex(ValueError,'inherited adapter'):
    driver.make_plan(path)
if __name__=='__main__':unittest.main()
