#pragma once
#include <filesystem>
#include <string>
#include <cstdint>
struct AdapterFixtureReceipt {unsigned checks;uint64_t max_submission_ns;std::string teardown;};
AdapterFixtureReceipt adapter_fixture_gate(unsigned,const std::filesystem::path&);
AdapterFixtureReceipt adapter_timing_gate(unsigned,const std::filesystem::path&);
AdapterFixtureReceipt gemv_timing_gate(unsigned,const std::filesystem::path&);
AdapterFixtureReceipt gemv_fixture_gate(unsigned,const std::filesystem::path&);
