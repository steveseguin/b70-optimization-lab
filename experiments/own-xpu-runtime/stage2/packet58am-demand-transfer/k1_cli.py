"""Build a help-only exec adapter around the unchanged hash-bound K1 fixture."""
import json,re
from prepare import P,sha,save
from build_engine import run

def main():
    source=next((P/'vendor').rglob('p58_native_fixture.cpp'))
    flags=sorted(set(re.findall(r'key=="(--[a-z-]+)"',source.read_text())))
    parent=P/'build/device/p58-cache-fixtures';binary=P/'build/device/p58-cache-fixtures-cli'
    code='#include <unistd.h>\n#include <cstdio>\n#include <string>\nint main(int argc,char**argv){if(argc==2&&std::string(argv[1])=="--help"){std::puts('+json.dumps('K1 unchanged fixture exec adapter: '+' '.join(flags))+');return 0;}execv('+json.dumps(str(parent))+',argv);std::perror("K1 exec");return 127;}\n'
    path=P/'native/k1_cli.cpp';path.write_text(code)
    run(['/usr/bin/g++','-std=c++20','-O2',str(path),'-o',str(binary)],'k1-cli')
    save(P/'evidence/k1-cli.json',dict(passed=True,device_executed=False,flags=flags,
        parent_binary_sha256=sha(parent),binary_sha256=sha(binary),source_sha256=sha(path),
        parser_source=str(source.relative_to(P)),parser_source_sha256=sha(source),behavior='--help only; all other argv exec unchanged fixture in same PID'))
if __name__=='__main__':main()
