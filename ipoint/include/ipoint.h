/*
 * ipoint.h - instrumentation points (IPoints) for unit-level execution-time
 * measurement of C/C++ programs on x86-64 Linux.
 *
 * Build-time mode (exactly one; OFF when none is given):
 *   -DIPOINT_MODE_TIMING    IPOINT(id) appends (timestamp, id, core) to a
 *                           thread-local buffer.
 *   -DIPOINT_MODE_COVERAGE  IPOINT(id) increments a thread-local hit counter.
 *   -DIPOINT_MODE_OFF       IPOINT(id) expands to nothing (uninstrumented
 *                           baseline; the helper functions still exist).
 *
 * Timestamp implementation for TIMING (default IPOINT_TS_RDTSCP_LFENCE):
 *   -DIPOINT_TS_IMPL=IPOINT_TS_RDTSCP_LFENCE        rdtscp; lfence
 *   -DIPOINT_TS_IMPL=IPOINT_TS_LFENCE_RDTSC_LFENCE  lfence; rdtsc; lfence
 *   -DIPOINT_TS_IMPL=IPOINT_TS_CPUID_RDTSC          cpuid; rdtsc
 *   -DIPOINT_TS_IMPL=IPOINT_TS_CLOCK_GETTIME_RAW    clock_gettime(CLOCK_MONOTONIC_RAW)
 *
 * Two ways of driving the buffers:
 *
 * 1. Harness mode (bench_main.c): the single thread calls ipoint_thread_init(),
 *    ipoint_run_begin()/ipoint_run_end() around every run and ipoint_flush(fp).
 *
 * 2. Job mode (long-running multi-threaded processes such as ROS 2 nodes):
 *    the instrumenter marks one function as the job and emits
 *    IPOINT_JOB_BEGIN(id) at its entry and IPOINT_JOB_END(id) at every exit.
 *    Each job invocation becomes one run (run index = process-wide invocation
 *    counter, seed field = thread id). A thread initializes its buffer lazily
 *    on its first probe and, when the environment variable IPOINT_OUT_DIR is
 *    set, appends its records to IPOINT_OUT_DIR/<tag>_<pid>_<tid>.bin with
 *    write(2) at every JOB_END (outside the measured interval; the high-water
 *    mark only forces a flush inside a job whose records exceed the buffer).
 *    IPOINT_OUT_DIR/<tag>_<pid>.meta.json (TSC calibration pairs, per-thread
 *    record counts, overflow counters) is rewritten every
 *    IPOINT_META_EVERY_JOBS jobs of the process. Nothing is done at process
 *    exit: an exit handler would touch the buffers of threads that may still
 *    run (and stdio during exit hangs multi-threaded ROS 2 containers), so a
 *    process loses at most the job being recorded when it stops.
 *    ipoint_flush_all() exists for programs that can call it once every
 *    thread is idle. Environment: IPOINT_OUT_DIR (required for file output),
 *    IPOINT_TAG (file prefix, default /proc/self/comm), IPOINT_BUF_RECORDS
 *    (per-thread buffer, default 1<<20), IPOINT_HIGH_WATER (records, default
 *    1024 = 16 KiB).
 *
 * The per-thread state is defined in exactly one translation unit that
 * defines IPOINT_IMPLEMENTATION before including this header.
 */
#ifndef IPOINT_H
#define IPOINT_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(IPOINT_MODE_TIMING) && (defined(IPOINT_MODE_COVERAGE) || defined(IPOINT_MODE_OFF))
#error "IPOINT_MODE_* macros are mutually exclusive"
#endif
#if defined(IPOINT_MODE_COVERAGE) && defined(IPOINT_MODE_OFF)
#error "IPOINT_MODE_* macros are mutually exclusive"
#endif
#if !defined(IPOINT_MODE_TIMING) && !defined(IPOINT_MODE_COVERAGE) && !defined(IPOINT_MODE_OFF)
#define IPOINT_MODE_OFF 1
#endif

#define IPOINT_TS_RDTSCP_LFENCE 1
#define IPOINT_TS_LFENCE_RDTSC_LFENCE 2
#define IPOINT_TS_CPUID_RDTSC 3
#define IPOINT_TS_CLOCK_GETTIME_RAW 4
#ifndef IPOINT_TS_IMPL
#define IPOINT_TS_IMPL IPOINT_TS_RDTSCP_LFENCE
#endif

#ifndef IPOINT_MAX_ID
#define IPOINT_MAX_ID 4096u
#endif
#ifndef IPOINT_MAX_THREADS
#define IPOINT_MAX_THREADS 256
#endif
#ifndef IPOINT_DEFAULT_BUF_RECORDS
#define IPOINT_DEFAULT_BUF_RECORDS (1u << 20)
#endif
#ifndef IPOINT_DEFAULT_HIGH_WATER
#define IPOINT_DEFAULT_HIGH_WATER 1024u /* records (16 KiB): a stopped process loses at most this much per thread */
#endif
#ifndef IPOINT_META_EVERY_JOBS
#define IPOINT_META_EVERY_JOBS 16u
#endif

#define IPOINT_ID_RUN_BEGIN 0xFFFFFFF0u /* ts = run index */
#define IPOINT_ID_RUN_SEED 0xFFFFFFF1u  /* ts = seed (job mode: thread id) */
#define IPOINT_ID_RUN_END 0xFFFFFFF2u   /* ts = timestamp */

#ifdef __cplusplus
#define IPOINT_TLS thread_local
extern "C" {
#else
#define IPOINT_TLS _Thread_local
#endif

typedef struct ipoint_rec {
  uint64_t ts;
  uint32_t id;
  uint32_t aux;
} ipoint_rec_t;

typedef struct ipoint_state {
  ipoint_rec_t *buf;
  size_t pos;
  size_t cap;
  uint64_t overflow;
  uint32_t *hits; /* IPOINT_MAX_ID + 1 counters */
  /* job mode */
  int fd;                /* per-thread output file (write(2)), opened at the first flush; 0 = none */
  uint64_t written;      /* records written to fp */
  uint64_t flush_in_job; /* synchronous flushes forced by a full buffer */
  uint64_t jobs;         /* job invocations recorded by this thread */
  uint64_t last_run;     /* process-wide index of the job being recorded */
  uint64_t tid;
  size_t high_water;
  int registered;
} ipoint_state_t;

/* Per-thread state: heap-allocated on first use and never freed, so that the
 * registry used by ipoint_flush_all() stays valid after a thread has exited.
 * The thread-local variable only holds the pointer. */
extern IPOINT_TLS ipoint_state_t *ipoint_tls;

/* ---- timestamp ------------------------------------------------------- */

static inline __attribute__((always_inline)) uint64_t ipoint_now(uint32_t *aux) {
#if IPOINT_TS_IMPL == IPOINT_TS_RDTSCP_LFENCE
  uint32_t lo, hi, a;
  __asm__ __volatile__("rdtscp\n\tlfence" : "=a"(lo), "=d"(hi), "=c"(a) : : "memory");
  if (aux) *aux = a;
  return ((uint64_t)hi << 32) | lo;
#elif IPOINT_TS_IMPL == IPOINT_TS_LFENCE_RDTSC_LFENCE
  uint32_t lo, hi;
  __asm__ __volatile__("lfence\n\trdtsc\n\tlfence" : "=a"(lo), "=d"(hi) : : "memory");
  if (aux) *aux = 0;
  return ((uint64_t)hi << 32) | lo;
#elif IPOINT_TS_IMPL == IPOINT_TS_CPUID_RDTSC
  uint32_t lo, hi;
  __asm__ __volatile__("xorl %%eax, %%eax\n\tcpuid\n\trdtsc"
                       : "=a"(lo), "=d"(hi)
                       :
                       : "rbx", "rcx", "memory");
  if (aux) *aux = 0;
  return ((uint64_t)hi << 32) | lo;
#elif IPOINT_TS_IMPL == IPOINT_TS_CLOCK_GETTIME_RAW
  struct timespec t;
  __asm__ __volatile__("" : : : "memory");
  clock_gettime(CLOCK_MONOTONIC_RAW, &t);
  __asm__ __volatile__("" : : : "memory");
  if (aux) *aux = 0;
  return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
#else
#error "unknown IPOINT_TS_IMPL"
#endif
}

/* ---- probe ----------------------------------------------------------- */

/* Slow path of ipoint_probe: the buffer is unallocated (lazy per-thread
 * initialization in job mode) or full (synchronous flush when a file is
 * attached, otherwise the record is dropped and counted). */
void ipoint_probe_slow(uint64_t ts, uint32_t id, uint32_t aux);

/* always_inline: the timestamp must be taken at the probe site even at -O3, where the
 * compiler would otherwise outline this function once per library */
static inline __attribute__((always_inline)) void ipoint_probe(uint32_t id) {
  uint32_t aux;
  uint64_t ts = ipoint_now(&aux);
  ipoint_state_t *s = ipoint_tls;
  if (s != NULL && s->pos < s->cap) {
    ipoint_rec_t *r = &s->buf[s->pos];
    r->ts = ts;
    r->id = id;
    r->aux = aux;
    s->pos++;
  } else {
    ipoint_probe_slow(ts, id, aux);
  }
}

static inline void ipoint_hit(uint32_t id) {
  __asm__ __volatile__("" : : : "memory");
  ipoint_state_t *s = ipoint_tls;
  if (s != NULL && s->hits && id <= IPOINT_MAX_ID) s->hits[id]++;
  __asm__ __volatile__("" : : : "memory");
}

void ipoint_job_begin(void);
void ipoint_job_end(void);

#if defined(IPOINT_MODE_TIMING)
#define IPOINT(id) ipoint_probe((uint32_t)(id))
#define IPOINT_JOB_BEGIN(id) do { ipoint_job_begin(); ipoint_probe((uint32_t)(id)); } while (0)
#define IPOINT_JOB_END(id) do { ipoint_probe((uint32_t)(id)); ipoint_job_end(); } while (0)
#define IPOINT_MODE_NAME "timing"
#elif defined(IPOINT_MODE_COVERAGE)
#define IPOINT(id) ipoint_hit((uint32_t)(id))
#define IPOINT_JOB_BEGIN(id) ipoint_hit((uint32_t)(id))
#define IPOINT_JOB_END(id) ipoint_hit((uint32_t)(id))
#define IPOINT_MODE_NAME "coverage"
#else
#define IPOINT(id) ((void)0)
#define IPOINT_JOB_BEGIN(id) ((void)0)
#define IPOINT_JOB_END(id) ((void)0)
#define IPOINT_MODE_NAME "off"
#endif

#if IPOINT_TS_IMPL == IPOINT_TS_RDTSCP_LFENCE
#define IPOINT_TS_NAME "rdtscp_lfence"
#elif IPOINT_TS_IMPL == IPOINT_TS_LFENCE_RDTSC_LFENCE
#define IPOINT_TS_NAME "lfence_rdtsc_lfence"
#elif IPOINT_TS_IMPL == IPOINT_TS_CPUID_RDTSC
#define IPOINT_TS_NAME "cpuid_rdtsc"
#else
#define IPOINT_TS_NAME "clock_gettime_raw"
#endif

/* ---- per-thread buffer management ------------------------------------ */

int ipoint_thread_init(size_t cap_records);
void ipoint_thread_free(void);
void ipoint_reset(void);
void ipoint_run_begin(uint64_t run_idx, uint64_t seed);
void ipoint_run_end(void);
size_t ipoint_count(void);
const ipoint_rec_t *ipoint_records(void);
uint64_t ipoint_overflow(void);
size_t ipoint_flush(FILE *fp);
int ipoint_first_last(uint32_t entry_id, uint32_t exit_id, uint64_t *t0, uint64_t *t1);
void ipoint_histogram(uint32_t *hist, uint32_t max_id);
void ipoint_hits_copy_and_clear(uint32_t *hist, uint32_t max_id);

/* ---- job mode (file output) ------------------------------------------- */

size_t ipoint_flush_thread(void); /* this thread's buffer -> its file */
void ipoint_flush_all(void);      /* every registered thread; call when they are idle */
uint64_t ipoint_job_count(void);  /* process-wide job invocations so far */

/* ---- calibration / environment --------------------------------------- */

double ipoint_calibrate_tsc_hz(double seconds);
unsigned ipoint_cpu_flags(void); /* bit0 constant_tsc, bit1 nonstop_tsc, bit2 rdtscp */
int ipoint_current_cpu(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

/* ====================================================================== */
#ifdef IPOINT_IMPLEMENTATION

#include <fcntl.h>
#include <pthread.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#ifdef __cplusplus
extern "C" {
#endif

IPOINT_TLS ipoint_state_t *ipoint_tls = NULL;

static ipoint_state_t *ipoint_state_get(void) {
  if (ipoint_tls == NULL) ipoint_tls = (ipoint_state_t *)calloc(1, sizeof(ipoint_state_t));
  return ipoint_tls;
}

/* process-wide job-mode state */
static pthread_mutex_t ipoint_mu = PTHREAD_MUTEX_INITIALIZER;
static ipoint_state_t *ipoint_registry[IPOINT_MAX_THREADS];
static size_t ipoint_registry_n = 0;
static uint64_t ipoint_registry_dropped = 0;
static uint64_t ipoint_job_counter = 0;
static int ipoint_process_ready = 0;
static int ipoint_file_output = 0;
static char ipoint_out_dir[512];
static char ipoint_tag[128];
static size_t ipoint_buf_records = IPOINT_DEFAULT_BUF_RECORDS;
static size_t ipoint_high_water = 0;
static uint64_t ipoint_t0_mono_ns, ipoint_t0_tsc, ipoint_t1_mono_ns, ipoint_t1_tsc;
static double ipoint_tsc_hz_short = 0.0;

static uint64_t ipoint_raw_tsc(void) {
  uint32_t lo, hi;
  __asm__ __volatile__("rdtscp" : "=a"(lo), "=d"(hi) : : "rcx", "memory");
  return ((uint64_t)hi << 32) | lo;
}

static uint64_t ipoint_mono_ns(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC_RAW, &t);
  return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}

static void ipoint_read_comm(char *out, size_t n) {
  FILE *f = fopen("/proc/self/comm", "r");
  size_t k = 0;
  out[0] = 0;
  if (!f) return;
  if (fgets(out, (int)n, f)) {
    k = strlen(out);
    while (k && (out[k - 1] == '\n' || out[k - 1] == ' ')) out[--k] = 0;
  }
  fclose(f);
}

static void ipoint_write_meta(void);
static unsigned ipoint_cpu_flags_value = 0xFFFFFFFFu;
static unsigned ipoint_cpu_flags_cached(void) {
  if (ipoint_cpu_flags_value == 0xFFFFFFFFu) ipoint_cpu_flags_value = ipoint_cpu_flags();
  return ipoint_cpu_flags_value;
}

/* Called once per process (under ipoint_mu) before the first buffer is used. */
static void ipoint_process_init_locked(void) {
  const char *e;
  if (ipoint_process_ready) return;
  ipoint_process_ready = 1;
  e = getenv("IPOINT_OUT_DIR");
  if (e && *e) {
    snprintf(ipoint_out_dir, sizeof ipoint_out_dir, "%s", e);
    ipoint_file_output = 1;
  }
  e = getenv("IPOINT_TAG");
  if (e && *e) snprintf(ipoint_tag, sizeof ipoint_tag, "%s", e);
  else ipoint_read_comm(ipoint_tag, sizeof ipoint_tag);
  if (!ipoint_tag[0]) snprintf(ipoint_tag, sizeof ipoint_tag, "proc");
  e = getenv("IPOINT_BUF_RECORDS");
  if (e && *e) ipoint_buf_records = (size_t)strtoull(e, NULL, 10);
  if (ipoint_buf_records < 1024) ipoint_buf_records = 1024;
  e = getenv("IPOINT_HIGH_WATER");
  ipoint_high_water = (e && *e) ? (size_t)strtoull(e, NULL, 10) : IPOINT_DEFAULT_HIGH_WATER;
  if (ipoint_high_water >= ipoint_buf_records) ipoint_high_water = ipoint_buf_records / 2;
  ipoint_t0_mono_ns = ipoint_mono_ns();
  ipoint_t0_tsc = ipoint_raw_tsc();
  if (ipoint_file_output) ipoint_tsc_hz_short = ipoint_calibrate_tsc_hz(0.02);
}

/* write(2) loop: no stdio locks, safe while other threads exit */
static void ipoint_write_fd(int fd, const void *p, size_t n) {
  const char *c = (const char *)p;
  while (n) {
    ssize_t w = write(fd, c, n);
    if (w <= 0) return;
    c += w;
    n -= (size_t)w;
  }
}

static void ipoint_register_locked(ipoint_state_t *s) {
  if (s->registered) return;
  s->registered = 1;
  s->tid = (uint64_t)syscall(SYS_gettid);
  if (ipoint_registry_n < IPOINT_MAX_THREADS) ipoint_registry[ipoint_registry_n++] = s;
  else ipoint_registry_dropped++;
}

int ipoint_thread_init(size_t cap_records) {
  ipoint_state_t *s = ipoint_state_get();
  if (s == NULL) return -1;
  ipoint_thread_free();
  s->buf = (ipoint_rec_t *)calloc(cap_records ? cap_records : 1, sizeof(ipoint_rec_t));
  s->hits = (uint32_t *)calloc(IPOINT_MAX_ID + 1, sizeof(uint32_t));
  if (!s->buf || !s->hits) {
    ipoint_thread_free();
    return -1;
  }
  s->cap = cap_records;
  s->pos = 0;
  s->overflow = 0;
  pthread_mutex_lock(&ipoint_mu);
  ipoint_process_init_locked();
  s->high_water = ipoint_high_water < cap_records ? ipoint_high_water : cap_records / 2;
  ipoint_register_locked(s);
  pthread_mutex_unlock(&ipoint_mu);
  return 0;
}

void ipoint_thread_free(void) {
  ipoint_state_t *s = ipoint_tls;
  if (s == NULL) return;
  free(s->buf);
  free(s->hits);
  s->buf = NULL;
  s->hits = NULL;
  s->cap = 0;
  s->pos = 0;
  s->overflow = 0;
}

void ipoint_reset(void) {
  ipoint_state_t *s = ipoint_tls;
  if (s == NULL) return;
  s->pos = 0;
  s->overflow = 0;
}

static __attribute__((unused)) void ipoint_push_raw(uint64_t ts, uint32_t id, uint32_t aux) {
  ipoint_state_t *s = ipoint_tls;
  if (s != NULL && s->pos < s->cap) {
    s->buf[s->pos].ts = ts;
    s->buf[s->pos].id = id;
    s->buf[s->pos].aux = aux;
    s->pos++;
  } else {
    ipoint_probe_slow(ts, id, aux);
  }
}

static int ipoint_open_thread_file(ipoint_state_t *s) {
  char path[768];
  if (s->fd > 0) return 1;
  if (!ipoint_file_output) return 0;
  snprintf(path, sizeof path, "%s/%s_%ld_%llu.bin", ipoint_out_dir, ipoint_tag, (long)getpid(),
           (unsigned long long)s->tid);
  s->fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
  return s->fd > 0;
}

static void ipoint_flush_state(ipoint_state_t *s) {
  if (!s->pos) return;
  if (ipoint_open_thread_file(s)) {
    ipoint_write_fd(s->fd, s->buf, s->pos * sizeof(ipoint_rec_t));
    s->written += s->pos;
  } else {
    s->overflow += s->pos;
  }
  s->pos = 0;
}

size_t ipoint_flush_thread(void) {
  ipoint_state_t *s = ipoint_tls;
  size_t n;
  if (s == NULL || !s->pos) return 0;
  n = s->pos;
  ipoint_flush_state(s);
  return n;
}

void ipoint_probe_slow(uint64_t ts, uint32_t id, uint32_t aux) {
  ipoint_state_t *s = ipoint_state_get();
  if (s == NULL) return;
  if (s->cap == 0) {
    /* lazy initialization of a thread that never called ipoint_thread_init */
    pthread_mutex_lock(&ipoint_mu);
    ipoint_process_init_locked();
    pthread_mutex_unlock(&ipoint_mu);
    if (ipoint_thread_init(ipoint_buf_records) != 0) {
      s->overflow++;
      return;
    }
  } else if (ipoint_file_output) {
    /* full inside a job: write synchronously (counted, it lands in the measured interval) */
    s->flush_in_job++;
    ipoint_flush_thread();
  } else {
    s->overflow++;
    return;
  }
  if (s->pos < s->cap) {
    s->buf[s->pos].ts = ts;
    s->buf[s->pos].id = id;
    s->buf[s->pos].aux = aux;
    s->pos++;
  } else {
    s->overflow++;
  }
}

void ipoint_run_begin(uint64_t run_idx, uint64_t seed) {
#if defined(IPOINT_MODE_TIMING)
  ipoint_push_raw(run_idx, IPOINT_ID_RUN_BEGIN, 0);
  ipoint_push_raw(seed, IPOINT_ID_RUN_SEED, 0);
#else
  (void)run_idx;
  (void)seed;
#endif
}

void ipoint_run_end(void) {
#if defined(IPOINT_MODE_TIMING)
  uint32_t aux;
  uint64_t ts = ipoint_now(&aux);
  ipoint_push_raw(ts, IPOINT_ID_RUN_END, aux);
#endif
}

/* meta.json is rewritten every IPOINT_META_EVERY_JOBS jobs of a thread (outside the
 * measured interval), so that a process killed at shutdown still leaves one */
static __attribute__((unused)) void ipoint_meta_tick(void) {
  pthread_mutex_lock(&ipoint_mu);
  ipoint_t1_mono_ns = ipoint_mono_ns();
  ipoint_t1_tsc = ipoint_raw_tsc();
  ipoint_write_meta();
  pthread_mutex_unlock(&ipoint_mu);
}

void ipoint_job_begin(void) {
#if defined(IPOINT_MODE_TIMING)
  ipoint_state_t *s = ipoint_state_get();
  uint64_t run;
  if (s == NULL) return;
  if (s->cap == 0) {
    uint32_t aux = 0;
    /* force the lazy initialization before the sentinels are written */
    ipoint_probe_slow(ipoint_now(&aux), IPOINT_ID_RUN_END, aux);
    s->pos = 0;
  }
  run = __atomic_fetch_add(&ipoint_job_counter, 1, __ATOMIC_RELAXED);
  s->jobs++;
  s->last_run = run;
  ipoint_push_raw(run, IPOINT_ID_RUN_BEGIN, 0);
  ipoint_push_raw(s->tid, IPOINT_ID_RUN_SEED, 0);
#endif
}

void ipoint_job_end(void) {
#if defined(IPOINT_MODE_TIMING)
  ipoint_state_t *s = ipoint_tls;
  if (s == NULL) return;
  ipoint_run_end();
  if (ipoint_file_output) {
    /* every job is written out immediately (outside the measured interval): a
     * callback that runs on a different executor thread each time would
     * otherwise never fill a per-thread buffer, and nothing is flushed at exit */
    ipoint_flush_thread();
    if (s->last_run % IPOINT_META_EVERY_JOBS == 0) ipoint_meta_tick();
  }
#endif
}

uint64_t ipoint_job_count(void) { return __atomic_load_n(&ipoint_job_counter, __ATOMIC_RELAXED); }

/* Flush every registered thread's buffer. Only safe when no other thread is
 * recording (e.g. after all worker threads were joined). */
void ipoint_flush_all(void) {
  size_t i;
  pthread_mutex_lock(&ipoint_mu);
  ipoint_t1_mono_ns = ipoint_mono_ns();
  ipoint_t1_tsc = ipoint_raw_tsc();
  if (ipoint_file_output) {
    for (i = 0; i < ipoint_registry_n; i++) ipoint_flush_state(ipoint_registry[i]);
    ipoint_write_meta();
  }
  pthread_mutex_unlock(&ipoint_mu);
}

/* Called with ipoint_mu held. Builds the JSON in a static buffer and writes it
 * with open/write/close (no stdio). The per-thread counters of other threads
 * are read racily; they are statistics only. */
static void ipoint_write_meta(void) {
  static char body[16384];
  char path[768];
  int fd, n = 0;
  size_t i;
  uint64_t jobs = 0;
  unsigned flags = ipoint_cpu_flags_cached();
  double hz = ipoint_tsc_hz_short;
  if (ipoint_t1_mono_ns > ipoint_t0_mono_ns)
    hz = (double)(ipoint_t1_tsc - ipoint_t0_tsc) * 1e9 / (double)(ipoint_t1_mono_ns - ipoint_t0_mono_ns);
  n += snprintf(body + n, sizeof body - (size_t)n,
                "{\n \"pid\": %ld,\n \"tag\": \"%s\",\n \"mode\": \"%s\",\n \"ts_impl\": \"%s\",\n"
                " \"cpu_flags\": %u,\n \"buf_records\": %zu,\n \"high_water\": %zu,\n \"tsc_hz_short\": %.3f,\n"
                " \"t0_mono_ns\": %llu,\n \"t0_tsc\": %llu,\n \"t1_mono_ns\": %llu,\n \"t1_tsc\": %llu,\n"
                " \"tsc_hz\": %.3f,\n \"sentinels\": {\"run_begin\": %u, \"run_seed\": %u, \"run_end\": %u},\n"
                " \"registry_dropped\": %llu,\n \"threads\": [\n",
                (long)getpid(), ipoint_tag, IPOINT_MODE_NAME, IPOINT_TS_NAME, flags, ipoint_buf_records,
                ipoint_high_water, ipoint_tsc_hz_short, (unsigned long long)ipoint_t0_mono_ns,
                (unsigned long long)ipoint_t0_tsc, (unsigned long long)ipoint_t1_mono_ns,
                (unsigned long long)ipoint_t1_tsc, hz, IPOINT_ID_RUN_BEGIN, IPOINT_ID_RUN_SEED, IPOINT_ID_RUN_END,
                (unsigned long long)ipoint_registry_dropped);
  for (i = 0; i < ipoint_registry_n && n < (int)sizeof body - 256; i++) {
    ipoint_state_t *s = ipoint_registry[i];
    jobs += s->jobs;
    n += snprintf(body + n, sizeof body - (size_t)n,
                  "  {\"tid\": %llu, \"file\": \"%s_%ld_%llu.bin\", \"records\": %llu, \"overflow\": %llu, "
                  "\"flush_in_job\": %llu, \"jobs\": %llu}%s\n",
                  (unsigned long long)s->tid, ipoint_tag, (long)getpid(), (unsigned long long)s->tid,
                  (unsigned long long)s->written, (unsigned long long)s->overflow,
                  (unsigned long long)s->flush_in_job, (unsigned long long)s->jobs,
                  i + 1 < ipoint_registry_n ? "," : "");
  }
  n += snprintf(body + n, sizeof body - (size_t)n, " ],\n \"jobs_total\": %llu\n}\n", (unsigned long long)jobs);
  if (n <= 0 || n >= (int)sizeof body) return;
  snprintf(path, sizeof path, "%s/%s_%ld.meta.json", ipoint_out_dir, ipoint_tag, (long)getpid());
  fd = open(path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
  if (fd < 0) return;
  ipoint_write_fd(fd, body, (size_t)n);
  close(fd);
}

size_t ipoint_count(void) { return ipoint_tls ? ipoint_tls->pos : 0; }
const ipoint_rec_t *ipoint_records(void) { return ipoint_tls ? ipoint_tls->buf : NULL; }
uint64_t ipoint_overflow(void) { return ipoint_tls ? ipoint_tls->overflow : 0; }

size_t ipoint_flush(FILE *fp) {
  ipoint_state_t *s = ipoint_tls;
  size_t n = 0;
  if (s == NULL) return 0;
  if (fp && s->pos) n = fwrite(s->buf, sizeof(ipoint_rec_t), s->pos, fp);
  s->pos = 0;
  return n;
}

int ipoint_first_last(uint32_t entry_id, uint32_t exit_id, uint64_t *t0, uint64_t *t1) {
  ipoint_state_t *s = ipoint_tls;
  size_t i;
  int have0 = 0, have1 = 0;
  if (s == NULL) return 0;
  for (i = 0; i < s->pos; i++) {
    uint32_t id = s->buf[i].id;
    if (!have0 && id == entry_id) {
      *t0 = s->buf[i].ts;
      have0 = 1;
    }
    if (id == exit_id) {
      *t1 = s->buf[i].ts;
      have1 = 1;
    }
  }
  return have0 && have1;
}

void ipoint_histogram(uint32_t *hist, uint32_t max_id) {
  ipoint_state_t *s = ipoint_tls;
  size_t i;
  memset(hist, 0, sizeof(uint32_t) * (max_id + 1));
  if (s == NULL) return;
  for (i = 0; i < s->pos; i++) {
    uint32_t id = s->buf[i].id;
    if (id <= max_id) hist[id]++;
  }
}

void ipoint_hits_copy_and_clear(uint32_t *hist, uint32_t max_id) {
  ipoint_state_t *s = ipoint_tls;
  uint32_t n = max_id < IPOINT_MAX_ID ? max_id : IPOINT_MAX_ID;
  if (s == NULL || !s->hits) {
    memset(hist, 0, sizeof(uint32_t) * (max_id + 1));
    return;
  }
  memcpy(hist, s->hits, sizeof(uint32_t) * (n + 1));
  memset(s->hits, 0, sizeof(uint32_t) * (IPOINT_MAX_ID + 1));
}

double ipoint_calibrate_tsc_hz(double seconds) {
  struct timespec a, b;
  uint64_t ta, tb;
  double dt;
  clock_gettime(CLOCK_MONOTONIC_RAW, &a);
  ta = ipoint_raw_tsc();
  do {
    clock_gettime(CLOCK_MONOTONIC_RAW, &b);
    dt = (double)(b.tv_sec - a.tv_sec) + (double)(b.tv_nsec - a.tv_nsec) * 1e-9;
  } while (dt < seconds);
  tb = ipoint_raw_tsc();
  return (double)(tb - ta) / dt;
}

unsigned ipoint_cpu_flags(void) {
  unsigned flags = 0;
  FILE *f = fopen("/proc/cpuinfo", "r");
  char line[4096];
  if (!f) return 0;
  while (fgets(line, sizeof line, f)) {
    if (strncmp(line, "flags", 5) == 0) {
      if (strstr(line, " constant_tsc")) flags |= 1u;
      if (strstr(line, " nonstop_tsc")) flags |= 2u;
      if (strstr(line, " rdtscp")) flags |= 4u;
      break;
    }
  }
  fclose(f);
  return flags;
}

/* IA32_TSC_AUX as set by Linux: bits 0-11 = cpu, bits 12-19 = node */
int ipoint_current_cpu(void) {
  uint32_t lo, hi, aux;
  __asm__ __volatile__("rdtscp" : "=a"(lo), "=d"(hi), "=c"(aux) : : "memory");
  (void)lo;
  (void)hi;
  return (int)(aux & 0xFFFu);
}

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* IPOINT_IMPLEMENTATION */
#endif /* IPOINT_H */
