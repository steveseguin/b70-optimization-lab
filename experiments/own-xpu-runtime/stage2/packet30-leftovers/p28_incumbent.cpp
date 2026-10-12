#include "../packet28-dense/submit.hpp"
namespace p30 { integrated::Launch dense_incumbent(ownrt::Device& d,const integrated::Matrix& m,unsigned v){return p28::submit(d,{m},"p28.dense.wg32",false,v);} }
