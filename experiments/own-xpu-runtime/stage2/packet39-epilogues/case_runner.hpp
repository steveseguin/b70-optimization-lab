#pragma once
#include <stdexcept>
namespace p39 {
struct ByteMismatch : std::runtime_error {using std::runtime_error::runtime_error;};
// Only known case failures continue. Allocation, transport, profiling, journal,
// stop and unknown failures are infrastructure errors and stop the window.
// Persist the failure before cleanup, including for infrastructure failures.
template<class Work,class Report,class Cleanup>
bool run_case(Work work,Report report,Cleanup cleanup){
 try {work();}
 catch(const std::invalid_argument& e){report("validation",e.what());cleanup();return false;}
 catch(const ByteMismatch& e){report("byte_mismatch",e.what());cleanup();return false;}
 catch(const std::exception& e){report("infrastructure",e.what());cleanup();throw;}
 cleanup();return true;
}
}
