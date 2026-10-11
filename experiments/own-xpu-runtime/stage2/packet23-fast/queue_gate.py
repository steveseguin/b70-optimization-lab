#!/usr/bin/env python3
"""Static admission check: changing the fenced submission sites requires review."""
from pathlib import Path
from kernel_overlay import apply
import hashlib
HERE=Path(__file__).resolve().parent
def check():
    owner=(HERE/'owner.cpp').read_text();main=(HERE/'main.cpp').read_text()
    backend=(HERE/'backend.hpp').read_text();retire=(HERE/'owner_retire.cpp').read_text()
    one=HERE.parents[1]/'stage1/packet3-prep/src/sycl_device.cpp'
    one=apply(one,one.read_text())
    requirements = [
      ('one-card event ID follows parameter planning/submission', 'auto submitted=native.submit(*queue_,bindings,wait);\n    auto id=next_handle();' in one),
      ('two-card event ID follows parameter planning/submission', 'auto submitted=op.submit(*queues[allocation_card],p,wait);\n    auto e=ownrt::next_handle();' in backend),
      ("cached native dependencies released before context", "void clear_events() override {dependency_storage.clear();events.clear();event_cards.clear();}" in backend),
      ('owner compute dependency assertion', 'assert_local_dependencies(chain,queue);' in owner and owner.count('assert_local_dependencies(chain,queue);') == 2),
      ('owner queue rejection', 'event_queue.at(e)!=queue' in owner),
      ('peer requires drained queues', 'dq!=sq&&owner_.in_flight()' in owner),
      ('shutdown marker has no dependencies', 'backend_->marker({})' in owner and 'backend_->marker(events_)' not in owner),
      ('every native entry checks target queue', backend.count('dependencies(deps,') == 3 and 'foreign-queue native dependency rejected' in backend),
      ('native same-queue event filter', 'event_cards.at(e)==target' in backend),
      ('queue switches fence', 'if(submission_card!=c)drain();' in main),
      ('all peer copies fence', 'for (auto &name : l.outputs) {\n        drain(); // every peer copy' in main),
      ('final Q1 commit before Q0 readback fences', 'e->drain(); // commit.final is Q1; readback is Q0' in main),
      ('retirement drains queues before deleting IDs', retire.index('backend_->synchronize();') < retire.index('backend_->clear_events();') < retire.index('forget_event_queues(events_);')),
    ]
    for name, passed in requirements:
        if not passed: raise RuntimeError('queue isolation static check: '+name)
    return dict(passed=True, checks=[name for name,_ in requirements],
                sources={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                         for name in ('main.cpp','owner.cpp','backend.hpp','owner_retire.cpp')},
                limit='Source structure guard plus owner runtime assertion; no native execution proof')
if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
