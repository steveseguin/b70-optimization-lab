# Window duration and stop rules

| Window | Expected duration (report only) | Graceful watchdog |
| --- | ---: | ---: |
| K0 compile smoke | 60 seconds | 300 seconds |
| G4 twelve-class, 200-repeat chain comparison | 240 seconds | 960 seconds |

These expectations are planning estimates, not a reason to abort a healthy
window. Watchdogs are at least four times the expectation and at least 300
seconds. The wrapper writes the failure first, then sends SIGTERM once. It
waits up to 360 further seconds and never sends SIGKILL. A retained process is
reported with its PID and belongs to the coordinator. No failure is retried.
New fault lines after the wrapper's own cursor latch the window; old reviewed
fault lines do not. K0 must succeed before G4. No model server is started.
