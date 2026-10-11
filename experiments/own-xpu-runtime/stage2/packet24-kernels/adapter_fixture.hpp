#pragma once
#include <cstdint>
#include <filesystem>
#include <string>
struct AdapterFixtureReceipt { unsigned checks=0;uint64_t max_submission_ns=0;std::string teardown; };
AdapterFixtureReceipt adapter_fixture_gate(unsigned card,const std::filesystem::path& output);
