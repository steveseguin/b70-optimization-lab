#!/usr/bin/env python3
"""Static admission check: changing the fenced submission sites requires review."""
from pathlib import Path
import hashlib
HERE=Path(__file__).resolve().parent
def check():
    owner=(HERE/'owner.cpp').read_text();main=(HERE/'main.cpp').read_text()
    backend=(HERE/'backend.hpp').read_text();retire=(HERE/'owner_retire.cpp').read_text()
    requirements = [
      ('owner compute dependency assertion', 'assert_local_dependencies(chain,bound->queue);' in owner and 'assert_local_dependencies(chain,queue);' in owner),
      ('owner queue rejection', 'event_card(e)!=queue' in owner),
      ('peer requires drained queues', 'dq!=sq&&owner_.in_flight()' in owner),
      ('shutdown marker has no dependencies', 'backend_->marker({})' in owner and 'backend_->marker(events_)' not in owner),
      ('every native entry checks target queue', backend.count('dependencies(deps,') == 3 and 'foreign-queue native dependency rejected' in backend),
      ('native in-order dependency validation', 'tracked(e).card!=target' in backend and 'static const std::vector<sycl::event> empty' in backend),
      ('native token mode queue omits profiling', 'bool profile=true' in backend and 'profiling?sycl::property_list' in backend),
      ('binding release invalidates pointer cache', 'fast_owners.at(&owner_).bindings.clear();' in owner),
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
