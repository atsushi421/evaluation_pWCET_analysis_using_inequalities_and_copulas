#include "bench_api.h"
#include "bench_rng.h"

/* Size-patched kernel (select.size.patch: arr[20] -> arr[1000]); the kernel
 * indexes arr[0..n-1]. Every run selects the median of 1000 U(0, 1000) values.
 * With --param rho > 0 (experiment E2-14, second kernel), a run is instead
 * given, with probability rho, the fixed quadratic-time input that McIlroy's
 * adversary ("A Killer Adversary for Quicksort", SP&E 1999) builds against
 * this select(); the choice uses a stream independent of the input stream, so
 * the other runs keep the inputs of rho = 0. The kernel object is compiled
 * with -Dselect=mrtc_select because libc declares select() through
 * <sys/types.h>. */
#define N 1000
extern float arr[N];
float mrtc_select(unsigned long k, unsigned long n);

static float result;
static int killer[N];

const char *const bench_name = "select";
const char *const bench_entry_function = "select";

/* Replica of select()'s control flow on item ids; the adversary fixes an
 * item's value only when a comparison forces it and keeps the pivot candidate
 * unfixed ("gas") as long as possible. */
static int val[N], ids[N], nsolid, candidate;
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
static void build_killer(unsigned long k, unsigned long n) {
  unsigned long i, ir, j, l, mid;
  int a, flag = 0, flag2;
  nsolid = 0;
  candidate = -1;
  for (i = 0; i < N; i++) { val[i] = GAS; ids[i] = (int)i; }
  l = 0;
  ir = n - 1;
  while (!flag) {
    if (ir <= l + 1) {
      if (ir == l + 1 && adv_cmp(ids[ir], ids[l]) < 0) ISWAP(ids[l], ids[ir]);
      flag = 1;
    } else {
      mid = (l + ir) >> 1;
      ISWAP(ids[mid], ids[l + 1]);
      if (adv_cmp(ids[l + 1], ids[ir]) > 0) ISWAP(ids[l + 1], ids[ir]);
      if (adv_cmp(ids[l], ids[ir]) > 0) ISWAP(ids[l], ids[ir]);
      if (adv_cmp(ids[l + 1], ids[l]) > 0) ISWAP(ids[l + 1], ids[l]);
      i = l + 1;
      j = ir;
      a = ids[l];
      flag2 = 0;
      while (!flag2) {
        i++;
        while (adv_cmp(ids[i], a) < 0) i++;
        j--;
        while (adv_cmp(ids[j], a) > 0) j--;
        if (j < i) flag2 = 1;
        if (!flag2) ISWAP(ids[i], ids[j]);
      }
      ids[l] = ids[j];
      ids[j] = a;
      if (j >= k) ir = j - 1;
      if (j <= k) l = i;
    }
  }
  /* val[] is indexed by item id, and item i starts at position i */
  for (i = 0; i < N; i++) killer[i] = val[i] == GAS ? nsolid++ : val[i];
}

void bench_setup(void) { build_killer(N / 2, N); }

/* 1 with probability rho, from a stream independent of the input stream */
static int is_adversarial(uint64_t seed, double rho) {
  uint64_t x = seed ^ 0xA5A5A5A5DEADBEEFull;
  return rho > 0 && (double)(splitmix64(&x) >> 11) * 0x1.0p-53 < rho;
}

void bench_gen_input(uint64_t seed, double param) {
  if (is_adversarial(seed, param)) {
    for (int i = 0; i < N; i++) arr[i] = (float)(killer[i] * (1000.0 / N));
    return;
  }
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 0; i < N; i++) arr[i] = (float)(rng_double(&r) * 1000.0);
}

void bench_run(void) { result = mrtc_select(N / 2, N); }

uint64_t bench_sink(void) {
  union {
    float f;
    uint32_t u;
  } c;
  c.f = result;
  return c.u;
}
