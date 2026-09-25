/* E2-14 second kernel probe: select (NR quickselect, k = N/2) on random, McIlroy-type adversary,
   and subnormal-scaled random inputs. Times the OFF kernel; counts outer-loop
   iterations and comparisons with a C copy of the kernel's control flow. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sched.h>
#include <x86intrin.h>
#include "bench_rng.h"
#define N 1000
extern float arr[N];
float mrtc_select(unsigned long k, unsigned long n);

/* adversary on ids */
static int val[N], ids[N], gas = N + 10, nsolid, candidate = -1;
static int cmp(int x, int y) {
  if (val[x] == gas && val[y] == gas) { if (x == candidate) val[x] = nsolid++; else val[y] = nsolid++; }
  if (val[x] == gas) candidate = x; else if (val[y] == gas) candidate = y;
  return (val[x] > val[y]) - (val[x] < val[y]);
}
#define SW(a,b) {int t_=(a);(a)=(b);(b)=t_;}
static void adversary(unsigned long k, unsigned long n) {
  unsigned long i, ir, j, l, mid; int a, flag = 0, flag2;
  l = 0; ir = n - 1;
  while (!flag) {
    if (ir <= l + 1) { if (ir == l + 1) if (cmp(ids[ir], ids[l]) < 0) SW(ids[l], ids[ir]); flag = 1; }
    else {
      mid = (l + ir) >> 1; SW(ids[mid], ids[l + 1]);
      if (cmp(ids[l + 1], ids[ir]) > 0) SW(ids[l + 1], ids[ir]);
      if (cmp(ids[l], ids[ir]) > 0) SW(ids[l], ids[ir]);
      if (cmp(ids[l + 1], ids[l]) > 0) SW(ids[l + 1], ids[l]);
      i = l + 1; j = ir; a = ids[l]; flag2 = 0;
      while (!flag2) { i++; while (cmp(ids[i], a) < 0) i++; j--; while (cmp(ids[j], a) > 0) j--;
        if (j < i) flag2 = 1; if (!flag2) SW(ids[i], ids[j]); }
      ids[l] = ids[j]; ids[j] = a;
      if (j >= k) ir = j - 1; if (j <= k) l = i;
    }
  }
}
/* counting copy of the kernel on floats */
static float c[N]; static long iters, cmps;
#define SWF(a,b) {float t_=(a);(a)=(b);(b)=t_;}
static void count(unsigned long k, unsigned long n) {
  unsigned long i, ir, j, l, mid; float a; int flag = 0, flag2;
  l = 0; ir = n - 1; iters = cmps = 0;
  while (!flag) { iters++;
    if (ir <= l + 1) { if (ir == l + 1) { cmps++; if (c[ir] < c[l]) SWF(c[l], c[ir]); } flag = 1; }
    else {
      mid = (l + ir) >> 1; SWF(c[mid], c[l + 1]); cmps += 3;
      if (c[l + 1] > c[ir]) SWF(c[l + 1], c[ir]);
      if (c[l] > c[ir]) SWF(c[l], c[ir]);
      if (c[l + 1] > c[l]) SWF(c[l + 1], c[l]);
      i = l + 1; j = ir; a = c[l]; flag2 = 0;
      while (!flag2) { i++; cmps++; while (c[i] < a) { i++; cmps++; } j--; cmps++; while (c[j] > a) { j--; cmps++; }
        if (j < i) flag2 = 1; if (!flag2) SWF(c[i], c[j]); }
      c[l] = c[j]; c[j] = a;
      if (j >= k) ir = j - 1; if (j <= k) l = i;
    }
  }
}
static int killer[N];
static void gen(int type, uint64_t seed) {
  bench_rng_t r; rng_seed(&r, seed);
  for (int i = 0; i < N; i++) arr[i] = (float)(rng_double(&r) * 1000.0);
  if (type == 1) for (int i = 0; i < N; i++) arr[i] = (float)(killer[i] * (1000.0 / N));
  if (type == 2) for (int i = 0; i < N; i++) arr[i] *= 1e-41f;          /* subnormal, same order */
  if (type == 3) for (int i = 0; i < N; i++) arr[i] = (float)(killer[i] * (1000.0 / N)) * 1e-41f;
}
static int cu(const void *a, const void *b) { uint64_t x = *(uint64_t *)a, y = *(uint64_t *)b; return (x > y) - (x < y); }
int main(int argc, char **argv) {
  int core = atoi(argv[1]); cpu_set_t s; CPU_ZERO(&s); CPU_SET(core, &s); sched_setaffinity(0, sizeof s, &s);
  for (int i = 0; i < N; i++) { val[i] = gas; ids[i] = i; }
  adversary(N / 2, N);
  for (int i = 0; i < N; i++) if (val[i] == gas) val[i] = nsolid++;
  for (int i = 0; i < N; i++) killer[i] = val[i];   /* value of the item at position i */
  const char *names[] = {"random", "killer", "subnormal", "killer-sub"};
  for (int type = 0; type < 4; type++) {
    enum { R = 5000 }; static uint64_t t[R]; static double avg[R]; double it = 0, cm = 0;
    for (int w = 0; w < 200; w++) { gen(type, w + 999999); mrtc_select(N / 2, N); }
    for (int r = 0; r < R; r++) {
      gen(type, r); memcpy(c, arr, sizeof c); count(N / 2, N); it += iters; cm += cmps;
      unsigned a; uint64_t t0 = __rdtscp(&a); _mm_lfence(); float v = mrtc_select(N / 2, N); uint64_t t1 = __rdtscp(&a); _mm_lfence();
      t[r] = t1 - t0; avg[r] = (double)t[r] / iters;
      if (v != c[N / 2]) { printf("MISMATCH\n"); return 1; }
    }
    qsort(t, R, 8, cu);
    double amax = 0, asum = 0; for (int r = 0; r < R; r++) { asum += avg[r]; if (avg[r] > amax) amax = avg[r]; }
    printf("%-10s median %8lu p99 %8lu max %8lu ticks | iters %.1f cmps %.0f | avg/iter mean %.0f max %.0f ticks\n",
           names[type], t[R / 2], t[R * 99 / 100], t[R - 1], it / R, cm / R, asum / R, amax);
  }
}
