#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet58g-onecard/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet178-onecard-portable/one-card/native-portable/experiments/own-xpu-runtime/stage2/packet58g-onecard/adapter_fixture.hpp"
#pragma once
#include <filesystem>
#include <string>
#include <cstdint>
struct AdapterFixtureReceipt {unsigned checks;uint64_t max_submission_ns;std::string teardown;};
AdapterFixtureReceipt adapter_fixture_gate(unsigned,const std::filesystem::path&);
AdapterFixtureReceipt adapter_timing_gate(unsigned,const std::filesystem::path&);
AdapterFixtureReceipt gemv_timing_gate(unsigned,const std::filesystem::path&);
AdapterFixtureReceipt gemv_fixture_gate(unsigned,const std::filesystem::path&);

AdapterFixtureReceipt p39_fixture_gate(unsigned,const std::filesystem::path&,bool);
