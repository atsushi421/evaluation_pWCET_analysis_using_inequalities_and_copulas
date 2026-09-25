#include "bench_api.h"
#include "bench_rng.h"

/* Size-patched kernel (qsort-exam.size.patch: arr[20] -> arr[1000]); the
 * kernel sorts arr[1..n] (arr[0] is unused, as upstream). Every run sorts 999
 * U(0, 1000) values. With --param rho > 0 (experiment E2-14), a run is
 * instead given, with probability rho, the fixed quadratic-time input that
 * McIlroy's adversary ("A Killer Adversary for Quicksort", SP&E 1999) builds
 * against this sort(); the choice uses a stream independent of the input
 * stream, so the other runs keep the inputs of rho = 0. */
#define N 999
#define M 7
extern float arr[N + 1];
void sort(unsigned long n);

const char *const bench_name = "qsort-exam";
const char *const bench_entry_function = "sort";

static int killer[N + 1];

/* Replica of sort()'s control flow on item ids; the adversary fixes an item's
 * value only when a comparison forces it and keeps the pivot candidate
 * unfixed ("gas") as long as possible. */
static int val[N + 1], ids[N + 1], nsolid, candidate;
#define GAS (N + 10)
static int adv_cmp(int x, int y) {
  if (val[x] == GAS && val[y] == GAS) {
    if (x == candidate) val[x] = nsolid++;
    else val[y] = nsolid++;
  }
  if (val[x] == GAS) candidate = x;
  else if (val[y] == GAS) candidate = y;
  return (val[x] > val[y]) - (val[x] < val[y]);
}
#define ISWAP(a, b) { int t_ = (a); (a) = (b); (b) = t_; }
static void build_killer(void) {
  unsigned long i, ir = N, j, k, l = 1, istack[2 * 64];
  int jstack = 0, a;
  nsolid = 0;
  candidate = -1;
  for (i = 0; i <= N; i++) { val[i] = GAS; ids[i] = (int)i; }
  while (1) {
    if (ir - l < M) {
      for (j = l + 1; j <= ir; j++) {
        a = ids[j];
        for (i = j - 1; i >= l; i--) {
          if (adv_cmp(ids[i], a) <= 0) break;
          ids[i + 1] = ids[i];
        }
        ids[i + 1] = a;
      }
      if (jstack == 0) break;
      ir = istack[jstack--];
      l = istack[jstack--];
    } else {
      k = (l + ir) >> 1;
      ISWAP(ids[k], ids[l + 1]);
      if (adv_cmp(ids[l], ids[ir]) > 0) ISWAP(ids[l], ids[ir]);
      if (adv_cmp(ids[l + 1], ids[ir]) > 0) ISWAP(ids[l + 1], ids[ir]);
      if (adv_cmp(ids[l], ids[l + 1]) > 0) ISWAP(ids[l], ids[l + 1]);
      i = l + 1;
      j = ir;
      a = ids[l + 1];
      for (;;) {
        i++;
        while (adv_cmp(ids[i], a) < 0) i++;
        j--;
        while (adv_cmp(ids[j], a) > 0) j--;
        if (j < i) break;
        ISWAP(ids[i], ids[j]);
      }
      ids[l + 1] = ids[j];
      ids[j] = a;
      jstack += 2;
      if (ir - i + 1 >= j - l) {
        istack[jstack] = ir;
        istack[jstack - 1] = i;
        ir = j - 1;
      } else {
        istack[jstack] = j - 1;
        istack[jstack - 1] = l;
        l = i;
      }
    }
  }
  for (i = 1; i <= N; i++) killer[i] = val[i] == GAS ? nsolid++ : val[i];
}

void bench_setup(void) { build_killer(); }

/* 1 with probability rho, from a stream independent of the input stream */
int bench_is_adversarial(uint64_t seed, double rho) {
  uint64_t x = seed ^ 0xA5A5A5A5DEADBEEFull;
  return rho > 0 && (double)(splitmix64(&x) >> 11) * 0x1.0p-53 < rho;
}

void bench_gen_input(uint64_t seed, double param) {
  arr[0] = 0.0f;
  if (bench_is_adversarial(seed, param)) {
    for (int i = 1; i <= N; i++) arr[i] = (float)(killer[i] * (1000.0 / N));
    return;
  }
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 1; i <= N; i++) arr[i] = (float)(rng_double(&r) * 1000.0);
}

void bench_run(void) { sort(N); }

uint64_t bench_sink(void) {
  union {
    float f;
    uint32_t u;
  } c;
  uint64_t s = 0;
  for (int i = 1; i <= N; i++) {
    c.f = arr[i];
    s = s * 31 + c.u;
  }
  return s;
}
