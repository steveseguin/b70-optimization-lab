// Host-only allocation tracer (research/tp/fault-ladder-2026-10-29). LD_PRELOAD into one engine process.
// Logs every malloc/calloc/realloc/aligned allocation and every anonymous mmap/mremap of at least ALLOC_TRACE_MIN bytes
// (default 256 KiB), and every free of a logged block, with a backtrace (glibc backtrace(), raw return addresses) and the
// calling thread's RUSAGE_THREAD minor-fault count. Inert unless ALLOC_TRACE_OUT is set and the program name is
// ALLOC_TRACE_PROG (default sc117-engine). No device API, no profiler, no memory setting; the real allocator is glibc's
// (__libc_* entry points), so nothing about allocation behaviour changes. /proc/self/maps is copied to OUT.maps at most
// once every 5 s while logging (and at exit) for offline symbolisation.
#define _GNU_SOURCE
#include <errno.h>
#include <execinfo.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

extern void* __libc_malloc(size_t);
extern void* __libc_calloc(size_t, size_t);
extern void* __libc_realloc(void*, size_t);
extern void* __libc_memalign(size_t, size_t);
extern void __libc_free(void*);
extern char* program_invocation_short_name;

static int fd = -1;
static size_t min_bytes = 256 * 1024;
static char maps_path[512];
static volatile long last_maps_s = 0;
static __thread int in_hook = 0;
#define TRACKED 8192
static void* volatile tracked[TRACKED];  // logged live blocks (pointer set; linear probe, lock-free enough for a log)

static long now_ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec * 1000000000L + t.tv_nsec; }
static void dump_maps(void) {
  int in = open("/proc/self/maps", O_RDONLY), out;
  if (in < 0) return;
  out = open(maps_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (out >= 0) { char b[65536]; ssize_t n; while ((n = read(in, b, sizeof b)) > 0) if (write(out, b, (size_t)n) < 0) break; close(out); }
  close(in);
}
static void track(void* p) { if (!p) return; size_t h = ((uintptr_t)p >> 12) % TRACKED; for (int i = 0; i < 64; ++i) { size_t k = (h + i) % TRACKED; if (!tracked[k]) { tracked[k] = p; return; } } }
static int untrack(void* p) { if (!p) return 0; size_t h = ((uintptr_t)p >> 12) % TRACKED; for (int i = 0; i < 64; ++i) { size_t k = (h + i) % TRACKED; if (tracked[k] == p) { tracked[k] = 0; return 1; } } return 0; }
static void logf_(const char* kind, size_t size, void* old, void* ptr) {
  if (fd < 0 || in_hook) return;
  in_hook = 1;
  char line[4096]; int n;
  struct rusage r; getrusage(RUSAGE_THREAD, &r);
  long t = now_ns();
  n = snprintf(line, sizeof line, "%ld %ld %s %zu %p %p %ld |", t, (long)syscall(SYS_gettid), kind, size, old, ptr, r.ru_minflt);
  void* frames[40]; int k = backtrace(frames, 40);
  for (int i = 1; i < k && n < (int)sizeof line - 24; ++i) n += snprintf(line + n, sizeof line - n, " %p", frames[i]);
  line[n++] = '\n';
  if (write(fd, line, (size_t)n) < 0) {}
  long s = t / 1000000000L;
  if (s - last_maps_s >= 5) { last_maps_s = s; dump_maps(); }
  in_hook = 0;
}
__attribute__((constructor)) static void init(void) {
  const char* out = getenv("ALLOC_TRACE_OUT"); const char* prog = getenv("ALLOC_TRACE_PROG"); const char* m = getenv("ALLOC_TRACE_MIN");
  if (!out || strcmp(program_invocation_short_name, prog ? prog : "sc117-engine") != 0) return;
  if (m) min_bytes = strtoull(m, 0, 10);
  char path[512]; snprintf(path, sizeof path, "%s.%d.log", out, (int)getpid()); snprintf(maps_path, sizeof maps_path, "%s.%d.maps", out, (int)getpid());
  void* warm[4]; in_hook = 1; backtrace(warm, 4); in_hook = 0;  // loads the unwinder before the first hooked call
  fd = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
  if (fd >= 0) { char b[256]; int n = snprintf(b, sizeof b, "# alloc_trace pid %d min %zu start_ns %ld\n", (int)getpid(), min_bytes, now_ns()); if (write(fd, b, (size_t)n) < 0) {} }
}
__attribute__((destructor)) static void fini(void) { if (fd >= 0) { dump_maps(); } }

void* malloc(size_t n) { void* p = __libc_malloc(n); if (fd >= 0 && n >= min_bytes && !in_hook) { logf_("malloc", n, 0, p); track(p); } return p; }
void* calloc(size_t a, size_t b) { void* p = __libc_calloc(a, b); size_t n = a * b; if (fd >= 0 && n >= min_bytes && !in_hook) { logf_("calloc", n, 0, p); track(p); } return p; }
void* realloc(void* o, size_t n) {
  int was = (fd >= 0 && o) ? untrack(o) : 0;
  void* p = __libc_realloc(o, n);
  if (fd >= 0 && !in_hook && (n >= min_bytes || was)) { logf_("realloc", n, o, p); if (n >= min_bytes) track(p); }
  return p;
}
void free(void* p) { if (fd >= 0 && p && !in_hook && untrack(p)) logf_("free", 0, p, 0); __libc_free(p); }
static void* aligned(size_t a, size_t n, const char* kind) { void* p = __libc_memalign(a, n); if (fd >= 0 && n >= min_bytes && !in_hook) { logf_(kind, n, 0, p); track(p); } return p; }
void* memalign(size_t a, size_t n) { return aligned(a, n, "memalign"); }
void* aligned_alloc(size_t a, size_t n) { return aligned(a, n, "aligned_alloc"); }
void* valloc(size_t n) { return aligned(4096, n, "valloc"); }
void* pvalloc(size_t n) { return aligned(4096, (n + 4095) & ~(size_t)4095, "pvalloc"); }
int posix_memalign(void** r, size_t a, size_t n) {
  if (a < sizeof(void*) || (a & (a - 1))) return EINVAL;
  void* p = __libc_memalign(a, n); if (!p && n) return ENOMEM; *r = p;
  if (fd >= 0 && n >= min_bytes && !in_hook) { logf_("posix_memalign", n, 0, p); track(p); }
  return 0;
}
void* mmap(void* a, size_t n, int prot, int flags, int f, off_t off) {
  void* p = (void*)syscall(SYS_mmap, a, n, prot, flags, f, off);
  if ((long)p < 0 && (long)p > -4096) { errno = -(int)(long)p; p = MAP_FAILED; }
  if (fd >= 0 && n >= min_bytes && p != MAP_FAILED && !in_hook) logf_((flags & MAP_ANONYMOUS) ? "mmap-anon" : "mmap-file", n, a, p);
  return p;
}
void* mmap64(void* a, size_t n, int prot, int flags, int f, off_t off) __attribute__((alias("mmap")));
void* mremap(void* o, size_t on, size_t n, int flags, ...) {
  void* na = 0; if (flags & MREMAP_FIXED) { va_list ap; va_start(ap, flags); na = va_arg(ap, void*); va_end(ap); }
  void* p = (void*)syscall(SYS_mremap, o, on, n, flags, na);
  if ((long)p < 0 && (long)p > -4096) { errno = -(int)(long)p; p = MAP_FAILED; }
  if (fd >= 0 && n >= min_bytes && p != MAP_FAILED && !in_hook) logf_("mremap", n, o, p);
  return p;
}
