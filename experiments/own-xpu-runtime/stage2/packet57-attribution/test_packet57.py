import json,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent
class Packet57(unittest.TestCase):
 def test_plan_never_launches(self):
  import p57_window
  with patch.object(subprocess,'run',side_effect=AssertionError('plan launched')),patch.object(subprocess,'Popen',side_effect=AssertionError('plan launched')):
   row=p57_window.plan(Path('/tmp/not-created-p57'))
  self.assertFalse(row['device_executed']);self.assertFalse(row['qualifying'])
  self.assertEqual([x['name'] for x in row['stages']],['K0','KD','W57-control','W57-attribution'])
  self.assertTrue(all(x['expected_work_seconds']+17<=x['watchdog_seconds']/4 for x in row['stages']))
 def test_parent_identity(self):
  from p57_seal import parent_proof
  base,proof=parent_proof();self.assertTrue(base['passed']);self.assertEqual(len(proof['windows']),8)
 def test_native_controller_exact(self):
  parent=P.parent/'packet56-draft-prefix'
  for name in ('native_controller.hpp','owner.cpp','single_device.cpp','p56_prefix.hpp','mtp_kernels.cpp','p49d_submit.cpp'):
   self.assertEqual((P/name).read_bytes(),(parent/name).read_bytes(),name)
 def test_recording_guard_and_categories(self):
  # Lightweight header-only CPU check, no SYCL import or device executable.
  source=P/'build/p57-recorder-test.cpp';binary=P/'build/p57-recorder-test'
  source.write_text('''#include "attribution.hpp"
#include <cassert>
int main(){
 using namespace p57;
 assert(!sample(8)&&sample(9)&&sample(16)&&!sample(17));
 for(auto label:{"draft.blk.0.expsgate","draft.blk.0.gather","draft.blk.0.moe"})assert(category(label)=="moe_experts");
 assert(category("draft.blk.0.attention")=="attention");
 assert(category("draft.blk.0.shexpdown")=="shared_expert");
 assert(category("draft.argmax")=="argmax");assert(category("draft.logits")=="head_prefix");
 assert(category("draft.transfer.proposal")=="transfers");
 assert(selected("blk.19.attention")&&selected("blk.22.gdn")&&selected("blk.23.attention")&&selected("blk.24.gdn"));
 assert(!selected("blk.21.gdn"));
 Recorder r;r.enabled=true;r.current={"draft.argmax",9,105,false};r.record(1);assert(r.events.at(1).fixture==9);
 r.current.fixture=17;r.record(2);assert(r.events.size()==1);
 r.enabled=false;r.current.fixture=9;r.record(3);assert(r.events.size()==1);
}
''')
  subprocess.run(['/usr/bin/g++','-std=c++20','-O0','-I',str(P),str(source),'-o',str(binary)],check=True,capture_output=True)
  subprocess.run([str(binary)],check=True,capture_output=True)
 def test_observation_sites_present(self):
  main=(P/'main.cpp').read_text();rank=(P/'rank.hpp').read_text();draft=(P/'mtp.hpp').read_text()
  self.assertIn('profile_events||attribution.enabled||a.mtp',main)
  self.assertIn('request.position-request.fixture',rank)
  self.assertIn('r.position-engine->attribution.generation_origin',rank)
  self.assertNotIn('"draft.transfer.begin",r.fixture',rank)
  for label in ('draft.transfer.hidden','draft.transfer.status','draft.transfer.proposal','transfer.half_token','transfer.half_streams'):self.assertIn(label,draft)
  poll=draft[draft.index('std::optional<Completion> poll_result()'):draft.index('void queue_half_inputs')]
  self.assertNotIn('attribution_row',poll);self.assertNotIn('.timing(',poll)
if __name__=='__main__':unittest.main()
