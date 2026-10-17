# Packet53 retention

Keep source, compact CPU/window receipts, logs, manifests and seal in Git.
Keep generated build trees and full device iteration logs out of Git. The new
build must remain below1GB and retain its three bench binaries/three proof
binaries plus relink proofs. After gates, cleanup removes only this packet's
regenerable object/dependency files and records each hash/size. Rebuild with
CPU-BUILD.md; do not delete other packets' builds or any packet49c chain file.
No model weights or secrets are copied.
