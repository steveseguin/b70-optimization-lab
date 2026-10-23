#!/usr/bin/env python3
"""Read-only final diet successor closure verification; no device or service actions."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');HERE=Path(__file__).resolve().parent;P=ROOT/'experiments/own-xpu-runtime/stage2/packet196-onecard-diet-chain'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def main():
    r=read(HERE/'READY-FOR-DEVICE.json');assert r==read(P/'READY-FOR-DEVICE.json')
    assert r['passed'] and r['ready_for_device_chain'] and r['final_content_write'] and r['last_packet_write']
    assert r['compiled_here'] is False and r['native_recompiled'] is False
    assert sha(P/'evidence/final-checks.json')==r['final_checks_sha256']
    for n,h in r['files_sha256'].items():assert sha(ROOT/n)==h,n
    assert {item['relative_path'] for item in r['orchestration_source_pins']}=={str(f.relative_to(ROOT)) for f in HERE.iterdir() if f.is_file() and f.suffix in ('.py','.sh')}
    for item in r['orchestration_source_pins']:assert sha(ROOT/item['relative_path'])==item['digest'],item['relative_path']
    b=read(P/'build-receipt.json')
    for root,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):
        for n,h in b[key].items():assert sha(root/n)==h,n
    for n,h in r['gates'].items():assert sha(ROOT/n)==h,n
    for n in ('diet-admission','diet-engine-binding','diet-script-argv','diet-tests','diet-submission','diet-final-rehearsals','launch-limits','launcher-tests'):
        g=read(P/'evidence'/f'{n}.json');assert g['passed'] and g['device_executed'] is False,n
    bind=read(P/'engine-binding.json')
    for row in bind['source_snapshot']['source_files']:assert sha(P/bind['source_snapshot']['directory']/row['relative_path'])==row['digest']
    d=read(P/'derived-chain.json');s=read(P/'runtime-selection.json')
    assert d['flags']==s['chain_flags']=={'--wait-policy':'spin','--foreground-io':'kernel','--expert-gateup':'diet'}
    assert s['cache_cap']=='max23' and s['cache_bytes']==s['cache_allocation_bytes']==23049601024
    assert hashlib.sha256(d['chain_command'].encode()).hexdigest()==r['chain_command_digest_sha256']
    assert read(P/'ready.json')['chain_command']==d['chain_command']
    assert read(ROOT/'scripts/packet58_onecard_record_threshold.json')['records'][-1]['threshold_tok_s']==36.60251162011413
    assert read(P/'evidence/diet-admission.json')['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert not (ROOT/d['chain_output']).exists() and not (P/'evidence/fault-review-diet-a.json').exists()
    for name in ('seal.py','verify_ready.py'):
        cp=subprocess.run([sys.executable,'-B',str(P/name)]+(['--verify'] if name=='seal.py' else []),stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
        assert cp.returncode==0,(name,cp.stderr[-500:])
    print(json.dumps(dict(passed=True,device_executed=False,files=len(r['files_sha256']),gates=len(r['gates']))))
if __name__=='__main__':main()
