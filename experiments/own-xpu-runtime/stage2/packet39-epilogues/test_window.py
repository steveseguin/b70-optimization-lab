#!/usr/bin/env python3
"""CPU-only end-to-end wrapper protocol; no device binary or discovery."""
import json, os, shutil, sys, tempfile
from pathlib import Path
import window
from types import SimpleNamespace

MOCK = r'''import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--mode');a=p.parse_args()
out=Path(a.output)
(out/'receipt.json').write_text(json.dumps({'passed':a.mode!='failure','device_executed':False,'mock':True,'LD_LIBRARY_PATH':os.environ.get('LD_LIBRARY_PATH')}))
fusions={'mock':'unfused' if a.mode=='slower' else 'p39.epilogue'}
if a.mode in ('conflict','act-rejected'):fusions={'expert-act-iq2':'p39.epilogue','expert-checks-iq2':'p39.epilogue'}
(out/'dispatch-measured.json').write_text(json.dumps({'schema':'packet26.dispatch.v1','classes':{},'gemv':{},'fusions':fusions}))
raise SystemExit(1 if a.mode=='failure' else 0)
'''

class MockServices(window.Services):
    def __init__(self, native, mode='pass'):
        self.native=native;self.mode=mode;self.contacts=0;self.journals=0
    def binaries(self):return {'p39-k0':'cpu-mock','p39-timing':'cpu-mock'}
    def boot(self):return 'mock-boot'
    def assembly(self):return {'mock':{'accepted':self.mode!='assembly-reject','reason':'mock regression'},'expert-act-iq2':{'accepted':self.mode!='act-rejected','reason':'mock activation spill'},'expert-checks-iq2':{'accepted':True,'reason':'accepted'}}
    def ldd(self,binary):
        if self.mode=='missing-library':raise RuntimeError('missing native library: libsycl.so => not found')
        return 'libc.so => /lib/system/libc.so (outside LD_LIBRARY_PATH is valid)'
    def journal(self,cursor=None):
        self.journals+=1
        if cursor is None:return 'old reviewed Fault response', 'own-start'
        if self.mode=='new-fault' and self.journals==2:return 'NEW Fault response', 'own-new'
        return '', 'own-next'
    def native_command(self,a,run):
        return self.native,window.command([sys.executable,'-B',self.native,'--output',run,'--mode',self.mode])
    def launch(self,argv,log,env):
        self.contacts+=1
        assert env==dict(os.environ), 'environment changed'
        return super().launch(argv,log,env)

def main():
    root=Path(tempfile.mkdtemp(prefix='protocol-',dir=window.P/'build'))
    old=os.environ.get('LD_LIBRARY_PATH');os.environ['LD_LIBRARY_PATH']='/coordinator/custom/lib:/opt/intel/lib'
    cases=[]
    try:
        native=root/'mock_native.py';native.write_text(MOCK)
        def run(name,mode='pass',window_name='K0',k0=None,authorized=True):
            out=root/name;s=MockServices(native,mode)
            args=['--window',window_name,'--card','3','--output',str(out)]
            if authorized:args+=['--authorized-device-window']
            if k0:args+=['--k0',str(k0)]
            code=window.main(args,s);row=json.loads((out/'window.json').read_text())
            assert row['passed']==(code==0)
            return out,row,s
        production=window.Services()
        _,k0_argv=production.native_command(SimpleNamespace(window='K0',card=3),root/'unused-k0')
        _,g4_argv=production.native_command(SimpleNamespace(window='G4',card=3),root/'unused-g4')
        assert '--compile-smoke' in k0_argv and '--compile-smoke' not in g4_argv and g4_argv[-2:]==['--repetitions','200']
        out,k0,s=run('k0');assert k0['passed'] and not (out/'FAULT.json').exists()
        assert json.loads((out/'run/receipt.json').read_text())['LD_LIBRARY_PATH']==os.environ['LD_LIBRARY_PATH']
        cases.append('K0 success, stale fault ignored, JSON persisted, LD_LIBRARY_PATH byte-for-byte')
        out,row,s=run('g4',window_name='G4',k0=root/'k0/window.json');assert row['passed'] and row['dispatch_sha256'];cases.append('G4 success + matching K0 + dispatch persistence')
        out,row,s=run('missing',mode='missing-library');assert not row['passed'] and not row['device_accessed'] and not s.contacts and not (out/'FAULT.json').exists();cases.append('missing library refusal: durable JSON, no contact, no latch')
        out,row,s=run('unauthorized',authorized=False);assert not row['passed'] and not s.contacts and not (out/'FAULT.json').exists();cases.append('authorization refusal before contact has no latch')
        out,row,s=run('failure',mode='failure');assert not row['passed'] and not (out/'FAULT.json').exists();cases.append('native failure durable, no false GPU fault latch')
        out,row,s=run('new-fault',mode='new-fault');assert not row['passed'] and (out/'FAULT.json').exists();cases.append('new cursor-relative fault latches and stops gracefully')
        out,row,s=run('no-k0',window_name='G4');assert not row['passed'] and not s.contacts;cases.append('G4 refused without K0 before contact')
        previous=json.loads((root/'k0/window.json').read_text());previous['card']=2;(root/'bad-k0.json').write_text(json.dumps(previous))
        out,row,s=run('bad-k0',window_name='G4',k0=root/'bad-k0.json');assert not row['passed'] and not s.contacts;cases.append('K0 card identity mismatch refused before contact')
        out,row,s=run('assembly-reject',mode='assembly-reject',window_name='G4',k0=root/'k0/window.json');assert row['passed'] and not json.loads((out/'run/dispatch-measured.json').read_text())['fusions'];assert (out/'run/dispatch-provisional.json').exists();cases.append('offline assembly rejection removes measured winner and retains raw proposal')
        out,row,s=run('slower',mode='slower',window_name='G4',k0=root/'k0/window.json');assert row['passed'] and not json.loads((out/'run/dispatch-measured.json').read_text())['fusions'];cases.append('slower candidate absent from dispatch; no unfused fake fusion')
        out,row,s=run('conflict',mode='conflict',window_name='G4',k0=root/'k0/window.json');assert row['passed'] and json.loads((out/'run/dispatch-measured.json').read_text())['fusions']=={'expert-act-iq2':'p39.epilogue'};cases.append('activation and status-only expert fusions mutually exclusive')
        out,row,s=run('act-rejected',mode='act-rejected',window_name='G4',k0=root/'k0/window.json');assert row['passed'] and json.loads((out/'run/dispatch-measured.json').read_text())['fusions']=={'expert-checks-iq2':'p39.epilogue'};cases.append('status-only fallback selected when activation rejected offline')
        window.persist(window.P/'protocol-tests.json',dict(passed=True,cpu_only=True,device_executed=False,checks=len(cases),cases=cases))
        print(json.dumps({'passed':True,'checks':len(cases),'device_executed':False}))
    finally:
        if old is None:os.environ.pop('LD_LIBRARY_PATH',None)
        else:os.environ['LD_LIBRARY_PATH']=old
        shutil.rmtree(root)
if __name__=='__main__':main()
