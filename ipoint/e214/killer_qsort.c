/* McIlroy's antiqsort adversary on an exact replica of the NR sort() of
   qsort-exam, then timing of the real kernel on random vs killer inputs. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sched.h>
#include <x86intrin.h>
#include "bench_rng.h"
#define N 999
#define M 7
extern float arr[];
void sort(unsigned long n);

static int val[N + 1], id[N + 1], gas = N + 10, nsolid = 0, candidate = -1;
static long ncmp = 0;
static int cmp(int x, int y) {
  ncmp++;
  if (val[x] == gas && val[y] == gas) { if (x == candidate) val[x] = nsolid++; else val[y] = nsolid++; }
  if (val[x] == gas) candidate = x; else if (val[y] == gas) candidate = y;
  return (val[x] > val[y]) - (val[x] < val[y]);
}
#define SW(a,b) {int t_=(a);(a)=(b);(b)=t_;}
static void replica(unsigned long n) {           /* same control flow as sort(), on ids */
  unsigned long i, ir = n, j, k, l = 1; int jstack = 0; int a; unsigned long istack[100];
  while (1) {
    if (ir - l < M) {
      for (j = l + 1; j <= ir; j++) { a = id[j];
        for (i = j - 1; i >= l; i--) { if (cmp(id[i], a) <= 0) break; id[i + 1] = id[i]; }
        id[i + 1] = a; }
      if (jstack == 0) break;
      ir = istack[jstack--]; l = istack[jstack--];
    } else {
      k = (l + ir) >> 1; SW(id[k], id[l + 1]);
      if (cmp(id[l], id[ir]) > 0) SW(id[l], id[ir]);
      if (cmp(id[l + 1], id[ir]) > 0) SW(id[l + 1], id[ir]);
      if (cmp(id[l], id[l + 1]) > 0) SW(id[l], id[l + 1]);
      i = l + 1; j = ir; a = id[l + 1];
      for (;;) { i++; while (cmp(id[i], a) < 0) i++; j--; while (cmp(id[j], a) > 0) j--; if (j < i) break; SW(id[i], id[j]); }
      id[l + 1] = id[j]; id[j] = a; jstack += 2;
      if (ir - i + 1 >= j - l) { istack[jstack] = ir; istack[jstack - 1] = i; ir = j - 1; }
      else { istack[jstack] = j - 1; istack[jstack - 1] = l; l = i; }
    }
  }
}
static int killer[N + 1];
static void gen(int type, uint64_t seed) {
  bench_rng_t r; rng_seed(&r, seed); arr[0] = 0.0f;
  for (int i = 1; i <= N; i++) arr[i] = (float)(rng_double(&r) * 1000.0);
  if (type == 1) for (int i = 1; i <= N; i++) arr[i] = (float)(killer[i] * (1000.0 / N));
}
int main(int argc, char **argv) {
  int core = atoi(argv[1]); cpu_set_t s; CPU_ZERO(&s); CPU_SET(core, &s); sched_setaffinity(0, sizeof s, &s);
  for (int i = 0; i <= N; i++) { val[i] = gas; id[i] = i; }
  replica(N);
  for (int i = 1; i <= N; i++) if (val[i] == gas) val[i] = nsolid++;
  for (int i = 1; i <= N; i++) killer[i] = val[i];
  printf("adversary comparisons %ld (random input ~%d)\n", ncmp, 12000);
  /* check the replica against the real kernel: sorted output of the killer input */
  const char *names[] = {"random", "killer"};
  for (int type = 0; type < 2; type++) {
    enum { R = 5000 }; static uint64_t t[R];
    for (int w = 0; w < 200; w++) { gen(type, w + 999999); sort(N); }
    for (int r = 0; r < R; r++) { gen(type, r); unsigned a; uint64_t t0 = __rdtscp(&a); _mm_lfence(); sort(N); uint64_t t1 = __rdtscp(&a); _mm_lfence(); t[r] = t1 - t0;
      for (int i = 2; i <= N; i++) if (arr[i - 1] > arr[i]) { printf("NOT SORTED\n"); return 1; } }
    int c(const void *a, const void *b) { uint64_t x = *(uint64_t *)a, y = *(uint64_t *)b; return (x > y) - (x < y); }
    qsort(t, R, 8, c);
    printf("%-8s median %8lu  p99 %8lu  max %8lu ticks\n", names[type], t[R / 2], t[R * 99 / 100], t[R - 1]);
  }
}
