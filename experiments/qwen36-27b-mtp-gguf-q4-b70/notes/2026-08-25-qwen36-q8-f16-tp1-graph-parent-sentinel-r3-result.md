# Qwen3.6 target-Q8 F16 TP1 graph parent sentinel R3 result

State: **failed-incomplete on redundant candidate configuration strings**.

R3 passed the repaired graph-off control and then ran the complete graph-on
candidate. The candidate recorded four executable graphs, replayed 66 graph
requests, served 62 direct persistent-cache hits, had zero compatibility or
device rejection, and reported cache limit 8. Its raw stdout exactly matched
the graph-off control (`cc12d7e...`). Both processes exited and cleaned.

The frozen parser nevertheless stopped before issuing a candidate receipt
because the backend omits the same three human-readable configuration strings
already removed from the control. The machine-readable summary and action
markers directly prove their substance. R3 remains failed and contributes no
reusable arm or matrix authority.

R4 may remove only those three unavailable candidate strings. It retains the
positive requested/recording/replay/direct-replay markers, exact summary,
cache limit 8, positive requested/recorded/created/replayed/direct/cache-hit
counts, zero rejection counters, exact stdout parity, all lifecycle/identity
gates, and zero publication/speed authority.
