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

#define IPOINT_ID_RUN_BEGIN 0xFFFFFFF0u /* ts = run index */
#define IPOINT_ID_RUN_SEED 0xFFFFFFF1u  /* ts = seed */
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
} ipoint_state_t;

extern IPOINT_TLS ipoint_state_t ipoint_tls;

/* ---- timestamp ------------------------------------------------------- */

static inline uint64_t ipoint_now(uint32_t *aux) {
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

static inline void ipoint_probe(uint32_t id) {
  uint32_t aux;
  uint64_t ts = ipoint_now(&aux);
  ipoint_state_t *s = &ipoint_tls;
  size_t pos = s->pos;
  if (pos < s->cap) {
    ipoint_rec_t *r = &s->buf[pos];
    r->ts = ts;
    r->id = id;
    r->aux = aux;
    s->pos = pos + 1;
  } else {
    s->overflow++;
  }
}

static inline void ipoint_hit(uint32_t id) {
  __asm__ __volatile__("" : : : "memory");
  ipoint_state_t *s = &ipoint_tls;
  if (s->hits && id <= IPOINT_MAX_ID) s->hits[id]++;
  __asm__ __volatile__("" : : : "memory");
}

#if defined(IPOINT_MODE_TIMING)
#define IPOINT(id) ipoint_probe((uint32_t)(id))
#define IPOINT_MODE_NAME "timing"
#elif defined(IPOINT_MODE_COVERAGE)
#define IPOINT(id) ipoint_hit((uint32_t)(id))
#define IPOINT_MODE_NAME "coverage"
#else
#define IPOINT(id) ((void)0)
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

/* ---- calibration / environment --------------------------------------- */

double ipoint_calibrate_tsc_hz(double seconds);
unsigned ipoint_cpu_flags(void); /* bit0 constant_tsc, bit1 nonstop_tsc, bit2 rdtscp */
int ipoint_current_cpu(void);

#ifdef __cplusplus
} /* extern "C" */
#endif

/* ====================================================================== */
#ifdef IPOINT_IMPLEMENTATION

IPOINT_TLS ipoint_state_t ipoint_tls = {NULL, 0, 0, 0, NULL};

int ipoint_thread_init(size_t cap_records) {
  ipoint_state_t *s = &ipoint_tls;
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
  return 0;
}

void ipoint_thread_free(void) {
  ipoint_state_t *s = &ipoint_tls;
  free(s->buf);
  free(s->hits);
  s->buf = NULL;
  s->hits = NULL;
  s->cap = 0;
  s->pos = 0;
  s->overflow = 0;
}

void ipoint_reset(void) {
  ipoint_tls.pos = 0;
  ipoint_tls.overflow = 0;
}

static __attribute__((unused)) void ipoint_push_raw(uint64_t ts, uint32_t id, uint32_t aux) {
  ipoint_state_t *s = &ipoint_tls;
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

size_t ipoint_count(void) { return ipoint_tls.pos; }
const ipoint_rec_t *ipoint_records(void) { return ipoint_tls.buf; }
uint64_t ipoint_overflow(void) { return ipoint_tls.overflow; }

size_t ipoint_flush(FILE *fp) {
  ipoint_state_t *s = &ipoint_tls;
  size_t n = 0;
  if (fp && s->pos) n = fwrite(s->buf, sizeof(ipoint_rec_t), s->pos, fp);
  s->pos = 0;
  return n;
}

int ipoint_first_last(uint32_t entry_id, uint32_t exit_id, uint64_t *t0, uint64_t *t1) {
  ipoint_state_t *s = &ipoint_tls;
  size_t i;
  int have0 = 0, have1 = 0;
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
  ipoint_state_t *s = &ipoint_tls;
  size_t i;
  memset(hist, 0, sizeof(uint32_t) * (max_id + 1));
  for (i = 0; i < s->pos; i++) {
    uint32_t id = s->buf[i].id;
    if (id <= max_id) hist[id]++;
  }
}

void ipoint_hits_copy_and_clear(uint32_t *hist, uint32_t max_id) {
  ipoint_state_t *s = &ipoint_tls;
  uint32_t n = max_id < IPOINT_MAX_ID ? max_id : IPOINT_MAX_ID;
  if (!s->hits) {
    memset(hist, 0, sizeof(uint32_t) * (max_id + 1));
    return;
  }
  memcpy(hist, s->hits, sizeof(uint32_t) * (n + 1));
  memset(s->hits, 0, sizeof(uint32_t) * (IPOINT_MAX_ID + 1));
}

static uint64_t ipoint_raw_tsc(void) {
  uint32_t lo, hi;
  __asm__ __volatile__("rdtscp" : "=a"(lo), "=d"(hi) : : "rcx", "memory");
  return ((uint64_t)hi << 32) | lo;
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

#endif /* IPOINT_IMPLEMENTATION */
#endif /* IPOINT_H */
