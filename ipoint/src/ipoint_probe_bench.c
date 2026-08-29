/*
 * ipoint_probe_bench - cost of one IPoint and TSC calibration.
 *
 * Build once per timestamp implementation, e.g.
 *   gcc -O2 -DIPOINT_MODE_TIMING -DIPOINT_TS_IMPL=IPOINT_TS_RDTSCP_LFENCE \
 *       -I../include ipoint_probe_bench.c -o ipoint_probe_bench_rdtscp_lfence
 *
 * Usage: ipoint_probe_bench [--pairs N] [--calib SECONDS] [--core C] [--json]
 *
 * The probe cost is the distance between two back-to-back IPoints, which is
 * the smallest interval the instrumentation can report. It is measured
 * N times and summarised as min / median / p99 / p99.9 / max.
 */
#define _GNU_SOURCE
#define IPOINT_IMPLEMENTATION
#include "ipoint.h"

#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int cmp_u64(const void *a, const void *b) {
  uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
  return x < y ? -1 : x > y;
}

static uint64_t quantile(const uint64_t *v, size_t n, double q) {
  size_t i = (size_t)(q * (double)(n - 1));
  return v[i];
}

int main(int argc, char **argv) {
  size_t pairs = 1000000;
  double calib = 1.0;
  int core = -1, json = 0;
  size_t i;
  for (i = 1; i < (size_t)argc; i++) {
    if (!strcmp(argv[i], "--pairs") && i + 1 < (size_t)argc) pairs = strtoull(argv[++i], NULL, 10);
    else if (!strcmp(argv[i], "--calib") && i + 1 < (size_t)argc) calib = atof(argv[++i]);
    else if (!strcmp(argv[i], "--core") && i + 1 < (size_t)argc) core = atoi(argv[++i]);
    else if (!strcmp(argv[i], "--json")) json = 1;
    else {
      fprintf(stderr, "usage: %s [--pairs N] [--calib SEC] [--core C] [--json]\n", argv[0]);
      return 2;
    }
  }
  if (core >= 0) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(core, &set);
    if (sched_setaffinity(0, sizeof set, &set) != 0) perror("sched_setaffinity");
  }
  if (ipoint_thread_init(2 * pairs + 16) != 0) {
    fprintf(stderr, "buffer allocation failed\n");
    return 1;
  }
  double hz = ipoint_calibrate_tsc_hz(calib);
#if IPOINT_TS_IMPL == IPOINT_TS_CLOCK_GETTIME_RAW
  double tick_ns = 1.0; /* timestamps are already nanoseconds */
#else
  double tick_ns = 1e9 / hz;
#endif

  /* warm up */
  for (i = 0; i < 10000; i++) {
    IPOINT(1);
    IPOINT(2);
  }
  ipoint_reset();
  for (i = 0; i < pairs; i++) {
    IPOINT(1);
    IPOINT(2);
  }
  size_t n = ipoint_count() / 2;
  if (n == 0) {
    fprintf(stderr, "no records\n");
    return 1;
  }
  const ipoint_rec_t *r = ipoint_records();
  uint64_t *d = malloc(n * sizeof(uint64_t));
  size_t bad = 0;
  for (i = 0; i < n; i++) {
    d[i] = r[2 * i + 1].ts - r[2 * i].ts;
    if (r[2 * i + 1].aux != r[2 * i].aux) bad++;
  }
  qsort(d, n, sizeof(uint64_t), cmp_u64);
  double mean = 0;
  for (i = 0; i < n; i++) mean += (double)d[i];
  mean /= (double)n;
  uint64_t mn = d[0], med = quantile(d, n, 0.5), p99 = quantile(d, n, 0.99),
           p999 = quantile(d, n, 0.999), mx = d[n - 1];
  if (json) {
    printf("{\"ts_impl\":\"%s\",\"pairs\":%zu,\"tsc_hz\":%.0f,\"tick_ns\":%.6f,"
           "\"cpu_flags\":%u,\"core\":%d,\"aux_mismatch\":%zu,\"overflow\":%llu,"
           "\"ticks\":{\"min\":%llu,\"median\":%llu,\"mean\":%.2f,\"p99\":%llu,\"p999\":%llu,\"max\":%llu},"
           "\"ns\":{\"min\":%.2f,\"median\":%.2f,\"mean\":%.2f,\"p99\":%.2f,\"p999\":%.2f,\"max\":%.2f}}\n",
           IPOINT_TS_NAME, n, hz, tick_ns, ipoint_cpu_flags(), ipoint_current_cpu(), bad,
           (unsigned long long)ipoint_overflow(), (unsigned long long)mn, (unsigned long long)med, mean,
           (unsigned long long)p99, (unsigned long long)p999, (unsigned long long)mx, mn * tick_ns,
           med * tick_ns, mean * tick_ns, p99 * tick_ns, p999 * tick_ns, mx * tick_ns);
  } else {
    printf("impl=%s pairs=%zu tsc_hz=%.0f tick_ns=%.4f core=%d flags=%u aux_mismatch=%zu\n",
           IPOINT_TS_NAME, n, hz, tick_ns, ipoint_current_cpu(), ipoint_cpu_flags(), bad);
    printf("ticks: min=%llu median=%llu mean=%.1f p99=%llu p99.9=%llu max=%llu\n", (unsigned long long)mn,
           (unsigned long long)med, mean, (unsigned long long)p99, (unsigned long long)p999,
           (unsigned long long)mx);
    printf("ns:    min=%.1f median=%.1f mean=%.1f p99=%.1f p99.9=%.1f max=%.1f\n", mn * tick_ns,
           med * tick_ns, mean * tick_ns, p99 * tick_ns, p999 * tick_ns, mx * tick_ns);
  }
  free(d);
  ipoint_thread_free();
  return 0;
}
