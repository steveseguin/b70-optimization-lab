#pragma once
#include <csignal>
#include <stdexcept>
namespace p42 {
inline volatile std::sig_atomic_t stopping=0;
inline void stop(int){stopping=1;}
inline void install_stop(){std::signal(SIGTERM,stop);std::signal(SIGINT,stop);}
inline void check_stop(){if(stopping)throw std::runtime_error("cooperative stop; no next launch");}
}
