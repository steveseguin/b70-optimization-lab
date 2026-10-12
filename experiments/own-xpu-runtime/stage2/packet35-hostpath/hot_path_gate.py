"""Static companion to malloc-hook measurements; native compilation only."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
def body(path,start,end):return (P/path).read_text().split(start,1)[1].split(end,1)[0]
def main():
 owner=body('owner.cpp','Event Device::issue(', 'bool Device::drain(')
 issue=body('main.cpp','flash::Event issue_site(', 'flash::Event enqueue(')
 finish=body('main.cpp','void finish(int, Launch l, bool gemv)', 'void drain()')
 native=body('prepared_submission.hpp','make_callback(NativeIssueState state)const override', 'template<class F> sycl::event prepared_submit')
 forbidden=('arena.row(','.find(','.equal_range(','.starts_with(','.substr(','std::stoi(','get_info<','new ','malloc(','make_shared','make_unique','a.timing')
 rows=[]
 for label,text in [('owner',owner),('engine',issue),('finish',finish),('native_callback',native)]:
  for token in forbidden:assert token not in text,(label,token)
  rows.append(dict(path=label,forbidden_calls_absent=True))
 assert 'class_timing?std::chrono::steady_clock::now()' in issue
 assert 'if(class_timing)family_ms' in issue
 assert 'if(profile_events)pending.push_back' in finish
 assert 'if(a.mini||a.checked)site_timings' in issue
 assert 'state.events->size()>=state.events->capacity()' in native
 assert 'queue->submit(command)' in native or 'q->submit(command)' in native
 assert 'bound->issue' not in (P/'backend.hpp').read_text()
 result=dict(passed=True,device_executed=False,checks=rows,scope='Closed success-path source guard; diagnostic branches permitted only under cached class/checked/mini booleans. SYCL internal allocations are not claimed absent.',sources={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('main.cpp','owner.cpp','owner_api.hpp','prepared_submission.hpp','backend.hpp')})
 (P/'hot-path-gates.json').write_text(json.dumps(result,indent=2)+'\n');print('four prepared success paths contain no prohibited lookup/allocation/string/query calls')
if __name__=='__main__':main()
