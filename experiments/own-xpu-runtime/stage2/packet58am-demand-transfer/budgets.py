"""Measured metadata storage scaling, never a performance projection."""
import json,math,shutil
from pathlib import Path
from prepare import P,AH,sha,save
def main():
    audit=json.loads((P.parent/'packet58al-demand-transfer-prep/evidence/parent-audit.json').read_text())
    sizes=[]
    for record in audit['measured_directory_sizes']:
        directory=P.parents[3]/record['path'];size=sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
        assert size==record['logical_bytes'];sizes.append(dict(path=record['path'],bytes=size))
    parent_bytes=next(r['bytes'] for r in sizes if r['path'].endswith('/WS128'))
    k1=sum(r['bytes'] for r in sizes if r['path'].endswith(('/K1a','/K1b')))
    prefill=sum(r['prefill_rows'] for r in audit['request_cold_rows']);parent_positions=prefill+12*128
    event=dict(kind='packed-H2D',id=18446744073709551615,start_ns=18446744073709551615,end_ns=18446744073709551615)
    row=dict(schema='packet58am.demand.v1',identity='packet58am-demand-a-smoke-A',position=999999,layer=47,mode='bcs-demand-retained32x2',slot_ids=list(range(10)),resident_slots=10,staged_entries=10,staged_bytes=19712000,copy_engine='copy-only-BCS',descriptor_producer=18446744073709551615,descriptor_readback=18446744073709551615,missing_consumer=18446744073709551615,clock_domain='same-device-sycl-profiling',events=[],all_consumers_completed=True,snapshot_disposition='retained-until-policy')
    encode=lambda value:len((json.dumps(value,separators=(',',':'))+'\n').encode())
    base=encode(row);event_size=encode(event)
    # Each position has 48 descriptors, two descriptor events and at most four
    # compute events per layer, plus <=64*3 packed copies across the fixed pool.
    bytes_per_position=48*base+(48*8+64*3)*(event_size+1)
    estimates={}
    for kind,views,tokens in [('smoke',2,64),('v5',5,128)]:
        positions=(prefill+12*tokens)*views
        baseline=math.ceil(parent_bytes*positions/parent_positions)
        diagnostics=bytes_per_position*positions if kind=='smoke' else 0
        estimate=baseline+diagnostics+(k1 if kind=='smoke' else 0)
        # Additional 50% covers streaming analyzer output, cooperative/fault
        # logs and temporary receipts; no duplicate raw evidence tree.
        reservation=math.ceil(estimate*1.5)
        assert reservation<=3*estimate
        estimates[kind]=dict(matched_measured_volume_estimate_bytes=estimate,planned_outstanding_write_bytes=reservation,
            baseline_bytes=baseline,new_schema_diagnostic_bytes=diagnostics,positions=positions,
            reservation_over_estimate=reservation/estimate,
            requires_actual_smoke_volume_refresh_before_admission=(kind=='v5'))
        path=P/'proposals'/f'{kind}.json';proposal=json.loads(path.read_text());proposal['storage']=estimates[kind];save(path,proposal)
    probe=json.loads((P/'evidence/preparation.json').read_text())['records'][-1]['probe_argv']
    census_path=Path(probe[probe.index('--output')+1])/'allocation-census.json';census=json.loads(census_path.read_text())
    rows=census['allocations'];staging=sum(r['bytes'] for r in rows if r['memory']=='device' and 'demand-' in r['label'])
    inherited_transfer=sum(r['bytes'] for r in rows if r['memory']=='device' and any(t in r['label'] for t in ('cache-publication-staging','parallel-controls','compact-routes')))
    assert staging+inherited_transfer<=268435456
    assert census['totals']['device']<=29963128848
    assert staging==126156800+96*496
    save(P/'allocation-plan.json',dict(passed=True,scope='real prepared allocation ledger with sparse CPU storage; not measured VRAM',
         census_sha256=sha(census_path),census=str(census_path.relative_to(P)),
         all_live_device_bytes=census['totals']['device'],demand_device_bytes=staging,
         inherited_transfer_device_bytes=inherited_transfer,transfer_allowance_bytes=268435456,
         device_owned_bound_bytes=29963128848,driver_allowance_bytes=536870912,device_reserve_bytes=1500000000,
         host_bound_bytes=90529619968,host_required_available_bytes=99119554560,host_reserve_bytes=8589934592,
         host_new_metadata_cap_bytes=2097152,host_shadow_stop_bytes=4294967296,all_views_same_maximum=True))
    save(P/'storage-budget.json',dict(passed=True,performance_extrapolation=False,measured_directories=sizes,
         new_schema_measurement_kind='serialized synthetic records; not device evidence',
         synthetic_row=row,synthetic_event=event,serialized_base_row_bytes=base,serialized_event_bytes=event_size,
         maximum_bytes_per_position=bytes_per_position,measured_parent_positions=parent_positions,
         root_floor_bytes=25000000000,cpu_preparation_stop_bytes=27000000000,
         root_free_at_preparation=shutil.disk_usage('/').free,estimates=estimates))
    print('Allocation and storage budgets PASS',estimates)
if __name__=='__main__':main()
