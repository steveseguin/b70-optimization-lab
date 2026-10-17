#!/usr/bin/env python3
"""One process/card; eight operations, one capture, fifty eager/replay calls."""
import time
from common import Stages, arguments, finished, ready_go, write_json


def main():
    args = arguments(__doc__)
    stages = Stages(args.output)
    stages.mark('import_torch')
    import torch
    if not torch.__version__.startswith('2.11.'):
        raise RuntimeError(f'expected A367 torch 2.11, got {torch.__version__}')
    itt = torch._C._itt
    if not itt.is_available():
        raise RuntimeError('ITT unavailable')
    stages.mark('device_setup')
    torch.set_num_threads(1)
    torch.xpu.set_device(0)
    # Transfers finish BEFORE capture. All output buffers remain alive as well.
    a = (torch.arange(4096, dtype=torch.float32).reshape(64, 64) / 4096).to('xpu:0')
    b = a.clone()
    buffers = [torch.empty_like(a) for _ in range(8)]
    stream = torch.xpu.Stream()
    pool = torch.xpu.graph_pool_handle()
    graph = torch.xpu.XPUGraph()
    torch.xpu.synchronize()

    def kernels():
        torch.add(a, b, out=buffers[0])
        torch.add(buffers[0], .25, out=buffers[1])
        torch.mul(buffers[1], b, out=buffers[2])
        torch.sin(buffers[2], out=buffers[3])
        torch.clamp_min(buffers[3], 0, out=buffers[4])
        torch.mm(buffers[4], b, out=buffers[5])
        torch.softmax(buffers[5], dim=-1, out=buffers[6])
        buffers[7].copy_(buffers[6])

    stages.mark('warmup')
    with torch.xpu.stream(stream):
        for _ in range(5):
            kernels()
    torch.xpu.synchronize()
    stages.mark('capture')
    with torch.xpu.graph(graph, pool=pool, stream=stream):
        kernels()  # No H2D, tensor host read, ITT or timing call inside capture.
    torch.xpu.synchronize()
    ready_go(args, stages)
    timings = {}
    # Synchronize INSIDE every iteration marker. These microtest spans really
    # bound device execution; this attribution is NOT valid for the census's
    # asynchronous forward markers. Single replay = one small replay batch.
    for phase, call in [('eager', kernels), ('replay', graph.replay)]:
        stages.mark(phase)
        start = time.perf_counter()
        itt.rangePush(f'A367Feas|{phase}')
        try:
            for iteration in range(50):
                torch.xpu.synchronize()
                itt.rangePush(f'A367Feas|{phase}|i={iteration}')
                try:
                    call()
                    torch.xpu.synchronize()
                finally:
                    itt.rangePop()
        finally:
            itt.rangePop()
        timings[phase + '_wall_s'] = time.perf_counter() - start
        print(f'{phase}: {timings[phase + "_wall_s"]:.6f}s for 50 calls', flush=True)
    write_json(args.output / 'graph.json', dict(schema='a367-tracefeas-graph-v1',
               torch_version=torch.__version__, iterations=50, operations=8,
               shape=[64, 64], dtype='float32', synchronized_markers=True, **timings))
    finished(args, stages)


if __name__ == '__main__':
    main()
