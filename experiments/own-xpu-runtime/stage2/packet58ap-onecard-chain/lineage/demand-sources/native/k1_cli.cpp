#include <unistd.h>
#include <cstdio>
#include <string>
int main(int argc,char**argv){if(argc==2&&std::string(argv[1])=="--help"){std::puts("K1 unchanged fixture exec adapter: --authorized-device-window --card --down-layout --iterations --output --stop-fd");return 0;}execv("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/build/device/p58-cache-fixtures",argv);std::perror("K1 exec");return 127;}
