import sys, numpy as np
a = np.fromfile(sys.argv[1], dtype=np.float32); b = np.fromfile(sys.argv[2], dtype=np.float32)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2304
print(a.shape, b.shape)
a = a.reshape(-1, n); b = b.reshape(-1, n)
d = np.linalg.norm(a - b) / np.linalg.norm(b)
print('relative L2 %.3e  max abs %.3e  ref max %.3e  worst row %.3e' % (d, np.abs(a - b).max(), np.abs(b).max(),
      (np.linalg.norm(a - b, axis=1) / np.linalg.norm(b, axis=1)).max()))
