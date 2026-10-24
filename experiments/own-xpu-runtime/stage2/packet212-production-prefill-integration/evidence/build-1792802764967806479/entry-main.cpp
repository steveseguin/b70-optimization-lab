#define main p212_model_body
#include "main.cpp"
#undef main
extern "C" int p212_future_entry(int argc,char**argv){return p212_model_body(argc,argv);}
int main(int,char**){std::cerr<<"P212 compile-only: all executable invocations disabled; native qualification pending\n";return 64;}
