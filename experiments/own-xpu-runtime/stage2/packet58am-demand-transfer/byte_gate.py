"""Real-shape original-slot partition proof, two fresh runs per compiler."""
import json,resource,subprocess,tempfile
from pathlib import Path
from prepare import P,sha,save
from generate import N,V,C,include,once
from build_engine import run,compiler_turn,limits

def fixture():
    t=(V/'native/ports_bytes.cpp').read_text()
    t=t.replace('#include "fixture.cpp"',include(V/'build/native/fixture.cpp').strip())
    t=t.replace('#include "p100_down.hpp"',include(C/'p100_down.hpp')+include(N/'p100_down.hpp'))
    t=t.replace('#include "p109_fusion.hpp"',include(V/'build/native/p109_fusion.hpp').strip())
    t=t.replace('for(unsigned scenario=0;scenario<4;++scenario)', 'const unsigned masks[]={0,1023,1,2,4,8,16,32,64,128,256,512,341,682,1023};\n for(unsigned scenario=0;scenario<5;++scenario)')
    t=t.replace('for(unsigned profile=0;profile<6;++profile)', 'for(unsigned profile=0;profile<=std::size(masks);++profile)')
    t=t.replace('if(profile==1||profile==5)p73hc::host(hc.bound());else p60::host_gate_mix(hc.bound());','p73hc::host(hc.bound());')
    t=t.replace('if(profile==4||profile==5){','if(true){')
    t=t.replace('std::array<void*,20> p{};', '''if(scenario==4)routes[3].expert_id=512;
   p58am::Map descriptor{},stages{};std::vector<uint8_t> staged(10*p58am::expert_bytes);
   for(unsigned slot=0;slot<10;++slot){descriptor.slots[slot].resident=profile?!(masks[profile-1]&(1u<<slot)):true;
    if(profile&&profile!=std::size(masks)&&!descriptor.slots[slot].resident&&routes[slot].expert_id<512){auto id=routes[slot].expert_id;auto* base=staged.data()+slot*p58am::expert_bytes;
     std::memcpy(base,reinterpret_cast<void*>(gp[id].address),p58am::gate_bytes);std::memcpy(base+p58am::gate_bytes,reinterpret_cast<void*>(uptr[id].address),p58am::up_bytes);std::memcpy(base+p58am::gate_bytes+p58am::up_bytes,reinterpret_cast<void*>(dp[id].address),p58am::down_bytes);
     stages.slots[slot].gate=uint64_t(base);stages.slots[slot].up=uint64_t(base+p58am::gate_bytes);stages.slots[slot].down=uint64_t(base+p58am::gate_bytes+p58am::up_bytes);
    }
   }
   std::array<void*,22> p{};p[20]=&descriptor;p[21]=&stages;''')
    t=t.replace('std::array<void*,22> p{};', 'std::fill(y.begin(),y.end(),0x5a5a);std::fill(z.begin(),z.end(),0x5a5a);std::fill(d.begin(),d.end(),0x5a5a);std::fill(status.begin(),status.end(),0x5a5a5a5a);std::fill(peer_status.begin(),peer_status.end(),0x5a5a5a5a);\n   std::array<void*,22> p{};')
    start=t.index('   if(profile==2){');end=t.index('   for(unsigned i=0;i<act.size();',start)
    t=t[:start]+'''   {p58ag_exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> op;op.indirect=true;
    if(!profile)op.run(p);else {op.partition=1;op.run(p);
     for(unsigned slot=0;slot<10;++slot)if(!descriptor.slots[slot].resident){check(status[slot]==0x5a5a5a5a&&peer_status[slot]==0x5a5a5a5a,"untouched gate status");for(unsigned row=0;row<640;++row)check(y[slot*640+row]==0x5a5a&&z[slot*640+row]==0x5a5a,"untouched gate output");}
     op.partition=2;op.run(p);}}
'''+t[end:]
    t=t.replace('p100::Kernel<2> downop;downop.indirect=true;downop.run(std::span<void*const>(p.data(),19));', '''p58am_down::Kernel<2> downop;downop.indirect=true;
   if(!profile)downop.run(p);else{downop.partition=1;downop.run(p);for(unsigned slot=0;slot<10;++slot)if(!descriptor.slots[slot].resident)for(unsigned row=0;row<2560;++row)check(d[slot*2560+row]==0x5a5a,"untouched down output");downop.partition=2;downop.run(p);}''')
    t=t.replace('\\"profiles\\":6','\\"profiles\\":16,\\"sentinel_untouched_slots\\":true,\\"partition_masks\\":15,\\"scenarios\\":5')
    (N/'demand_bytes.cpp').write_text(t)

def main():
    limits();fixture();records=[]
    for tag,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        flags=['-O3','-march=native'] if tag=='GNU' else ['-O2','-fdenormal-fp-math=ieee']
        common=[cxx,'-std=c++20',*flags,'-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-ffunction-sections','-fdata-sections','-I'+str(N),'-I'+str(V/'build/native'),'-I'+str(C)]
        ref=P/'build'/f'{tag}-reference.o';binary=P/'build'/f'{tag}-demand-bytes'
        run([*common,str(N/'demand_bytes.cpp'),'-Wl,--gc-sections','-lcrypto','-o',str(binary)],tag+'-demand-bytes')
        for repeat in range(2):
            with tempfile.TemporaryDirectory(prefix='byte-fixture-',dir=P/'build') as tmp:
                log=P/'evidence'/f'{tag}-demand-bytes-{repeat}.log'
                with compiler_turn(),log.open('w') as f:
                    subprocess.run([str(binary),tmp],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,
                        preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3)))
                a,b=Path(tmp)/'expected.bin',Path(tmp)/'actual.bin';assert sha(a)==sha(b)
                records.append(dict(compiler=tag,repeat=repeat,passed=True,bytes=a.stat().st_size,sha256=sha(a),binary_sha256=sha(binary)))
                print(tag,repeat,'real-shape exact PASS',flush=True)
        assert records[-1]['sha256']==records[-2]['sha256']
    save(P/'evidence/bytes.json',dict(passed=True,device_executed=False,records=records,
        sources={str(f.relative_to(P)):sha(f) for f in (N/'demand_bytes.cpp',N/'p58ag_expert.hpp',N/'p100_down.hpp',P/'native/demand.hpp')},
        max_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
if __name__=='__main__':main()
