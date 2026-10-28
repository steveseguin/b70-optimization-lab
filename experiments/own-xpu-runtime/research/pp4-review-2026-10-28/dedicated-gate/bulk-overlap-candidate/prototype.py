"""CPU-only two-parity scheduling sketch; no model/device/transport imports."""
from concurrent.futures import ThreadPoolExecutor

def run(specs,target,replay,record,fail):
    # Main owns target commands; one worker owns provider socket. target returns
    # immutable source records/sequence snapshot; replay validates full native ACK.
    specs=tuple(specs)
    if not specs:return
    job=target(specs[0])
    with ThreadPoolExecutor(max_workers=1) as pool:
        for index in range(len(specs)):
            future=pool.submit(replay,job)
            try:
                following=target(specs[index+1]) if index+1<len(specs) else None
                ack=future.result();record(job,ack)
            except BaseException as error:
                fail(error) # existing Guard stop; join worker before closing maps
                raise
            job=following

def compute_only_bound(target,draft):
    assert len(target)==len(draft)>0
    serial=sum(target)+sum(draft)
    overlap=target[0]+sum(max(draft[i],target[i+1]) for i in range(len(draft)-1))+draft[-1]
    return dict(serial_component_seconds=serial,overlap_component_seconds=overlap,
                optimistic_saved_seconds=serial-overlap,
                scope='Algebra on recorded work components, not measured overlap or speedup.')
