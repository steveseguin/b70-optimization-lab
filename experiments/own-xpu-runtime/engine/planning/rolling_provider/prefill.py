"""Verified prompt prefill for the existing native op15/op9 ring owners."""
import struct
import time


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
