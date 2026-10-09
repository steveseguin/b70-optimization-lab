Attempt 1 (2026-10-09 01:32:24 UTC): `docker run` refused the argument
`--device=/dev/dri/by-path/pci-0000:23:00.0-render:/dev/dri/renderD128:rw`
("bad format for path": docker splits --device on colons, and the by-path name contains two).
No container was created, no process opened a render node, the kernel journal stayed at zero fault
lines. The watcher then hit its 150-second bound (STOP written by the watcher, not by a device event).
Fix: resolve the by-path symlink to its renderD node in the printer and pass that; the by-path name
is kept in the receipt via an environment variable. Re-run is a fresh first attempt, not a retry after a fault.
