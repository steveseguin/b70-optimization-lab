#!/usr/bin/env python3
"""CPU-only real-message preregistration. No service, device, native or HTTP calls."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import sys

P=Path(__file__).resolve().parent;ROOT=P.parents[3]
INTEGRATION=P.parents[1]/'integration'
sys.dont_write_bytecode=True
sys.path.insert(0,str(INTEGRATION))
from chat_codec import PinnedChatCodec

P198=P.parent/'packet198-postreply-checkpoint'
RUN=P198/'evidence/device-p198-lifecycle-A-a'
MODEL='qwen38-flash-next-ud-iq3-xxs-experimental'
CHECKPOINT_ROOT=P/'evidence/runcheckpoints'
FOLLOWUP='Continue with the next concrete steps and identify who owns each action.'
EDIT='Correction: the incident began at 14:05 UTC, not 14:00 UTC.\n\n'


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def tokens_sha(ids):return hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,row):Path(path).write_text(json.dumps(row,indent=2,ensure_ascii=False)+'\n')


def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    codec=PinnedChatCodec()
    suite=ROOT/'repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
    prompts={p['id']:p['prompt'] for p in read(suite)['prompts']}
    retained={row['path']:row for row in read(P198/'evidence/closeout-inventory.json')['files']}
    sources={str(suite.relative_to(ROOT)):sha(suite)}
    def reference(name):
        folder=RUN/'owner/requests'/name
        for path in (folder/'result.json',folder/'input.tokens'):
            rel=str(path.relative_to(ROOT));assert sha(path)==retained[rel]['sha256'];sources[rel]=sha(path)
        return list(map(int,(folder/'input.tokens').read_text().split())),read(folder/'result.json')['tokens']
    a,a_reply=reference('fresh-a');b,b_reply=reference('fresh-b')
    a384,a384_reply=reference('fresh-a-reference')
    assert a384==a and a384_reply[:256]==a_reply
    ma=[dict(role='user',content=prompts['incident-retrospective'])]
    mb=[dict(role='user',content=prompts['decision-memo'])]
    assert codec.encode(codec.render(ma))==a and codec.encode(codec.render(mb))==b
    assert codec.encode(codec.decode(a_reply))==a_reply and codec.encode(codec.decode(b_reply))==b_reply
    assert not set(a_reply+b_reply)&{248044,248046}
    continuation=[*ma,dict(role='assistant',content=codec.decode(a_reply)),dict(role='user',content=FOLLOWUP)]
    edited=[dict(role='user',content=EDIT+ma[0]['content']),*continuation[1:]]
    saved=a+a_reply;append_ids=codec.encode(codec.render(continuation));edit_ids=codec.encode(codec.render(edited))
    assert append_ids[:len(saved)]==saved
    edit_difference=next(i for i,(x,y) in enumerate(zip(saved,edit_ids)) if x!=y)
    rows=[]
    def row(name,session,messages,maximum,action,output_rule,service='parked',evict=()):
        ids=codec.encode(codec.render(messages));assert len(ids)+maximum<=4096
        item=dict(name=name,session=session,service=service,
            http=dict(method='POST',path='/v1/chat/completions',headers={'Content-Type':'application/json','X-Ownrt-Session':session},
                body=dict(model=MODEL,messages=messages,max_tokens=maximum,temperature=0,top_p=1,n=1,stream=False)),
            prompt_tokens=ids,prompt_token_count=len(ids),prompt_json_sha256=tokens_sha(ids),
            rendered_utf8_sha256=hashlib.sha256(codec.render(messages).encode()).hexdigest(),
            expected_policy_action=action,expected_disposition='SAVE' if service=='parked' else 'RELEASE',
            expected_output=output_rule,expected_evictions=list(evict))
        rows.append(item)
    def exact(name,tokens):return dict(kind='exact-recorded-p198',source_request=name,tokens=tokens,json_sha256=tokens_sha(tokens),finish_reason='length')
    row('a-park','p199-a',ma,256,'prefill',exact('fresh-a',a_reply))
    row('b-park','p199-b',mb,128,'prefill',exact('fresh-b',b_reply))
    row('a-chat-append','p199-a',continuation,128,'restore',dict(kind='pair-with-fresh-reference',reference_row='a-chat-fresh',max_tokens=128),evict=['p199-b'])
    rows[-1]['saved_prefix']=dict(source_row='a-park',visible_tokens=len(saved),json_sha256=tokens_sha(saved),
                                 exact_prefix=True,appended_tokens=len(append_ids)-len(saved))
    row('a-chat-fresh','p199-fresh',continuation,128,'prefill',dict(kind='exact-tokens-and-native-state-of-row',source_row='a-chat-append'))
    row('a-edited','p199-a',edited,128,'prefill',dict(kind='new-unreferenced-prompt',max_tokens=128,
        claim='Verify ordinary cap/native-stop/HTTP mapping only; no prerecorded token oracle for edited prompt.'))
    rows[-1]['prefix_refusal']=dict(known_first_difference_index=edit_difference,known_saved_token=saved[edit_difference],
        edited_token=edit_ids[edit_difference],proof='Difference occurs in the original prompt, before any unknown append completion; all extensions must miss.')
    row('final-b-no-park','p199-final-b',mb,128,'prefill',exact('fresh-b',b_reply),service='no-parking')
    vectors=dict(schema='packet199.real-message-vectors.draft-v1',status='CPU-preregistered; not a live admission seal',
        device_executed=False,native_executed=False,http_bound=False,model=MODEL,rows=rows,
        codec_provenance=dict(codec.provenance),tokenizer_identity=dict(codec.tokenizer_identity),native_stop_token_ids=[248044,248046],
        source_files_sha256=sources,
        unused_available_reference=dict(request='fresh-a-reference',prompt_tokens=a384,output_tokens=a384_reply,
            reason='Same prompt has a p198384-token reference, but six-turn proposal does not spend an extra request on it.'),
        reference_scope='P198 raw append469 is not this rendered chat prompt; no old append output is presented as an oracle for new chat rendering.')
    save(P/'vectors.json',vectors)
    fs=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        fields=line.split()
        if fields[4] in ('/mnt/usb-models','/'):fs.append(line)
    mount=Path('/mnt/usb-models');stat=mount.stat();root_free=shutil.disk_usage(ROOT).free;ext_free=shutil.disk_usage(mount).free
    runtime=[INTEGRATION/n for n in ('chat_codec.py','chat_service.py','chat_http.py','checkpoint_engine.py','checkpoint_bridge.py','native_checkpoint_store.py','request_front/client_v2.py')]+[ROOT/'tools/ctxkeeper/parking.py']
    admitted=read(INTEGRATION/'checkpoint-fixtures-p198/admitted-engine-identity.json')
    bound=read(INTEGRATION/'receipts/p198-checkpoint-size-bound.json')
    assert bound['engine_binary_sha256']==admitted['engine']['binary_sha256'] and bound['geometry']==admitted['geometry']
    assert bound['save_size_bound_bytes']==256*1024**2
    plan=dict(schema='packet199.chat-parking-draft-plan-v1',status='DRAFT: no READY, worker launch, listener, or window admission',
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),device_executed=False,native_executed=False,
        unit='packet199-chat-parking-a',output=str(P/'evidence/device-p199-chat-A-a'),
        parent_binary=str(P198/'build/device/own-rt-iq3'),binary_sha256=admitted['engine']['binary_sha256'],
        reuse='Unchanged p198 C++ binary, native arithmetic, full BF16 state and native v1.2+p198 checkpoint contract; no compilation.',
        identity=admitted,placement=dict(lane='A',card=0,pci='0000:23:00.0',native_cpu_affinity='0-3,16-19',native_nice=0,
            helper_cpu_affinity='8-15,24-31',helper_nice=19,omp_threads=2),
        host_required_available_bytes=98_990_252_032,coordinator_memory_margin_bytes=1024**3,
        request_budget=dict(requests=6,maximum_generated_tokens=sum(r['http']['body']['max_tokens'] for r in rows),
            maximum_context=4096,native_stop_token_ids=[248044,248046],controls=6,expected_saves=5,expected_releases=1,
            native_deadline_seconds=7200,idle_seconds=300,concurrency=1),
        http=dict(bind='127.0.0.1',port=0,listener_count=1,streaming=False,client_configuration=False,
            service_switch='Before final request only, coordinator confirms zero active handler and selects a second ChatService/Parking(budget0) on the same owner; record selection and retain shared512MiBpolicy.'),
        parking=dict(main_budget_bytes=512*1024**2,save_size_bound_bytes=256*1024**2,no_parking_budget_bytes=0,
            bound_receipt=str((INTEGRATION/'receipts/p198-checkpoint-size-bound.json').relative_to(ROOT)),bound_receipt_sha256=sha(INTEGRATION/'receipts/p198-checkpoint-size-bound.json'),
            expected_peak_reservations=2,accounting='Every SAVE includes existing/retained checkpoint reservations; before row3evictB; preserve oldA until replacementvisible.'),
        storage=dict(checkpoint_root=str(CHECKPOINT_ROOT),selection='Local private ext4 after separately verified p184 archive/prune headroom; no checkpoint root created.',
            fresh_exclusive_mode='0700',root_floor_bytes=27_000_000_000,root_write_forecast_bytes=640*1024**2,
            checkpoint_peak_bytes=512*1024**2,worker_logs_cache_restoration_allowance_bytes=128*1024**2,
            root_free_observed_bytes=root_free,root_after_forecast_bytes=root_free-640*1024**2,
            root_full_forecast_fits=root_free-640*1024**2>=27_000_000_000,
            root_stat=dict(st_dev=ROOT.stat().st_dev,uid=ROOT.stat().st_uid,gid=ROOT.stat().st_gid,mode=oct(ROOT.stat().st_mode&0o7777)),
            required_before_live='Coordinator must verify archive/prune receipts and fresh free-after-fullforecast >=27GB; never lower the floor.',
            unused_external_alternative=dict(path='/mnt/usb-models/own-runtime-checkpoints/packet199-chat-a',
                free_observed_bytes=ext_free,mount_observation=dict(path=str(mount),uid=stat.st_uid,gid=stat.st_gid,
                    mode=oct(stat.st_mode&0o7777),st_dev=stat.st_dev,inode=stat.st_ino,mountinfo=fs),
                rejected_without_probe='fuseblk uid0/mode0777 risks failing strict0700; root selected local ext4 after verified archival. Prepared fs_smoke.py unused; no external files created and no mount change.')),
        daily_endpoints='Preserve three current owner endpoints through one established graceful-stop window and one successful clean-drain restore; next restore suffix only if fresh. No service changes during preparation.',
        safety=['Reuse proven whole-host admission, fault polling, PAUSE-B preservation, queue/STOP checks and privileged passive pre/postdrain via future reviewed controller.',
            'No new request on fault; incident single cooperative retained-owner action, never kill/restart/reboot/reset or power/memory changes.',
            'Final no-parking RELEASE then stopped requests6 controls6 pendingfalse, owner exit0 and passive drain required before one restoration.',
            'Do not infer latency, cold performance or throughput from this functional HTTP pilot or external storage.'],
        vector_file='vectors.json',vector_sha256=sha(P/'vectors.json'),
        mutable_source_observations={str(f.relative_to(ROOT)):sha(f) for f in runtime},
        remaining_gates=['Verified closedp184 archival/prune receipts and refreshed localroot fullforecast headroom.',
            'Worker/controller implementation and independent review; no fullwindow prepared by this plan.',
            'Seal only after HTTP/service/store/codec/worker final and all exactidentity/argv/plan/gate tests pass.',
            'Root owner handles live --check, endpoint/window permission and one-shotlaunch; not authorized by this draft.'])
    save(P/'plan.json',plan)
    print(json.dumps(dict(passed=True,device_executed=False,rows=len(rows),prompt_counts=[r['prompt_token_count'] for r in rows],
        expected_policy=[r['expected_policy_action'] for r in rows],append_saved_prefix=len(saved),append_prompt=len(append_ids),
        edited_difference=edit_difference,root_after_forecast=plan['storage']['root_after_forecast_bytes'])))


if __name__=='__main__':main()
