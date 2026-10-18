"""Static guard for the single-device rank ownership boundary."""
from pathlib import Path
import hashlib
P=Path(__file__).resolve().parent
def check():
 owner=(P/'owner.cpp').read_text();main=(P/'main.cpp').read_text();rank=(P/'rank.hpp').read_text();retire=(P/'owner_retire.cpp').read_text()
 requirements=[
 ('single-device backend', 'ownrt::make_sycl_device(a.card' in main and 'make_two_device' not in main),
 ('single-card CLI admission', 'a.cards==1' in main.replace(' ','')),
 ('split rejects peer plan', 'split requires flattened local plan' in rank),
 ('rank1 refuses speculation', 'rank1 must never speculate' in rank),
 ('owner local dependencies', 'assert_local_dependencies(chain,bound->queue);' in owner and 'assert_local_dependencies(chain,queue);' in owner),
 ('shutdown marker has no dependencies', 'backend_->marker({})' in owner and 'backend_->marker(events_)' not in owner),
 ('retirement order', retire.index('backend_->synchronize();') < retire.index('backend_->clear_events();') < retire.index('forget_event_queues(events_);')),
 ('readback after local drain', 'e.drain();int error=' in rank),
 ('shared stop channel', 'POLLIN|POLLHUP|POLLERR|POLLNVAL' in rank)]
 for name,ok in requirements:assert ok,name
 return dict(passed=True,checks=[n for n,_ in requirements],device_executed=False,
  sources={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ('main.cpp','rank.hpp','owner.cpp','owner_retire.cpp')})
if __name__=='__main__':
 import json
 print(json.dumps(check(),indent=2))
