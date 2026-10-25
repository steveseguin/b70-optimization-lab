#!/usr/bin/env python3
"""One resident pipeline for an explicitly pinned cold-request suite."""
import argparse
import hashlib
import json
from pathlib import Path

import live_wavefront_driver as live
import persistent_live_suite as suite_tools
base, wave = live.base, live.wave


def make_plan(config_path):
    plan = live.make_plan(config_path)
    config = json.loads(Path(config_path).read_text())
    base.require(config.get('persistent_requests') is True, 'explicit persistent requests required')
    plan = suite_tools.enable_reset_plan(plan, config['build_receipt'])
    path = Path(config['suite']).resolve()
    raw = suite_tools.read_bounded(path, 4*1024**2)
    base.require(hashlib.sha256(raw).hexdigest() == config['suite_sha256'], 'independently pinned cold suite')
    suite = json.loads(raw)
    count = config.get('suite_prompt_count', 12)
    rows = suite_tools.validate_suite(suite, plan, count)
    base.require(plan['prompt_tokens'] == rows[0]['prompt_tokens'], 'plan prompt must match first cold request')
    dump_each = config.get('dump_each', False)
    base.require(type(dump_each) is bool, 'explicit per-request dump boolean')
    base.require(not dump_each or count <= 2, 'full per-request dumps limited to two-request qualification')
    plan.update(schema='ownrt.persistent-wavefront-driver-plan.v1', suite=str(path),
                suite_sha256=config['suite_sha256'], suite_prompt_count=count, dump_each=dump_each,
                limits='One loaded worker set; cold request reset before each prompt. Diagnostic timings until reset/state/output qualification passes.')
    plan['pins'][str(path)] = config['suite_sha256']
    plan['pins'][str(Path(__file__).resolve())] = base.digest(__file__)
    return plan


def run(stages, plan, guard, output):
    raw = suite_tools.read_bounded(plan['suite'], 4*1024**2)
    base.require(hashlib.sha256(raw).hexdigest() == plan['suite_sha256'], 'suite changed before execution')
    suite = json.loads(raw)
    return suite_tools.run_suite(stages, plan, guard, output, suite=suite,
                                 expected_count=plan['suite_prompt_count'], dump_each=plan['dump_each'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--unit')
    args = parser.parse_args()
    if not args.run:
        base.require(args.config is not None, 'planning config required')
        base.save(args.plan, make_plan(args.config))
        print(json.dumps(dict(plan=str(args.plan), sha256=base.digest(args.plan), device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit, 'explicit admission and owning unit required')
    plan = suite_tools.read_json(args.plan, 4*1024**2)
    base.require(plan == make_plan(plan['config']), 'persistent plan/source identity changed')
    admission = suite_tools.read_json(args.admission)
    base.require(admission['plan_sha256'] == base.digest(args.plan), 'persistent admission plan mismatch')
    wave.execute(plan, admission, args.unit, stage_type=live.LiveStage, driver=run, scripted_proposals=False)


if __name__ == '__main__':main()
