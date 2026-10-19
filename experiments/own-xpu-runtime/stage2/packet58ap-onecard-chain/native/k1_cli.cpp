#include <filesystem>
#include <string>
#include <vector>
#include <unistd.h>
#include <cstdio>
int main(int argc,char**argv){
 if(argc==2 && std::string(argv[1])=="--help"){std::puts("--authorized-device-window --card --down-layout --iterations --output --stop-fd --cpu-preparation-probe");return 0;}
 bool cpu=false;for(int i=1;i<argc;i++)if(std::string(argv[i])=="--cpu-preparation-probe")cpu=true;
 auto dir=std::filesystem::canonical("/proc/self/exe").parent_path();
 auto target=cpu?dir.parent_path()/"gnu-host/p58-cache-fixtures":dir/"p58-cache-fixtures-core";
 std::string path=target.string();std::vector<char*> args{path.data()};
 for(int i=1;i<argc;i++)if(std::string(argv[i])!="--cpu-preparation-probe" && !(cpu&&std::string(argv[i])=="--authorized-device-window"))args.push_back(argv[i]);
 args.push_back(nullptr);execv(path.c_str(),args.data());std::perror("K1 exec");return 127;
}
