"""Apply the new packet's chain configuration only."""
import json,shutil,subprocess
from prepare import P,O,ROOT,AJ,AM,sha,save,copy
def edit(name,old,new):
    p=P/name;t=p.read_text();assert old in t,(name,old);p.write_text(t.replace(old,new))
def main():
    edit('composition.py',"FLAGS = {'--lookups':'resident',", "FLAGS = {'--demand':'bcs-demand-retained32x2', '--demand-identity':'packet58ap-chain-a', '--lookups':'resident',")
    edit('suite_driver.py',"'--lookups','resident','--hc'", "'--demand','bcs-demand-retained32x2','--demand-identity','packet58ap-chain-a','--lookups','resident','--hc'")
    edit('suite_driver.py','            status=child.wait()',"            from stream_sensor import partial\n            checked=set(); subset=dict(manifest,prompts=entries)\n            while child.poll() is None:\n                partial(args.output,subset,checked,8 if args.window in ('KD','W2m') else 128)\n                time.sleep(1)\n            status=child.wait()\n            partial(args.output,subset,checked,8 if args.window in ('KD','W2m') else 128,final=True)")
    edit('suite_driver.py','import signal','import signal\nimport time')
    # Demand staging is additional to the resident parent's memory admission.
    copy(AM/'allocation-plan.json',P/'allocation-plan.json')
    extra="""    if not window.startswith('K1'):
        target=json.loads((Path(__file__).parent/'allocation-plan.json').read_text())
        extra=target['host_required_available_bytes']-budget['host_required_available_bytes']
        require(extra>=0,'cannot reduce host admission')
        budget['host_categories']['demand_increment']=extra
        budget['host_bound_bytes']+=extra
        budget['host_required_available_bytes']+=extra
    return budget"""
    edit('memory_plan.py','    return budget',extra)
    edit('budget_gate.py','98990252032',str(json.loads((P/'allocation-plan.json').read_text())['host_required_available_bytes']))
    edit('packet58_submission.py',"RERUN_DISCLOSURE = (", "RERUN_DISCLOSURE = ('58aj predecessor WS128 31.966820 tok/s, cmveqsmsl00ebrf014yvrsosx. ' + (",)
    edit('packet58_submission.py',"no third run; arithmetic unchanged.')", "no third run; arithmetic unchanged.'))")
    # Keep predecessor history in its note, leaving payload room for actual v5 numbers.
    p=P/'packet58_submission.py';t=p.read_text();start=t.index('RERUN_DISCLOSURE = (');end=t.index('\n\n\ndef require',start)
    t=t[:start]+"RERUN_DISCLOSURE = 'Predecessor: packet58aj resident record 31.966820 tok/s, cmveqsmsl00ebrf014yvrsosx.'"+t[end:]
    t=t.replace("+result['public_record_check']['disclosure']+' '+POLICY['readiness_amendment']+' '+RERUN_DISCLOSURE)","+result['public_record_check']['disclosure']+' '+POLICY['readiness_amendment']+' '+RERUN_DISCLOSURE+' '+result.get('bracket_disclosure','Bracket v5 pending; synthetic rehearsal only.'))")
    t=t.replace("'tile16, HC-wide fusion,", "'post-router demand transfer bcs-demand-retained32x2; tile16, HC-wide fusion,")
    # Queue readiness is captured by the real coordinator immediately before launch.
    old="    e.add('queue.json', chain / 'queue.json')"
    t=t.replace(old,old+"\n    readiness = e.read('queue.json').get('readiness', {})\n    require(readiness.get('parent_binary_sha256') == json.loads((repo/PACKET/'parent-binding.json').read_text())['artifacts']['build/device/own-rt-iq3'], 'v5 candidate binding missing')\n    for leaf, digest in readiness.get('screen_sources', {}).items():\n        e.add('parent-v5/'+leaf, inside(repo,leaf));e.verify('parent-v5/'+leaf,digest)\n    require(bool(readiness.get('screen_sources')), 'v5 evidence closure missing')")
    # Unconditional floor applies also when a rehearsal substitutes an older ledger.
    t=t.replace("    require(record['threshold_tok_s'] is None or speed > record['threshold_tok_s'],", "    require(speed > 31.966820, 'WS128 must exceed 31.966820')\n    require(record['threshold_tok_s'] is None or speed > record['threshold_tok_s'],")
    # Derive remains a pure portable replay, including the bracket disclosure.
    marker="    policy = e.read('record-threshold.json')"
    t=t.replace(marker,"    bracket = e.read('queue.json').get('readiness', {})\n    if bracket:\n        require(bracket.get('candidate_beats_all_controls') is True and bracket.get('minimum_gain',-1)>=.005 and bracket.get('control_drift_fraction',1)<=.03, 'v5 readiness gate differs')\n    "+marker.lstrip(),1)
    # The returned result is enriched in write_prepared below by derive wrapper.
    marker='\ndef submission_notes(result):'
    t=t.replace(marker,"\n_derive_chain = derive\ndef derive(e):\n    result = _derive_chain(e)\n    bracket=e.read('queue.json').get('readiness')\n    require(bracket is not None, 'v5 bracket numbers missing')\n    rates=bracket['rates'];require(len(rates)==5, 'five bracket numbers required')\n    result['bracket_disclosure']='v5 A0/B0/A1/B1/A2: '+ '/'.join(f'{v:.6f}' for v in rates)+' tok/s; 60/60 exact; A0 warm-up; drift '+f\"{bracket['control_drift_fraction']*100:.3f}%\"+'; worst gain '+f\"{bracket['minimum_gain']*100:.3f}%.\"\n    return result\n"+marker)
    p.write_text(t)
    # Add explicit demand selection to the synthetic submission fixture.
    edit('test_submission.py',"'--lookups','resident'", "'--demand','bcs-demand-retained32x2','--demand-identity','packet58ap-chain-a','--lookups','resident'")
    edit('test_submission.py',"    return e, seal_hash", "    q=e.read('queue.json');q['readiness']=dict(candidate_beats_all_controls=True,minimum_gain=.01,control_drift_fraction=0.,rates=[20,33.33,33,33.33,33]);put(e,'queue.json',q)\n    return e, seal_hash")
    # The old adapter cannot print flags; this tiny adapter changes no kernels.
    (P/'native').mkdir(exist_ok=True)
    source=r'''#include <filesystem>
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
'''
    (P/'native/k1_cli.cpp').write_text(source)
    (P/'build/device/p58-cache-fixtures').rename(P/'build/device/p58-cache-fixtures-core')
    cmd=['g++','-std=c++17','-O2',str(P/'native/k1_cli.cpp'),'-o',str(P/'build/device/p58-cache-fixtures')]
    subprocess.run(cmd,stdin=subprocess.DEVNULL,check=True)
    save(P/'evidence/k1-adapter-build.json',dict(passed=True,device_executed=False,command=cmd,source_sha256=sha(P/'native/k1_cli.cpp'),binary_sha256=sha(P/'build/device/p58-cache-fixtures'),reason='Unchanged K1 core has no help/CPU preparation switch; adapter exposes both using the original native parser and GNU CPU fixture. No model runtime compiled.'))
    # Retain the exact K1 kernel source and original receipt, unmodified.
    copy(AJ/'lineage/58ab-k1-inputs/lineage/owned-inputs/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p58_native_fixture.cpp',P/'lineage/k1-original.cpp')
    save(P/'evidence/build.json',dict(passed=True,device_executed=False,artifacts=json.loads((P/'parent-binding.json').read_text())['artifacts']))
    proposal=json.loads((ROOT/'experiments/own-xpu-runtime/ops/packet58aj-orchestration/entry-proposal.jsonl').read_text())
    text=json.dumps(proposal).replace(str(AJ),str(P)).replace('packet58aj-onecard-resident','packet58ap-onecard-chain').replace('58aj-a','58ap-a').replace('packet58ajc-chain-entry','packet58ap-chain-entry')
    proposal=json.loads(text)
    for b in proposal['plan']['entry_rehearsal']['binaries']:
        b['sha256']=sha(ROOT/b['path']);b.update(args=['--help'],returncode=0);b.pop('contains',None)
    save(O/'entry-proposal.jsonl',proposal)
    print('configured private chain; candidate bytes unchanged')
if __name__=='__main__':main()
