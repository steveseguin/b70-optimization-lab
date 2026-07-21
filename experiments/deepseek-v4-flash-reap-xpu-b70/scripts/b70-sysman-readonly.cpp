// Read-only Level Zero Sysman probe for B70 ECC and frequency domains.
// It deliberately contains no setters.

#include <level_zero/ze_api.h>
#include <level_zero/zes_api.h>

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <vector>

static const char *result_name(ze_result_t r) {
  switch (r) {
    case ZE_RESULT_SUCCESS: return "SUCCESS";
    case ZE_RESULT_ERROR_UNSUPPORTED_FEATURE: return "UNSUPPORTED_FEATURE";
    case ZE_RESULT_ERROR_NOT_AVAILABLE: return "NOT_AVAILABLE";
    case ZE_RESULT_ERROR_INSUFFICIENT_PERMISSIONS: return "INSUFFICIENT_PERMISSIONS";
    case ZE_RESULT_ERROR_UNINITIALIZED: return "UNINITIALIZED";
    case ZE_RESULT_ERROR_DEPENDENCY_UNAVAILABLE: return "DEPENDENCY_UNAVAILABLE";
    default: return "OTHER_ERROR";
  }
}

static const char *domain_name(zes_freq_domain_t d) {
  switch (d) {
    case ZES_FREQ_DOMAIN_GPU: return "gpu";
    case ZES_FREQ_DOMAIN_MEMORY: return "memory";
    case ZES_FREQ_DOMAIN_MEDIA: return "media";
    default: return "unknown";
  }
}

int main() {
  setenv("ZES_ENABLE_SYSMAN", "1", 1);
  ze_result_t r = zesInit(0);
  if (r != ZE_RESULT_SUCCESS) {
    std::cerr << "zeInit=" << result_name(r) << " (" << std::hex << r << ")\n";
    return 2;
  }
  uint32_t driver_count = 0;
  zesDriverGet(&driver_count, nullptr);
  std::vector<zes_driver_handle_t> drivers(driver_count);
  zesDriverGet(&driver_count, drivers.data());
  unsigned ordinal = 0;
  for (auto driver : drivers) {
    uint32_t device_count = 0;
    zesDeviceGet(driver, &device_count, nullptr);
    std::vector<zes_device_handle_t> devices(device_count);
    zesDeviceGet(driver, &device_count, devices.data());
    for (auto device : devices) {
      zes_device_properties_t dp{ZES_STRUCTURE_TYPE_DEVICE_PROPERTIES};
      zesDeviceGetProperties(device, &dp);
      auto sys = device;
      ze_bool_t available = false, configurable = false;
      const ze_result_t ar = zesDeviceEccAvailable(sys, &available);
      const ze_result_t cr = zesDeviceEccConfigurable(sys, &configurable);
      zes_device_ecc_properties_t ep{ZES_STRUCTURE_TYPE_DEVICE_ECC_PROPERTIES};
      const ze_result_t er = zesDeviceGetEccState(sys, &ep);
      std::cout << "device=" << ordinal++ << " name=\"" << dp.core.name << "\""
                << " ecc_available_result=" << result_name(ar)
                << " ecc_available=" << static_cast<unsigned>(available)
                << " ecc_configurable_result=" << result_name(cr)
                << " ecc_configurable=" << static_cast<unsigned>(configurable)
                << " ecc_state_result=" << result_name(er);
      if (er == ZE_RESULT_SUCCESS)
        std::cout << " ecc_current=" << ep.currentState
                  << " ecc_pending=" << ep.pendingState
                  << " ecc_action=" << ep.pendingAction;
      std::cout << '\n';

      uint32_t count = 0;
      r = zesDeviceEnumFrequencyDomains(sys, &count, nullptr);
      std::cout << "  frequency_enum_result=" << result_name(r)
                << " count=" << count << '\n';
      if (r != ZE_RESULT_SUCCESS) continue;
      std::vector<zes_freq_handle_t> handles(count);
      zesDeviceEnumFrequencyDomains(sys, &count, handles.data());
      for (auto h : handles) {
        zes_freq_properties_t p{ZES_STRUCTURE_TYPE_FREQ_PROPERTIES};
        zes_freq_state_t s{ZES_STRUCTURE_TYPE_FREQ_STATE};
        const ze_result_t pr = zesFrequencyGetProperties(h, &p);
        const ze_result_t sr = zesFrequencyGetState(h, &s);
        std::cout << std::fixed << std::setprecision(1)
                  << "  domain=" << (pr == ZE_RESULT_SUCCESS ? domain_name(p.type) : "unknown")
                  << " properties_result=" << result_name(pr)
                  << " state_result=" << result_name(sr);
        if (pr == ZE_RESULT_SUCCESS)
          std::cout << " min_MHz=" << p.min << " max_MHz=" << p.max
                    << " controllable=" << static_cast<unsigned>(p.canControl);
        if (sr == ZE_RESULT_SUCCESS)
          std::cout << " request_MHz=" << s.request << " tdp_MHz=" << s.tdp
                    << " actual_MHz=" << s.actual
                    << " throttle_reasons=0x" << std::hex << s.throttleReasons << std::dec;
        std::cout << '\n';
      }
    }
  }
  return 0;
}
