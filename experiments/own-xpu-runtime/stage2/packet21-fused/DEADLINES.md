# Packet 21 expected durations and watchdogs

Prepared during FAULT HALT. No device code ran. These are planning proxies,
not measured packet21 device performance. Expected duration is reported only;
it never triggers a signal or a failed gate. A separate watchdog requests a
cooperative stop only at its stated bound. No external shorter timeout is allowed.

| Window | Expected work | First-run JIT proxy | Expected total | Default watchdog | Minimum watchdog | Default margin |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| K1, each component pair | 1,800 s | 17 s | 1,817 s | 10,800 s | 7,300 s | 5.94× |
| W0 | 30 s | 17 s | 47 s | 600 s | 300 s | 12.77× |
| W1 | 1,897.718 s | 17 s | 1,914.718 s | 10,800 s | 7,659 s | 5.64× |
| W2 | 1,897.718 s | 17 s | 1,914.718 s | 10,800 s | 7,659 s | 5.64× |
| W3 | 1,200 s | 17 s | 1,217 s | 10,800 s | 4,868 s | 8.87× |

Every minimum is at least max(300 s, ceil(4 × expected total)); K1 rounds its
7,268-second four-times floor upward to 7,300 seconds. Upper limits are 1,800 s
for W0 and 10,800 s elsewhere. W1/W2 reuse the deliberately conservative
packet18 frozen CPU-gate sizing proxy; W3 uses packet18's 1,200-second planning
proxy. K1 allows 1,800 seconds for both expanded fixture components, including M=87
and their additional startup overhead. Its shared watchdog spans both children;
it does not restart at the second component.
These are not predictions derived from launch count. The approximately 17-second
first-run JIT comes from earlier device evidence and is not a packet21 measurement.

## Per-submission budgets are separate

The slowest known reference kernel is the **single-work-item reference core row,
approximately 1.05 seconds on card**. Existing parallel kernels are below
20 milliseconds. Neither observation establishes an upper bound for the new
fused kernels. The driver job timeout is 5 seconds.

K1's submission budget is **strictly below 4 seconds**, assessed from device
profiling after completion. The fixture receipt fails a completed over-budget
submission; an expectation never sends a signal. W1/W2/W3 use the same 4-second
planning budget and retain site timing evidence for review. K1 must qualify the
new fused kernels before model windows run. It cannot guarantee that every
full-model shape or compiler specialization has the same duration.

W0 retains its stricter **below 100 milliseconds** profiled submission gate.
The canary completes its fixed coverage and normal teardown before reporting
an exceeded budget; aggregate duration is not a canary pass gate.

The multi-site non-GEMV correctness construction serializes groups inside one
work-group. It may exceed the old parallel-kernel duration and must not inherit
the below-20-ms label. If K1 finds a slow submission, keep it failed and redesign
the grouping; never mask the fault with a larger driver timeout or restart.

## Stop and wait behavior

Native model cooperative deadline equals the admitted watchdog. It stops new
work and drains or retains ownership; it does not signal itself. A watcher
expiry, new kernel fault or lost kernel monitoring requests at most one SIGTERM
to its captured child. After a 60-second cooperative drain it reports any live
child and preserves its unit. There is no SIGKILL, group kill, automatic restart
or retry. The child owns all resources until safe teardown.

Inherited completion waits are 5 seconds in the tiny canary and 60 seconds in
model-operation drain/teardown. Journal helper timeout is 2 seconds, loader
inspection 10 seconds, ionice inspection 2 seconds; these are CPU-helper bounds.
Postflight observes the kernel journal for 5 seconds after child exit. Watcher
polling is 250 milliseconds. Blocking runtime/JIT APIs have no unsafe hard kill.
The roomier process watchdog includes startup/JIT; it is not a per-kernel budget.

Prepared user units explicitly use `Type=exec`, `ExitType=cgroup`,
`KillMode=process`, `SendSIGKILL=no`, and `Restart=no`. Thus watcher exit after
its 60-second drain does not make the service finished while its native child
is retained, and service-stop handling cannot escalate to a cgroup SIGKILL.
These are future command properties only; no unit was created or modified here.
