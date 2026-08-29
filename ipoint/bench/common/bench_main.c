/*
 * bench_main - generic measurement harness for an instrumented kernel.
 *
 *   bench_<name> --out DIR [--runs N] [--first-run K] [--full-trace-runs N]
 *                [--seed0 S] [--core C] [--warmup N] [--param P] [--calib SEC]
 *                [--entry-id E --exit-id X] [--max-id M] [--buf-recs N]
 *
 * Every run: derive the run seed, generate the input, execute the kernel once
 * between two harness timestamps, then record one summary row. For the first
 * --full-trace-runs runs all IPoint records are appended to DIR/trace.bin;
 * afterwards only the summary row (end-to-end time from the outermost IPoint
 * pair, harness time, per-id hit counts) is kept in DIR/summary.bin.
 *
 * summary.bin row layout (little endian):
 *   u64 run, u64 seed, u64 e2e_ticks, u64 harness_ticks, u64 sink,
 *   u32 n_records, u32 overflow, u32 hits[max_id + 1]
 */
#define _GNU_SOURCE
#define IPOINT_IMPLEMENTATION
#include "ipoint.h"

#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "bench_api.h"
#include "bench_rng.h"

static void die(const char *msg) {
  perror(msg);
  exit(1);
}

static uint64_t parse_u64(const char *s) {
  char *end;
  double d = strtod(s, &end); /* accepts 1e7 */
  if (*end) {
    fprintf(stderr, "bad number: %s\n", s);
    exit(2);
  }
  return (uint64_t)d;
}

static void mkdir_p(const char *dir) {
  char tmp[4096];
  size_t n = strlen(dir);
  if (n == 0 || n >= sizeof tmp) die("mkdir_p");
  memcpy(tmp, dir, n + 1);
  for (size_t i = 1; i < n; i++) {
    if (tmp[i] == '/') {
      tmp[i] = 0;
      if (mkdir(tmp, 0755) != 0 && errno != EEXIST) die(tmp);
      tmp[i] = '/';
    }
  }
  if (mkdir(tmp, 0755) != 0 && errno != EEXIST) die(tmp);
}

static double wall_now(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

int main(int argc, char **argv) {
  const char *out = NULL;
  uint64_t runs = 10000, first_run = 0, full_trace_runs = 100000, seed0 = 20260829, warmup = 1000;
  uint64_t buf_recs = 1u << 20;
  int core = -1;
  double param = 0.0, calib = 1.0;
  uint32_t entry_id = 0, exit_id = 0, max_id = 0;
  int i;
  for (i = 1; i < argc; i++) {
    const char *a = argv[i];
    const char *v = (i + 1 < argc) ? argv[i + 1] : NULL;
    if (!strcmp(a, "--out") && v) out = argv[++i];
    else if (!strcmp(a, "--runs") && v) runs = parse_u64(argv[++i]);
    else if (!strcmp(a, "--first-run") && v) first_run = parse_u64(argv[++i]);
    else if (!strcmp(a, "--full-trace-runs") && v) full_trace_runs = parse_u64(argv[++i]);
    else if (!strcmp(a, "--seed0") && v) seed0 = parse_u64(argv[++i]);
    else if (!strcmp(a, "--core") && v) core = atoi(argv[++i]);
    else if (!strcmp(a, "--warmup") && v) warmup = parse_u64(argv[++i]);
    else if (!strcmp(a, "--param") && v) param = atof(argv[++i]);
    else if (!strcmp(a, "--calib") && v) calib = atof(argv[++i]);
    else if (!strcmp(a, "--entry-id") && v) entry_id = (uint32_t)parse_u64(argv[++i]);
    else if (!strcmp(a, "--exit-id") && v) exit_id = (uint32_t)parse_u64(argv[++i]);
    else if (!strcmp(a, "--max-id") && v) max_id = (uint32_t)parse_u64(argv[++i]);
    else if (!strcmp(a, "--buf-recs") && v) buf_recs = parse_u64(argv[++i]);
    else {
      fprintf(stderr, "unknown or incomplete option: %s\n", a);
      return 2;
    }
  }
  if (!out) {
    fprintf(stderr, "--out DIR is required\n");
    return 2;
  }
  mkdir_p(out);

  if (core >= 0) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(core, &set);
    if (sched_setaffinity(0, sizeof set, &set) != 0) die("sched_setaffinity");
  }
  int mlock_ok = mlockall(MCL_CURRENT | MCL_FUTURE) == 0;
  if (!mlock_ok) fprintf(stderr, "warning: mlockall failed (%s); continuing\n", strerror(errno));

  if (ipoint_thread_init((size_t)buf_recs) != 0) die("ipoint_thread_init");
  uint32_t *hist = calloc(max_id + 1, sizeof(uint32_t));
  if (!hist) die("calloc");

  char path[4096];
  snprintf(path, sizeof path, "%s/trace.bin", out);
  FILE *tracefp = fopen(path, "wb");
  if (!tracefp) die("trace.bin");
  snprintf(path, sizeof path, "%s/summary.bin", out);
  FILE *sumfp = fopen(path, "wb");
  if (!sumfp) die("summary.bin");
  static char sumbuf[1 << 20], trbuf[1 << 22];
  setvbuf(sumfp, sumbuf, _IOFBF, sizeof sumbuf);
  setvbuf(tracefp, trbuf, _IOFBF, sizeof trbuf);

  bench_setup();
  double tsc_hz_start = ipoint_calibrate_tsc_hz(calib);
  double wall_start = wall_now();

  uint64_t r;
  for (r = 0; r < warmup; r++) {
    bench_gen_input(bench_run_seed(seed0 ^ 0x5DEECE66Dull, r), param);
    bench_run();
    ipoint_reset();
  }
  ipoint_hits_copy_and_clear(hist, max_id);

  uint64_t migrations = 0, missing_e2e = 0, total_overflow = 0, sink_acc = 0;
  double e2e_sum = 0;
  uint64_t e2e_max = 0, e2e_min = UINT64_MAX;
  for (r = first_run; r < first_run + runs; r++) {
    uint64_t seed = bench_run_seed(seed0, r);
    uint32_t aux0, aux1;
    ipoint_reset();
    ipoint_run_begin(r, seed);
    bench_gen_input(seed, param);
    uint64_t t0 = ipoint_now(&aux0);
    bench_run();
    uint64_t t1 = ipoint_now(&aux1);
    ipoint_run_end();
    uint64_t sink = bench_sink();
    sink_acc += sink;
    if ((aux0 & 0xFFFu) != (aux1 & 0xFFFu)) migrations++;

    uint64_t e2e = 0;
#if defined(IPOINT_MODE_TIMING)
    uint64_t a = 0, b = 0;
    if (entry_id && ipoint_first_last(entry_id, exit_id, &a, &b)) e2e = b - a;
    else missing_e2e++;
    ipoint_histogram(hist, max_id);
#elif defined(IPOINT_MODE_COVERAGE)
    ipoint_hits_copy_and_clear(hist, max_id);
#else
    memset(hist, 0, sizeof(uint32_t) * (max_id + 1));
#endif
    uint32_t nrec = (uint32_t)ipoint_count();
    uint32_t ovf = (uint32_t)ipoint_overflow();
    total_overflow += ovf;
    if (r - first_run < full_trace_runs) ipoint_flush(tracefp);
    else ipoint_reset();

    uint64_t row[5] = {r, seed, e2e, t1 - t0, sink};
    uint32_t row2[2] = {nrec, ovf};
    fwrite(row, sizeof row, 1, sumfp);
    fwrite(row2, sizeof row2, 1, sumfp);
    fwrite(hist, sizeof(uint32_t), max_id + 1, sumfp);

    uint64_t obs = e2e ? e2e : (t1 - t0);
    e2e_sum += (double)obs;
    if (obs > e2e_max) e2e_max = obs;
    if (obs < e2e_min) e2e_min = obs;
    if (((r - first_run + 1) % 1000000ull) == 0)
      fprintf(stderr, "%s: %llu/%llu runs, %.1f s elapsed\n", bench_name,
              (unsigned long long)(r - first_run + 1), (unsigned long long)runs, wall_now() - wall_start);
  }
  double wall_end = wall_now();
  double tsc_hz_end = ipoint_calibrate_tsc_hz(calib);
  fclose(tracefp);
  fclose(sumfp);

  snprintf(path, sizeof path, "%s/meta.json", out);
  FILE *mf = fopen(path, "w");
  if (!mf) die("meta.json");
  fprintf(mf,
          "{\n"
          "  \"bench\": \"%s\",\n  \"entry_function\": \"%s\",\n  \"mode\": \"%s\",\n  \"ts_impl\": \"%s\",\n"
          "  \"tsc_hz_start\": %.0f,\n  \"tsc_hz_end\": %.0f,\n  \"cpu_flags\": %u,\n  \"core_requested\": %d,\n"
          "  \"core_observed\": %d,\n  \"mlockall\": %s,\n  \"runs\": %llu,\n  \"first_run\": %llu,\n"
          "  \"full_trace_runs\": %llu,\n  \"seed0\": %llu,\n  \"warmup\": %llu,\n  \"param\": %g,\n"
          "  \"entry_id\": %u,\n  \"exit_id\": %u,\n  \"max_id\": %u,\n  \"buf_recs\": %llu,\n"
          "  \"migrations\": %llu,\n  \"missing_e2e\": %llu,\n  \"total_overflow\": %llu,\n"
          "  \"sink\": %llu,\n  \"wall_seconds\": %.3f,\n"
          "  \"e2e_ticks\": {\"min\": %llu, \"mean\": %.2f, \"max\": %llu},\n"
          "  \"record_layout\": \"<u8 ts, <u4 id, <u4 aux\",\n"
          "  \"sentinels\": {\"run_begin\": %u, \"run_seed\": %u, \"run_end\": %u},\n"
          "  \"summary_layout\": \"<u8 run, <u8 seed, <u8 e2e_ticks, <u8 harness_ticks, <u8 sink, <u4 n_records, <u4 overflow, <u4 hits[max_id+1]\"\n"
          "}\n",
          bench_name, bench_entry_function, IPOINT_MODE_NAME, IPOINT_TS_NAME, tsc_hz_start, tsc_hz_end,
          ipoint_cpu_flags(), core, ipoint_current_cpu(), mlock_ok ? "true" : "false",
          (unsigned long long)runs, (unsigned long long)first_run, (unsigned long long)full_trace_runs,
          (unsigned long long)seed0, (unsigned long long)warmup, param, entry_id, exit_id, max_id,
          (unsigned long long)buf_recs, (unsigned long long)migrations, (unsigned long long)missing_e2e,
          (unsigned long long)total_overflow, (unsigned long long)sink_acc, wall_end - wall_start,
          (unsigned long long)e2e_min, e2e_sum / (double)runs, (unsigned long long)e2e_max, IPOINT_ID_RUN_BEGIN,
          IPOINT_ID_RUN_SEED, IPOINT_ID_RUN_END);
  fclose(mf);
  fprintf(stderr, "%s [%s]: %llu runs in %.1f s; e2e ticks min/mean/max = %llu/%.1f/%llu; migrations=%llu overflow=%llu\n",
          bench_name, IPOINT_MODE_NAME, (unsigned long long)runs, wall_end - wall_start, (unsigned long long)e2e_min,
          e2e_sum / (double)runs, (unsigned long long)e2e_max, (unsigned long long)migrations,
          (unsigned long long)total_overflow);
  free(hist);
  ipoint_thread_free();
  return 0;
}
