"""Read-only CPU audit of sealed predecessor sizes and merged admission budgets."""
import ast,json
from pathlib import Path
import storage as s
import window as w
P=Path(__file__).resolve().parent
E=P/'evidence/storage-admission-fix'

def main():
    predecessor=P.parent/'packet44-context'
    rows=[]
    for sealed in sorted(predecessor.glob('receipts-*/*/window.json')):
        receipt=json.loads(sealed.read_text());context=receipt['context'];name=sealed.parent.name
        local=predecessor/f'build/c{context}b'/name
        # Copied K0/K1 receipts can have a different context in their source.
        directory_context=32768 if '32768' in sealed.parent.parent.name else 4096
        local=predecessor/f'build/c{directory_context}b'/name
        same=(local/'window.json').is_file() and s.digest(local/'window.json')==s.digest(sealed)
        current=sum(f.stat().st_size for f in local.rglob('*') if f.is_file())
        states=[dict(path=str(f.relative_to(predecessor)),receipt_sha256=s.digest(f),
                     **json.loads(f.read_text())) for f in local.rglob('state-retention.json')]
        removed=[v for v in receipt.get('retained_artifacts',{}).values()]
        raw=sum(v.get('uncompressed_bytes',0) for v in removed)
        # A deliberately conservative reconstruction: retained tree + ALL raw
        # fixture/log bytes + the largest serial state dump. This is not a
        # measurement of block I/O, nor the sum of all writes across RESETs.
        peak=current+raw+max((v['original_bytes'] for v in states),default=0)
        requests=25 if name=='WS64' else 3 if name=='WL' else 13 if name.startswith('WS') else 1
        mapped='WS' if name in ('WS128','WS64','WL') else 'WSs' if name=='WSs128' else name
        projection=s.projected_write_bytes(mapped,requests,directory_context,8)
        assert peak<projection,(sealed,peak,projection)
        rows.append(dict(path=str(sealed.relative_to(P.parent)),sha256=s.digest(sealed),
            local_receipt_matches=same,context=directory_context,window=name,
            old_admission=receipt['storage_admission'],current_retained_bytes=current,
            recorded_raw_log_fixture_bytes=raw,state_receipts=states,
            recorded_total_state_write_bytes=sum(v['original_bytes'] for v in states),
            reconstructed_peak_upper_bytes=peak,new_projected_bytes=projection,
            caveat='W2m 32768 raw states were deleted by packet44 coordinator; current size is incomplete' if name=='W2m' and directory_context==32768 else
                   'Cumulative build_bytes deltas include other windows; admitted_write_bytes is a reservation, not measured I/O'))
    plan=json.loads((P/'memory-plan.json').read_text());memory=[]
    for rank,placement in plan['placements'].items():
        for context,c in placement['capacities'].items():
            device=sum(r['total_with_mtp_bytes'] for r in c['ranks'])
            pinned=2*4*1024**2+20492+200704
            required=device+29321610240+pinned
            assert required<97*1024**3
            memory.append(dict(draft_rank=int(rank),context=int(context),
                planned_device_bytes=device,host_table_bytes=29321610240,
                pinned_ipc_bytes=pinned,bounded_combined_bytes=required,
                required_MemAvailable=97*1024**3,margin_bytes=97*1024**3-required))
    projections=[]
    for context in (256,4096,32768):
        for name in w.CONFIG:
            count=13 if name in w.SUITE_WINDOWS else 1
            steps=16 if name=='WS128x' else 0 if name in w.SPEED_WINDOWS and name!='WSs' else 8
            projections.append(dict(context=context,window=name,requests=count,retained_steps=steps,
                projected_bytes=s.projected_write_bytes(name,count,context,steps),
                watchdog_seconds=w.watchdog(name,context=context)))
    # Exact source/line inventory prevents a prose audit silently omitting a
    # literal in the admission, reset, retention, or watchdog implementation.
    sources=('storage.py','window.py','draft_window.py','suite.py','window_safety.py',
             'memory_gate.py','memory_plan.py','pipeline.py','fixture_support.py',
             'cpu_merged_gate.py','capacity_cpu_gate.py','capacity_fixture_gate.py','capacity_draft_gate.py','capacity_selection_gate.py','hc_activation_gate.py','build.py','k2_summary.py')
    literals=[]
    for name in sources:
        tree=ast.parse((P/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and type(node.value) in (int,float) and abs(node.value)>=8:
                literals.append(dict(source=name,line=node.lineno,value=node.value))
    row=dict(passed=True,device_executed=False,source_sha256={n:s.digest(P/n) for n in sources},
        predecessor_windows=rows,memory=memory,projections=projections,literal_inventory=literals,
        free_floor_bytes=s.FREE_FLOOR,remaining_chain_reserve_bytes=s.CHAIN_RESERVE,
        structural_build_limit_bytes=s.BUILD_LIMIT,
        measurements_note='Current file sizes and authenticated retention sizes; reservations are never relabeled as actual writes. Deleted packet44 state bytes are not reconstructed as measurements.')
    (E/'admission-audit.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(dict(passed=True,predecessor_windows=len(rows),memory_rows=len(memory),projection_rows=len(projections),numeric_literals=len(literals))))

if __name__=='__main__':main()
