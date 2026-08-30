#include "bench_api.h"
#include "bench_rng.h"

/* n = 49 is the largest order the upstream arrays a[50][50], b[50], x[50]
 * admit (the kernel indexes 0..n). Off-diagonal entries are U(0, 10) and the
 * diagonal is 500 + U(0, 10), so the matrix is diagonally dominant and the
 * eps pivot check never returns early. */
#define N 49
extern double a[50][50], b[50], x[50];
int ludcmp(int n, double eps);

static int result;

const char *const bench_name = "ludcmp";
const char *const bench_entry_function = "ludcmp";

void bench_setup(void) {}

void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 0; i <= N; i++) {
    for (int j = 0; j <= N; j++) a[i][j] = rng_double(&r) * 10.0 + (i == j ? 500.0 : 0.0);
    b[i] = rng_double(&r) * 100.0;
  }
}

void bench_run(void) { result = ludcmp(N, 1.0e-6); }

uint64_t bench_sink(void) {
  union {
    double d;
    uint64_t u;
  } c;
  uint64_t s = (uint32_t)result;
  for (int i = 0; i <= N; i++) {
    c.d = x[i];
    s = s * 31 + c.u;
  }
  return s;
}
