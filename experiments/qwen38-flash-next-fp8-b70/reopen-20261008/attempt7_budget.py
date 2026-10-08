#!/usr/bin/env python3
"""CPU-only exact-pin counterfactual; preserve attempt 6 evidence and accounting."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import analyze_host_budget as old
import memory_plan
import screen

HERE = Path(__file__).resolve().parent


def build():
    placement = json.loads((HERE/'placement-attempt6-v5.json').read_text())
    contract = json.loads((HERE/'memory-contract.json').read_text())
    previous = old.build_budget(old.analyze(HERE/'runs/screen1b-mmap-calibrate-load-20261008-attempt6'), placement, contract)
    expert = sum(contract['pinned_expert_bytes_per_rank'])
    embeddings = 4*contract['pinned_input_embedding_bytes_per_rank']
    saving = previous['expert_reserved_total_bytes']-expert+previous['embedding_reserved_bytes']-embeddings
    steady = previous['plateau_scenario_bytes']-saving
    loading = steady+contract['global_staging_bytes']
    command = screen.launch(SimpleNamespace(mode='calibrate-load',port=19988,loading_ram_guard_gb=96),
                            HERE/'runs/screen1b-mmap-calibrate-load-20261008-attempt7')
    planner = memory_plan.build_prediction(command)
    return dict(schema='screen1b.attempt7-exact-pins-budget.v1', prediction_is_measurement=False,
        placement_changed=False, move_rows_to_ranks_1_3_needed=False,
        allocator_environment=memory_plan.launch_identity(command)['pinned_allocator_environment'],
        expert_payload_bytes=expert, expert_allocator_request_bytes=expert,
        previous_expert_rounded_bytes=previous['expert_reserved_total_bytes'],
        embedding_allocator_request_bytes=embeddings,
        ple_cache_bytes=previous['ple_cache_bytes'], ple_step_allocator_request_bytes=previous['ple_step_reserved_bytes'],
        ple_metadata_bytes=previous['ple_metadata_bytes'],
        private_runtime_excluding_ple_metadata_bytes=previous['anchor_cgroup_anon_excluding_bound_ple_metadata_bytes'],
        other_gpuactive_residual_bytes=previous['anchor_unattributed_gpu_bytes'],
        host_baseline_bytes=contract['host_baseline_bytes'],
        other_pressure_residual_bytes=previous['plateau_scenario_bytes']-sum((
            previous['expert_reserved_total_bytes'], previous['embedding_reserved_bytes'],
            previous['ple_cache_bytes'], previous['ple_step_reserved_bytes'], previous['ple_metadata_bytes'],
            previous['anchor_cgroup_anon_excluding_bound_ple_metadata_bytes'],
            previous['anchor_unattributed_gpu_bytes'],contract['host_baseline_bytes'])),
        removed_padding_bytes=saving, steady_pressure_bytes=steady,
        global_staging_bytes=contract['global_staging_bytes'], loading_pressure_bytes=loading,
        loading_plus_2gib_retention_bytes=loading+2*old.GIB,
        active_file_speed_allowance_bytes=contract['active_file_allowance_bytes'],
        loading_plus_active_files_plus_2gib_retention_bytes=loading+contract['active_file_allowance_bytes']+2*old.GIB,
        conservative_planner_steady_bytes=planner['illustrative_host_peak_bytes']-contract['active_file_allowance_bytes']-contract['global_staging_bytes'],
        conservative_planner_working_memory_bytes=planner['illustrative_host_peak_bytes'],
        recommended_loading_guard_bytes=96000000000,
        unchanged_watchdog_pressure_line_bytes=previous['exact_watchdog_pressure_line_bytes'],
        mtp1_measured_plateau_max_bytes=90000000000/1.15,
        assumptions=['Same runtime/OS/driver residual as attempt 6; do not add worker RSS twice.',
            'Exact requests supported by reviewed torch 2.13 source; installed XPU behavior unmeasured.',
            'Large pins are not cached after free; no savings credited for freed large staging buffers.',
            'Driver/page granularity and later MTP/capture retention are not a measured upper bound.',
            'File-cache allowance is desired working memory, not necessarily MemTotal minus MemAvailable.'],
        input_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in (
            'placement-attempt6-v5.json','memory-contract.json','overlay-manifest.json',
            'analyze_host_budget.py','attempt7_budget.py','evidence/attempt6-host-attribution.json',
            'evidence/torch-2.13-pinned-allocator/sources.json')}) , planner


if __name__ == '__main__':
    budget, planner = build()
    (HERE/'evidence/attempt7-exact-pins-budget.json').write_text(json.dumps(budget,indent=2)+'\n')
    (HERE/'evidence/attempt7-exact-pins-prediction.json').write_text(json.dumps(planner,indent=2)+'\n')
    print(json.dumps(budget,indent=2))
