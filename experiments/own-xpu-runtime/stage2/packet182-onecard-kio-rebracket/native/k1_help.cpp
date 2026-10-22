#include <iostream>
#include <string>
#include <unistd.h>
int main(int argc,char**argv){if(argc==2&&std::string(argv[1])=="--help"){std::cout<<"--output --down-layout --card --iterations --authorized-device-window --stop-fd\n";return 0;}execv("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet182-onecard-kio-rebracket/build/device/p58-cache-fixtures-core",argv);return 127;}
