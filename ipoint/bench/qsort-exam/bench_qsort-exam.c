#include "bench_api.h"
#include "bench_rng.h"

/* Size-patched kernel (qsort-exam.size.patch: arr[20] -> arr[1000]); the
 * kernel sorts arr[1..n] (arr[0] is unused, as upstream). Every run sorts 999
 * U(0, 1000) values. */
#define N 999
extern float arr[N + 1];
void sort(unsigned long n);

const char *const bench_name = "qsort-exam";
const char *const bench_entry_function = "sort";

void bench_setup(void) {}

void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  arr[0] = 0.0f;
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
