# Preparation closeout: final storage guard

The CPU-only preparation replay was stopped cooperatively during prefill so the
final teardown write also receives an immediate df -B1 / check. This is a wrapper
guard change, not a numerical failure or arithmetic change. No completed oracle
is claimed. Preserve partial timings, attempt/build identities and logs here.
