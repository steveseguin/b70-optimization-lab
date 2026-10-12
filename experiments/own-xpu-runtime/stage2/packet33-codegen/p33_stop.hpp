#pragma once
#include <csignal>
#include <stdexcept>
namespace p33 {
inline volatile std::sig_atomic_t stop_requested=0;
inline void stop_handler(int){stop_requested=1;}
inline void install_stop(){std::signal(SIGTERM,stop_handler);std::signal(SIGINT,stop_handler);}
inline void check_stop(){if(stop_requested)throw std::runtime_error("cooperative stop requested; no next launch");}
}
