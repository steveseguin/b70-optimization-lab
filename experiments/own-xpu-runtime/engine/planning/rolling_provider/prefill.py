"""Verified prompt prefill for the existing native op15/op9 ring owners."""
import struct
import time
from concurrent.futures import ThreadPoolExecutor


OP = 15
DRAFT = 9
HEADER_BYTES = 4096
REVERSE_OFFSET = 2 * 65536 + 4096
REVERSE_READY_OFFSET = 2 * 65536 + 192


def map_bytes(rows, stream_bytes):
    return HEADER_BYTES + 4 * rows * stream_bytes


def region(mapping, kind, index, rows, stream_bytes, count=None):
    count = rows if count is None else count
    group = {'forward': 0, 'reverse': 2}[kind]
    begin = HEADER_BYTES + (group + index) * rows * stream_bytes
    return memoryview(mapping)[begin:begin + count * stream_bytes]


def verified_metadata(wire, row, stage, final):
    return wire.ROW_META.pack(0x52494e47, 1, wire.ROW_META.size, 0,
        row.epoch, row.identity, row.parent, row.position, row.token, row.fixture,
        stage, int(final), -1, 0, 0, 0, 1, row.request, row.before, row.after,
        wire.EMPTY_SHA, bytes(16))


def run(stages, model, plan, base, pending, ring):
    pipeline = plan.get('prefill_pipeline', False)
    base.require(type(pipeline) is bool, 'prefill pipeline boolean')
    rows = plan.get('prefill_rows', 0)
    base.require(type(rows) is int and 0 <= rows <= 256, 'prefill rows integer bound 0..256')
    # Diagnostic host wall seconds, not kernel/device timings. Target and draft
    # phases are disjoint; OP command walls are a subset of target_wall_s.
    timing = dict(schema='rolling-prefill-host-wall-v1', total_wall_s=0.0,
                  target_wall_s=0.0, target_command_wall_s=[0.0]*4,
                  draft_replay_wall_s=0.0, other_wall_s=0.0)
    empty = dict(prefill_positions=0, prefill_chunks=0, prefill_draft_replay=0,
                 prefill_timing=timing)
    if not rows:
        return empty
    base.require(len(stages) == 4 and plan.get('provider_stage', 0) == 0 and
                 plan.get('speculative_depth') == 3,
                 'batched prefill requires four-stage depth3 local provider')
    bulk = len(model.prompt)-2
    if bulk < rows:
        return empty
    base.require(all(s.prefill_rows == rows and s.stream_bytes == stages[0].stream_bytes
                     for s in stages), 'uniform native prefill maps')
    if pipeline:
        return run_pipeline(stages, model, rows, bulk, base, pending, ring)
    began = time.perf_counter()
    model.adopt_prefill(bulk)
    stream = stages[0].stream_bytes
    provider = stages[0]
    chunks = drafts = 0
    for start in range(0, bulk, rows):
        target_began = time.perf_counter()
        count = min(rows, bulk-start)
        parity = (start//rows) % 2
        stages[0].prefill[16:16+4*count] = struct.pack(f'<{count}i', *model.prompt[start:start+count])
        for index, stage in enumerate(stages):
            if index:
                source_kind = 'forward' if index == 1 else 'reverse'
                region(stage.prefill, 'forward', parity, rows, stream, count)[:] = \
                    region(stages[index-1].prefill, source_kind, parity, rows, stream, count)
            row = model.rows[start+count-1].row
            metadata = verified_metadata(pending.wire, row, index, index == len(stages)-1)
            stage.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+len(metadata)] = metadata
            command_began = time.perf_counter()
            reply = stage.command(OP, count, start, parity)
            timing['target_command_wall_s'][index] += time.perf_counter()-command_began
            base.require(reply[3] == count*stream, 'native prefill reply extent')
        target_ended = time.perf_counter()
        timing['target_wall_s'] += target_ended-target_began
        chunks += 1
        draft_began = time.perf_counter()
        final_reverse = region(stages[-1].prefill, 'reverse', parity, rows, stream, count)
        for position in range(max(1, start+1), start+count+1):
            hidden = final_reverse[(position-1-start)*stream:(position-start)*stream]
            provider.shared[base.SLOT*2+4096:base.SLOT*2+4096+stream] = hidden
            provider.shared[REVERSE_READY_OFFSET:REVERSE_READY_OFFSET+4] = struct.pack('<I', position)
            if position < bulk:
                row = model.rows[position].row
            else:
                parent = model.rows[bulk-1].row
                row = ring.Row(model.epoch, bulk+1, parent.identity, bulk, model.prompt[bulk], 0,
                               model.request, parent.after, model.proposals.hashes[bulk+1])
            metadata = verified_metadata(pending.wire, row, 0, False)
            provider.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+len(metadata)] = metadata
            provider.command(DRAFT, model.prompt[position], position, 0)
            drafts += 1
        timing['draft_replay_wall_s'] += time.perf_counter()-draft_began
    base.require(drafts == bulk, 'canonical prefill DRAFT replay extent')
    for stage in stages:
        stage.physical = stage.committed = bulk
    timing['total_wall_s'] = time.perf_counter()-began
    timing['other_wall_s'] = (timing['total_wall_s']-timing['target_wall_s']-
                              timing['draft_replay_wall_s'])
    return dict(prefill_positions=bulk, prefill_chunks=chunks, prefill_draft_replay=drafts,
                prefill_timing=timing)


def run_pipeline(stages, model, rows, bulk, base, pending, ring):
    """Two-chunk waves; requires native bounded prefill replay ownership.

    Host work durations overlap: never subtract them from total wall. Phase
    walls are disjoint (target-only, mixed target/draft, draft-only); their
    residual is orchestration/adoption/finalization. No device timing claim.
    """
    timing = dict(schema='rolling-prefill-host-wave-wall-v2', total_wall_s=0.0,
                  target_command_work_wall_s=[0.0]*4, target_work_wall_s=0.0,
                  draft_replay_work_wall_s=0.0, target_only_phase_wall_s=0.0,
                  mixed_phase_wall_s=0.0, draft_only_phase_wall_s=0.0,
                  other_wall_s=0.0)
    began = time.perf_counter()
    model.adopt_prefill(bulk)
    stream = stages[0].stream_bytes

    def target(index, start):
        work_began = time.perf_counter()
        count, parity = min(rows, bulk-start), (start//rows) % 2
        stage = stages[index]
        if index == 0:
            stage.prefill[16:16+4*count] = struct.pack(f'<{count}i', *model.prompt[start:start+count])
        else:
            kind = 'forward' if index == 1 else 'reverse'
            region(stage.prefill, 'forward', parity, rows, stream, count)[:] = \
                region(stages[index-1].prefill, kind, parity, rows, stream, count)
        metadata = verified_metadata(pending.wire, model.rows[start+count-1].row,
                                     index, index == 3)
        stage.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+len(metadata)] = metadata
        command_began = time.perf_counter()
        reply = stage.command(OP, count, start, parity)
        command_wall = time.perf_counter()-command_began
        base.require(reply[3] == count*stream, 'native prefill reply extent')
        return index, command_wall, time.perf_counter()-work_began

    def replay(start):
        work_began = time.perf_counter()
        count, parity = min(rows, bulk-start), (start//rows) % 2
        final_reverse = region(stages[-1].prefill, 'reverse', parity, rows, stream, count)
        provider = stages[0]
        for position in range(start+1, start+count+1):
            hidden = final_reverse[(position-1-start)*stream:(position-start)*stream]
            provider.shared[REVERSE_OFFSET:REVERSE_OFFSET+stream] = hidden
            provider.shared[REVERSE_READY_OFFSET:REVERSE_READY_OFFSET+4] = struct.pack('<I', position)
            if position < bulk:
                row = model.rows[position].row
            else:
                parent = model.rows[bulk-1].row
                row = ring.Row(model.epoch, bulk+1, parent.identity, bulk, model.prompt[bulk], 0,
                               model.request, parent.after, model.proposals.hashes[bulk+1])
            metadata = verified_metadata(pending.wire, row, 0, False)
            provider.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+len(metadata)] = metadata
            provider.command(DRAFT, model.prompt[position], position, 0)
        return count, time.perf_counter()-work_began

    chunks = drafts = 0
    # A phase barrier owns every stage until its command and all shared-memory
    # reads/writes complete. On error the context joins both workers before
    # propagating; no subsequent phase is submitted and nothing is retried.
    with ThreadPoolExecutor(max_workers=2) as pool:
        def phase(targets=(), draft=None):
            phase_began = time.perf_counter()
            futures = [pool.submit(target, index, start) for index, start in targets]
            draft_future = None if draft is None else pool.submit(replay, draft)
            for future in futures:
                index, command_wall, work_wall = future.result()
                timing['target_command_work_wall_s'][index] += command_wall
                timing['target_work_wall_s'] += work_wall
            count = 0
            if draft_future is not None:
                count, wall = draft_future.result()
                timing['draft_replay_work_wall_s'] += wall
            key = ('mixed_phase_wall_s' if targets and draft is not None else
                   'target_only_phase_wall_s' if targets else 'draft_only_phase_wall_s')
            timing[key] += time.perf_counter()-phase_began
            return count

        for a in range(0, bulk, 2*rows):
            b = a+rows
            phase(((0, a),))
            if b < bulk:
                phase(((1, a), (0, b)))
                phase(((2, a), (1, b)))
                phase(((3, a), (2, b)))
                drafts += phase(((3, b),), a)
                drafts += phase(draft=b)
                chunks += 2
            else:
                for index in (1, 2, 3):
                    phase(((index, a),))
                drafts += phase(draft=a)
                chunks += 1
    base.require(drafts == bulk, 'canonical prefill DRAFT replay extent')
    for stage in stages:
        stage.physical = stage.committed = bulk
    timing['total_wall_s'] = time.perf_counter()-began
    timing['other_wall_s'] = timing['total_wall_s']-sum(timing[key] for key in
        ('target_only_phase_wall_s', 'mixed_phase_wall_s', 'draft_only_phase_wall_s'))
    return dict(prefill_positions=bulk, prefill_chunks=chunks,
                prefill_draft_replay=drafts, prefill_timing=timing)
