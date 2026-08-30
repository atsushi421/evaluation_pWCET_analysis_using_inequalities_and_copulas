#include "bench_api.h"
#include "bench_rng.h"

/* main() (renamed to ipoint_orig_main, instrumented entry) seeds the kernel's
 * own generator with InitSeed() and fills the two 1000-element arrays itself,
 * so the input is the same in every run and the path is fixed. */
int ipoint_orig_main(void);
extern double SumA, SumB;

const char *const bench_name = "st";
const char *const bench_entry_function = "main";

void bench_setup(void) {}

void bench_gen_input(uint64_t seed, double param) {
  (void)seed;
  (void)param;
}

void bench_run(void) { ipoint_orig_main(); }

uint64_t bench_sink(void) {
  union {
    double d;
    uint64_t u;
  } a, b;
  a.d = SumA;
  b.d = SumB;
  return a.u * 31 + b.u;
}
