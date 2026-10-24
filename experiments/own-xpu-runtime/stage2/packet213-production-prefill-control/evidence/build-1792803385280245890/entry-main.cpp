#define main p213_model_body
#include "main.cpp"
#undef main
extern "C" int p213_future_entry(int argc,char**argv){return p213_model_body(argc,argv);}
int main(int,char**){std::cerr<<"P213 compile-only: all executable invocations disabled; native qualification pending\n";return 64;}
