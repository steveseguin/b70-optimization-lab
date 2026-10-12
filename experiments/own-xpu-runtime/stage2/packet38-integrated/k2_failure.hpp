#pragma once
#include "owner.hpp"
#include <fstream>
#include <filesystem>
#include <stdexcept>
namespace packet26 {
// Validation/equality failures exclude an arm. Execution/timeout failures still
// escape to safe teardown and the coordinator's fault handling.
inline void candidate_failure(const std::filesystem::path& out,const std::string& klass,
 const std::string& variant,const std::string& workload,const std::exception& e,const std::string& implementation=""){
 std::string why=e.what();
 if(!dynamic_cast<const std::invalid_argument*>(&e)&&why.find("mismatch")==std::string::npos&&why.find("exactness")==std::string::npos)throw;
 std::ofstream(out/"candidate-failures.jsonl",std::ios::app)
  <<"{\"class\":"<<ownrt::quote(klass)<<",\"variant\":"<<ownrt::quote(variant)
  <<",\"implementation\":"<<ownrt::quote(implementation.empty()?variant:implementation)<<",\"workload\":"<<ownrt::quote(workload)<<",\"error\":"<<ownrt::quote(why)<<"}\n";
}
}
