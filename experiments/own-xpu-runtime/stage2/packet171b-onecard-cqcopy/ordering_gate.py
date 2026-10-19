"""Gate 1: CPU foreground-copy ordering test that fails on the old routing.

Runs the mock-queue test built (in build_engine's single compile turn) from the
same p171 templates SyclDevice instantiates, once as the candidate and once with
-DP171_PARENT_ROUTING (packet58as single_device.cpp:108-124,187-190 routing).
Also proves the device source differs from the packet58as base commit only by
apply_cqcopy_delta.py, and that SyclDevice::fill stays byte-identical.
"""
import importlib.util,json,subprocess,tempfile
from pathlib import Path
from build_engine import P,B,ROOT,sha,save,limits

BASE_COMMIT='dabfc958b7d3322dda3eeada3689b4d6011b7cc1'
PARENT='experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait'
FILES=('native/generated/single_device.cpp','native/generated/main.cpp','native/bracket_table.hpp')

def parent_text(rel):
    raw=subprocess.run(['git','-C',str(ROOT),'show',f'{BASE_COMMIT}:{PARENT}/{rel}'],stdin=subprocess.DEVNULL,capture_output=True,check=True).stdout
    return raw.decode().replace('packet58as-onecard-spinwait',P.name)

def between(text,start,end):
    i=text.index(start);return text[i:text.index(end,i)]

def main():
    limits();records=[]
    expected_old=('FAIL: B: a foreground copy reached the BCS foreground list','FAIL: B: a compute-queue barrier was submitted',
                  'FAIL: B: foreground_sync waited on an idle copy list')
    for tag in ('gnu','intel'):
        new=B/(tag+'-cqcopy-test');old=B/(tag+'-cqcopy-parent')
        ok=subprocess.run([str(new)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
        bad=subprocess.run([str(old)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
        assert ok.returncode==0 and json.loads(ok.stdout)=={'passed':True,'failures':0},(ok.stdout,ok.stderr)
        assert bad.returncode==1 and json.loads(bad.stdout)['passed'] is False,(bad.stdout,bad.stderr)
        fails=[s for s in bad.stderr.splitlines() if s.startswith('FAIL')]
        assert all(e in fails for e in expected_old),fails
        assert not any(s.startswith('FAIL: A:') for s in fails),'parent routing must still pass the A-view checks'
        records.append(dict(compiler=tag,candidate_binary_sha256=sha(new),candidate_passed=True,
            parent_routing_binary_sha256=sha(old),parent_routing_returncode=bad.returncode,parent_routing_failures=fails))
    # Source delta: parent bytes + apply_cqcopy_delta == current sources, nothing else.
    spec=importlib.util.spec_from_file_location('delta',P/'apply_cqcopy_delta.py');delta=importlib.util.module_from_spec(spec);spec.loader.exec_module(delta)
    with tempfile.TemporaryDirectory(dir=B) as d:
        d=Path(d)
        for rel in FILES:(d/Path(rel).name).write_text(parent_text(rel))
        delta.single_device(d/'single_device.cpp');delta.main_cpp(d/'main.cpp');delta.bracket_table(d/'bracket_table.hpp')
        for rel in FILES:assert (d/Path(rel).name).read_text()==(P/rel).read_text(),rel
    device=(P/'native/generated/single_device.cpp').read_text();parent=parent_text(FILES[0])
    fill=between(device,'  Event fill(','  bool fill_complete(');assert fill==between(parent,'  Event fill(','  bool fill_complete(')
    assert 'maintenance_queue_->memcpy(dst,src,bytes,after)' in fill
    header=(P/'native/cq_copy.hpp').read_text();assert 'maintenance_queue_' not in header and 'fill(' not in header
    for name in ('Event fill(','bool fill_complete(','void finish_fills()','Event compute(','std::function<Event()> prepare(','bool wait(Event e'):
        assert between(device,name,'\n  }')==between(parent,name,'\n  }'),name
    save(P/'evidence/cqcopy-order.json',dict(passed=True,device_executed=False,records=records,
        candidate_checks=['no BCS foreground copy','no compute-queue barrier','50 foreground copies on the in-order compute queue',
                          'readback ordered after the compute tail','readback recorded as the compute tail',
                          'fills reach the maintenance list','sync skips an idle copy list','pending copy-list work drained at the switch',
                          'barrier recovery only in copy-queue mode','A views keep BCS copy + barrier and two-queue sync'],
        fails_on_old_code=True,old_code='P171_PARENT_ROUTING build: packet58as BCS copy + per-copy barrier + two-queue sync',
        source_delta_only=True,base_commit=BASE_COMMIT,fill_source_identical=True,wait_spin_compute_prepare_identical=True,
        mock_backend=True,sycl_instantiation='native/generated/single_device.cpp (device build)'))
    print('PASS ordering test (GNU/Intel); parent routing fails it; device source = parent + delta; fills unchanged')
if __name__=='__main__':main()
