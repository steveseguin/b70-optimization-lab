#!/usr/bin/env python3
"""Generate current SC117 native command templates without importing lab adapters.

CPU planning only. This tool never starts an engine and provides no device-run
admission. A controller must independently enforce physical ownership, fault and
resource preflight, explicit run authority, stop coordination, and postflight.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

try:
    from . import prepare as prep
except ImportError:
    import prepare as prep

PROFILE = prep.HERE.parent/'profiles/sc117-iq3s'
POLICY_SHA256 = 'f50fbc4971ac553c7dcbd95af8355fc69c4f6ed4251437a7e4156dbdab088c62'
SLOT = 65536
SHARED_BYTES = 4*SLOT+4096+64


def hash_file(path, cap=1024**3):
    path=Path(path).absolute()
    with prep.Directory(path.parent) as directory, prep.HeldFile(directory,path.name) as held:
        prep.require(0 < held.before['bytes'] <= cap, 'bounded artifact size: '+str(path))
        return held.hash_range(0,held.before['bytes'],time.monotonic()+120)


def checked_file(path, trusted_sha, cap=2*1024**2):
    raw=prep.read_small(path,cap)
    prep.require(prep.hexhash(trusted_sha) and prep.digest(raw)==trusted_sha,'pinned artifact changed: '+str(path))
    return json.loads(raw,object_pairs_hook=prep.pairs)


def validate_local_files(binding, require_draft=False):
    for component in ('target','draft'):
        if component=='draft' and not require_draft:
            continue
        root=binding[component+'_root']
        prep.require(root is not None,'MTP needs an authenticated local draft binding')
        with prep.Directory(root) as directory:
            for name, expected in binding['shards'][component].items():
                with prep.HeldFile(directory,name) as held:
                    prep.require(held.before==expected,'local model identity changed: '+name)
                    held.stable()


def make_plan(deployment, profile_sha, binding_sha, receipt_path, receipt_sha,
              bdfs, library_dirs, output, prompt_tokens, mode='target-only',
              max_new=32, seconds=1800):
    deployment,receipt_path,output=map(lambda p:Path(p).absolute(),(deployment,receipt_path,output))
    authority=prep.validate_overlay(deployment/'include',profile_sha,binding_sha)
    binding=checked_file(deployment/'binding.json',binding_sha)
    policy=checked_file(PROFILE/'launch-policy.json',POLICY_SHA256)
    prep.require(policy['model_profile_sha256']==profile_sha,'launch policy belongs to another model profile')
    prep.require(mode in ('target-only','mtp'),'supported mode: target-only or mtp')
    prep.require(len(bdfs) in (2,4) and len(set(bdfs))==len(bdfs)
                 and all(re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]',b) for b in bdfs),
                 'two/four distinct canonical PCI BDFs required')
    prep.require(mode!='mtp' or len(bdfs)==2,'current MTP controller requires two ranks')
    prep.require(type(max_new)is int and 1<=max_new<=512 and type(seconds)is int and 30<=seconds<=172800,'bounded output/lifetime')
    prep.require(isinstance(prompt_tokens,list) and prompt_tokens
                 and all(type(t)is int and 0<=t<policy['vocab'] for t in prompt_tokens)
                 and len(prompt_tokens)+max_new-1<=policy['context'],'prompt/output context bounds')
    prep.require(not output.exists() and not output.is_symlink(),'fresh run output required')
    with prep.Directory(output.parent) as directory:
        parent=os.fstat(directory.fd)
        prep.require(parent.st_uid==os.getuid(),'run output parent must be owned')
        parent_identity=dict(dev=parent.st_dev,ino=parent.st_ino)
    validate_local_files(binding,mode=='mtp')
    libraries=[]
    for directory_path in library_dirs:
        with prep.Directory(directory_path) as directory:
            prep.require(':' not in str(directory.path),'library directory cannot contain colon')
            libraries.append(str(directory.path))
    prep.require(libraries and len(set(libraries))==len(libraries),'explicit unique runtime library directories required')
    receipt=checked_file(receipt_path,receipt_sha,4*1024**2)
    prep.require(receipt['schema']=='ownrt.engine.build.v1'
                 and receipt.get('generated_authority')==authority,'build did not use this generated authority')
    binary=Path(receipt['binary']).absolute()
    prep.require(hash_file(binary)==receipt['binary_sha256'],'build binary changed')
    prep.require(receipt.get('generated_dependencies')=={str(deployment/'include'/prep.HEADER):authority['header_sha256']},'compiled overlay dependency identity')
    runtime=receipt.get('runtime_assets')
    prep.require(isinstance(runtime,dict) and len(runtime)==1,'one pinned RoPE runtime asset required')
    for path,want in runtime.items():
        prep.require(Path(path).name=='rope.bf16' and hash_file(path,4*1024**2)==want,'RoPE runtime asset missing/changed')
    dispatch=PROFILE/policy['dispatch']['file']
    prep.require(hash_file(dispatch,2*1024**2)==policy['dispatch']['sha256'],'dispatch profile changed')
    profile,_,_,rows,_,_=prep.load_profile(deployment/'profile.json',profile_sha)
    cuts=policy['boundaries'][str(len(bdfs))]
    pins={str(deployment/'binding.json'):binding_sha,str(deployment/'profile.json'):profile_sha,
          str(receipt_path):receipt_sha,str(binary):receipt['binary_sha256'],
          str(PROFILE/'launch-policy.json'):POLICY_SHA256,str(dispatch):policy['dispatch']['sha256'],
          str(Path(__file__).resolve()):hash_file(__file__),str(prep.HERE/'prepare.py'):hash_file(prep.HERE/'prepare.py'),
          **runtime,**{str(deployment/k):v for k,v in binding['artifacts'].items()}}
    pins['/usr/bin/ionice'] = hash_file('/usr/bin/ionice', 2*1024**2)
    stages=[]
    for i,bdf in enumerate(bdfs):
        first,final=i==0,i==len(bdfs)-1
        local=output/f'stage{i}';native=local/'native'
        shared=output/'shared.bin' if mode=='mtp' else local/'shared.bin'
        argv=['/usr/bin/ionice','-c','3',str(binary),'--gsq-packed','--rank',str(0 if first else 1),
              '--channel','<channel-fd>','--stop-fd','<stop-fd>','--shared',str(shared),
              '--cards','1','--card','0','--output',str(native),'--memory','resident',
              '--context',str(policy['context']),'--seconds',str(seconds),'--native-nice','19',
              '--timing','token','--max-new',str(max_new),'--retain-steps','none','--draft-rank','0',
              '--target-split','23','--host-path','prepared','--plan',str(deployment/'placement.tsv'),
              '--identity',str(deployment/'shard-auth.tsv'),'--model-dir',binding['target_root'],
              '--authorized-device-window',*policy['target_flags'],
              '--reset-dump','none','--finish-dump','none','--token-stream','jsonl',
              '--activations','f32','--dispatch',str(dispatch)]
        if mode=='target-only':
            argv+=['--pipeline-boundaries',','.join(map(str,cuts)),'--pipeline-stage',str(i)]
        else:
            argv+=['--draft-experts',policy['mtp']['experts']]
            if first:
                argv+=['--draft-mtp','--draft-fault','none','--draft-manifest',str(deployment/'draft-manifest.tsv'),
                       '--draft-model',binding['draft_root']]
        environment=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=':'.join(libraries),
                         NEOReadDebugKeys='1',FilterBdfPath=bdf,ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',
                         ZE_AFFINITY_MASK='0',ONEAPI_DEVICE_SELECTOR='level_zero:0',**policy['environment'])
        for key,sub in [('SYCL_CACHE_DIR','sycl'),('NEO_CACHE_DIR','neo'),('XDG_CACHE_HOME','xdg')]:
            environment[key]=str(local/'cache'/sub)
        packed=sum(t['bytes'] for t in rows if t['component'] not in ('embedding','ple_lookup')
                   and (cuts[i]<=t['layer']<cuts[i+1] or (t['layer']==-1 and final)))
        prep.require(packed<=31000000000,'stage packed weights exceed current B70 planning bound')
        stages.append(dict(id=i,first=first,final=final,begin=cuts[i],end=cuts[i+1],bdf=bdf,
                           native_output=str(native),shared=str(shared),argv=argv,environment=environment,
                           packed_weight_bytes=packed))
    result=dict(schema='ownrt.portable-launch-plan.v1',model_profile_sha256=profile_sha,
        deployment_binding_sha256=binding_sha,model_id=profile['id'],pins=pins,output=str(output),
        output_parent_identity=parent_identity,boundaries=cuts,stages=stages,mode=mode,
        protocol='pipeline-target-only-v1' if mode=='target-only' else 'legacy-native-two-rank-mtp',
        context=policy['context'],prompt_tokens=prompt_tokens,max_new=max_new,seconds=seconds,
        vocab=policy['vocab'],eos=policy['eos_token_ids'][0],eos_token_ids=policy['eos_token_ids'],
        shared_bytes=SHARED_BYTES,activation_dtype='F32',prefill_rows=0,
        device_execution_requested=False,run_authorized=False,portable_observer_available=False,
        process_requirements=dict(nice=19,io_priority_class=3,
                                  controller_must_check_before_spawn=True,
                                  io_priority_enforced_by_argv=True),
        required_controller_gates=['explicit run admission bound to this plan SHA256','passive complete PID/FD physical ownership inventory',
            'controller nice level exactly19 before spawning; child ionice idle class3 and native nice19 validation',
            'unchanged boot, PCI mappings and kernel fault baseline','memory and storage floors','cooperative stop and no automatic retry',
            'bounded process lifetime and postflight','token/state qualification before speed claims'],
        limits='Command templates only. No controller/service deployment, physical admission, runtime parity or memory-fit certification. MTP uses existing fixed draft weights; no training.')
    result['command_sha256']=prep.digest(json.dumps(stages,sort_keys=True,separators=(',',':')).encode())
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deployment',type=Path,required=True)
    p.add_argument('--profile-sha256',required=True)
    p.add_argument('--binding-sha256',required=True)
    p.add_argument('--build-receipt',type=Path,required=True)
    p.add_argument('--build-receipt-sha256',required=True)
    p.add_argument('--bdf',action='append',required=True)
    p.add_argument('--library-dir',action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prompt-tokens',type=Path,required=True,help='JSON list of integer token IDs')
    p.add_argument('--mode',choices=('target-only','mtp'),default='target-only')
    p.add_argument('--max-new',type=int,default=32)
    p.add_argument('--seconds',type=int,default=1800)
    p.add_argument('--plan',type=Path,required=True)
    a=p.parse_args()
    prompt_raw=prep.read_small(a.prompt_tokens)
    result=make_plan(a.deployment,a.profile_sha256,a.binding_sha256,a.build_receipt,a.build_receipt_sha256,
        a.bdf,a.library_dir,a.output,json.loads(prompt_raw),a.mode,a.max_new,a.seconds)
    result['pins'][str(a.prompt_tokens.absolute())]=prep.digest(prompt_raw)
    with a.plan.open('xb') as output:output.write(prep.encoded(result))
    print(json.dumps(dict(plan=str(a.plan.absolute()),sha256=hash_file(a.plan),device_execution_requested=False,run_authorized=False)))


if __name__=='__main__':main()
