"""CPU-only, receipt-aligned cache attribution; no device/runtime imports."""
import hashlib
import json
from pathlib import Path
import resource
import statistics

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PINS = {}


def read(path):
    raw = path.read_bytes()
    PINS[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw


def js(path):
    return json.loads(read(path))


def lines(path):
    return [json.loads(x) for x in read(path).splitlines() if x.strip()]


def main():
    records = []
    paths = [P.parent/'packet58p-onecard-record/evidence/card0-58p-a'/w
             for w in ('WS', 'WS128x', 'WS128')]
    paths += [P.parent/'packet58r-onecard-v5/evidence/card0-v5-a/route-rec/WSCREEN',
              P.parent/'packet58t-resident-lookups/evidence/card0-resident-a/resident/WSCREEN']
    for path in paths:
        window, summary = js(path/'window.json'), js(path/'summary.json')
        assert window['passed'] and summary['passed']
        caches = lines(path/'run/run/cache.jsonl')
        pos = 0
        for view in summary.get('views', [summary]):
            label = view.get('label', '')
            selected, decode, allrows = [], [], []
            folder = path/'run/run'/label
            for request in view['requests']:
                req = folder/request['prompt_id']
                pre, gen = lines(req/'prefill-timings.jsonl'), lines(req/'timings.jsonl')
                assert len(pre) == request['prompt_tokens']-1
                assert len(gen) == request['output_tokens']
                for timing in pre+gen:
                    cache = caches[pos]
                    pos += 1
                    assert cache['epoch'] == pos
                    allrows.append((timing, cache))
                    if timing['kind'] != 'prefill_token':
                        decode.append((timing, cache))
                        if 2 <= timing['generated_index'] <= 100:
                            selected.append((timing, cache))
                count = js(req/'cache-stats.json')
                assert count['fills_total'] == sum(r['fills'] for r in caches[:pos])
                assert count['fill_bytes_total'] == sum(r['fill_bytes'] for r in caches[:pos])
            assert len(selected) == 12*99
            def stats(rows):
                return dict(positions=len(rows),
                    token_wall_ms=statistics.mean(t['wall_ms'] for t,c in rows),
                    cache_wall_ms=statistics.mean(c['wall_ms'] for t,c in rows),
                    fills=statistics.mean(c['fills'] for t,c in rows),
                    fill_bytes=statistics.mean(c['fill_bytes'] for t,c in rows),
                    pointer_publications=144, pointer_bytes=144*512*16,
                    pointer_publication_ms=None,
                    pointer_time_reason='not separately instrumented; nested within cache wall')
            records.append(dict(path=str(path.relative_to(ROOT)), view=label,
                metric_events_2_100=stats(selected), all_decode=stats(decode), all_positions=stats(allrows),
                rate=view['class_balanced_tok_s_1_100_intervals_after_ttft']['median']))
        assert pos == len(caches)
    for path in [P.parent/'packet58r-onecard-v5/sources/main.cpp',
                 P.parent/'packet58j-onecard-port/owner.cpp',
                 P.parent/'packet58i-onecard-attribution/ATTRIBUTION.json']:
        read(path)
    result = dict(passed=True, device_executed=False, sources=PINS, records=records,
                  stop_threshold_ms=1.5, stop=False,
                  reason='Every retained metric-window mean exceeds 1.5 ms/token; implementation warranted.')
    assert all(r['metric_events_2_100']['cache_wall_ms'] >= 1.5 for r in records)
    (P/'evidence/measurement.json').write_text(json.dumps(result, indent=2)+'\n')
    for r in records:
        m=r['metric_events_2_100']
        print(r['path'].split('/')[3], r['path'].split('/')[-1], r['view'],
              {k:round(v,6) if isinstance(v,float) else v for k,v in m.items()})


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3,4*1024**3))
    main()
