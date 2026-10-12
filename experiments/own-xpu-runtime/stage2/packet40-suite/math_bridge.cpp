#include "detmath.hpp"
extern "C" float v2_exp(float x){return detmath::exp(x);}
extern "C" float v2_log(float x){return detmath::log(x);}
extern "C" float v2_sqrt(float x){return detmath::sqrt(x);}
