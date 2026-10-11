#pragma once
#include "depcheck.hpp"
#include <cstdio>
#include <iostream>
namespace depcheck {
// Called only by the generated CPU owner overlay's retained-owner path.
// Native owner/backend sources are not edited. No pending closure is run here.
[[noreturn]] inline void fatal_cpu_exit() {
 size_t canceled=0;for(const auto& [id,w]:checker.work)if(!w.done)++canceled;
 if(auto path=std::getenv("DEPCHECK_REPORT")){
  std::ofstream f(path);
  f<<"{\"device_executed\":false,\"exit_code\":2,\"fatal_owner_retention\":true,\"submissions\":"<<checker.submitted
   <<",\"executed\":"<<checker.executed<<",\"max_ready\":"<<checker.max_ready<<",\"canceled_submissions\":"<<canceled<<",\"violations\":[";
  for(size_t i=0;i<checker.violations.size();++i)f<<(i?",":"")<<ownrt::quote(checker.violations[i]);
  f<<"],\"canceled_events\":[";bool comma=false;
  for(const auto& [id,w]:checker.work)if(!w.done){f<<(comma?",":"")<<"{\"event\":"<<id<<",\"site\":"<<ownrt::quote(w.site)<<"}";comma=true;}
  f<<"]}\n";f.flush();
 }
 checker.trace.flush();
 std::fprintf(stderr,"CPU sanitizer retained-owner failure: canceled %zu pending submissions; exit 2.\n",canceled);
 std::cout.flush();std::cerr.flush();std::fflush(nullptr);
 std::_Exit(2);
}
}
