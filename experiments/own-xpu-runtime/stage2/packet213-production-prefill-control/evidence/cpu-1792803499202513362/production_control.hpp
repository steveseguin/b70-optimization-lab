#pragma once
#include "../packet212-production-prefill-integration/production_schedule.hpp"
namespace p213 {
using p212::need;using p212::Site;using p212::Tensor;using p212::Layer;using p212::Schedule;
using p212::StepKind;using p212::Step;using p212::build_schedule;using p212::route_offset;
using p212::chronological_routes;using p212::admit_chunk;
enum class Mode {serial_frozen2,paired_frozen2};
inline const char* mode_name(Mode mode){switch(mode){case Mode::serial_frozen2:return "serial-frozen2";case Mode::paired_frozen2:return "paired-frozen2";}throw std::invalid_argument("p213 invalid mode");}
inline std::vector<Step> ordered_steps(const Schedule& schedule,Mode mode){
 if(mode==Mode::paired_frozen2)return p212::ordered_steps(schedule);
 need(mode==Mode::serial_frozen2,"p213 explicit serial/paired mode");
 std::vector<Step> result;for(unsigned row=0;row<2;++row){for(auto index:schedule.prefix)result.push_back({StepKind::site,index,row});for(const auto&layer:schedule.layers)for(auto index:layer.sites)result.push_back({StepKind::site,index,row});}return result;
}
} // namespace p213
