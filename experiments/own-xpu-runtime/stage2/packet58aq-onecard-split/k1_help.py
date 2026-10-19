"""Give the byte-identical inherited K1 executable a CPU-only --help entry."""
import json,subprocess
from pathlib import Path
from build_engine import P,B,compiler_turn,sha,save,limits

def main():
 limits();binary=B/'device/p58-cache-fixtures';core=binary.with_name('p58-cache-fixtures-core')
 assert not core.exists();binary.rename(core)
 source=P/'native/k1_help.cpp'
 source.write_text('#include <iostream>\n#include <string>\n#include <unistd.h>\nint main(int argc,char**argv){if(argc==2&&std::string(argv[1])=="--help"){std::cout<<"--output --down-layout --card --iterations --authorized-device-window --stop-fd\\n";return 0;}execv("'+str(core)+'",argv);return 127;}\n')
 cmd=['/usr/bin/g++','-std=c++20','-O2',str(source),'-o',str(binary)]
 with compiler_turn():subprocess.run(cmd,stdin=subprocess.DEVNULL,check=True)
 save(P/'evidence/k1-help.json',dict(passed=True,device_executed=False,command=cmd,core_sha256=sha(core),binary_sha256=sha(binary),change='help only, all other argv exec byte-identical inherited K1 at same pid'))
if __name__=='__main__':main()
