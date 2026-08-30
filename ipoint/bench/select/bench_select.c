#include "bench_api.h"
#include "bench_rng.h"

/* Size-patched kernel (select.size.patch: arr[20] -> arr[1000]); the kernel
 * indexes arr[0..n-1]. Every run selects the median of 1000 U(0, 1000) values.
 * The kernel object is compiled with -Dselect=mrtc_select because libc
 * declares select() through <sys/types.h>. */
#define N 1000
extern float arr[N];
float mrtc_select(unsigned long k, unsigned long n);

static float result;

const char *const bench_name = "select";
const char *const bench_entry_function = "select";

void bench_setup(void) {}

void bench_gen_input(uint64_t seed, double param) {
  (void)param;
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
