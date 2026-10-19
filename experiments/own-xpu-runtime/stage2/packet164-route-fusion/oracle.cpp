// Separate translation unit, real runtime arguments, no LTO or specialization.
#include "p109_route.hpp"
extern "C" void p164_original(route42::Args a) { p109route::host(a); }
