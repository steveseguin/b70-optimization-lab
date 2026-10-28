"""CPU event/lease simulator for two chunks across target actors + provider.
No model math, native protocol substitute, process launch or device work.
"""
import heapq

def simulate(counts,durations,*,fail_at=None):
    counts=tuple(counts);n=len(counts);actors=len(durations);targets=actors-1
    assert targets in (2,3) and n>0 and all(type(c)is int and 0<c<=256 for c in counts)
    assert all(len(row)==n and all(t>0 for t in row) for row in durations)
    starts=[];total=0
    for c in counts:starts.append(total);total+=c
    now=0.;queue=[];events=[];busy=[None]*actors;next_chunk=[0]*actors
    completed=[set() for _ in range(actors)];frontier=[0]*actors
    leases={};parity_owner={};publications={};captures={};issued_sequence=[0]*actors
    failed=None;peak=0
    def issue_available():
        nonlocal peak
        for actor in reversed(range(actors)):
            k=next_chunk[actor]
            if busy[actor] is not None or k>=n:continue
            parity=k%2
            if actor==0:
                if len(leases)>=2:continue
                assert parity not in parity_owner,'parity reuse before provider full ACK'
                leases[k]=parity;parity_owner[parity]=k;peak=max(peak,len(leases))
            elif k not in completed[actor-1]:continue
            assert leases.get(k)==parity and parity_owner.get(parity)==k,'exact chunk lease'
            if actor:
                assert publications[actor-1,parity]==(k,counts[k]),'actual upstream source readiness'
            if actor==targets:
                captures[k]=(publications[0,parity],publications[targets-1,parity])
            busy[actor]=k;next_chunk[actor]+=1;issued_sequence[actor]+=1
            events.append(dict(event='issued',time=now,actor=actor,chunk=k,parity=parity,start=starts[k],count=counts[k],sequence=issued_sequence[actor],unfinished_chunks=len(leases)))
            heapq.heappush(queue,(now+durations[actor][k],actor,k))
    issue_available()
    while queue:
        now=queue[0][0];ready=[]
        while queue and queue[0][0]==now:ready.append(heapq.heappop(queue))
        for _,actor,k in ready:
            assert busy[actor]==k;busy[actor]=None
            if failed is not None:
                events.append(dict(event='drained-after-fault',time=now,actor=actor,chunk=k));continue
            if fail_at==(actor,k):
                failed=dict(actor=actor,chunk=k,time=now);events.append(dict(event='fault',**failed));continue
            parity=k%2
            assert leases[k]==parity and parity_owner[parity]==k
            assert frontier[actor]==starts[k],'per-owner ordered canonical position'
            frontier[actor]+=counts[k];completed[actor].add(k)
            if actor<targets:publications[actor,parity]=(k,counts[k])
            else:
                assert captures[k]==(publications[0,parity],publications[targets-1,parity]),'source records/raw parity changed before full ACK'
                del leases[k];del parity_owner[parity]
            events.append(dict(event='full-ack' if actor==targets else 'completed',time=now,actor=actor,chunk=k,parity=parity,position=frontier[actor]))
        if failed is None:issue_available()
    adopted=failed is None and all(p==total for p in frontier)
    assert failed is not None or adopted and not leases and all(b is None for b in busy)
    return dict(schema='ownrt.two-parity-stage-pipeline-cpu.v1',wall_seconds=now,adopted=adopted,
        failed=failed,frontiers=frontier,peak_unfinished_chunks=peak,live_leases_at_end=dict(leases),
        drained=all(b is None for b in busy),events=events,
        scope='Deterministic CPU control/lease simulation only; timing is input algebra, not native/GPU execution.')

def pair_wave(counts,durations):
    n=len(counts);actors=len(durations);total=0.
    for a in range(0,n,2):
        if a+1==n:total+=sum(row[a] for row in durations);continue
        total+=durations[0][a]
        for actor in range(1,actors):total+=max(durations[actor][a],durations[actor-1][a+1])
        total+=durations[-1][a+1]
    return total
