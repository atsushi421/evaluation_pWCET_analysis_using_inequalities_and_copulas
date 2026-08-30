#include "bench_api.h"
#include "bench_rng.h"

/* main() (renamed to ipoint_orig_main, instrumented entry) generates the
 * 201-sample test signal with the kernel's own fixed-seed generator and runs
 * the adaptive filter over it. main() rescales the global step size mu in
 * place, so mu is restored before every run to keep the runs identical. */
int ipoint_orig_main(void);
extern float mu;

static float mu0;

const char *const bench_name = "lms";
const char *const bench_entry_function = "main";

void bench_setup(void) { mu0 = mu; }

void bench_gen_input(uint64_t seed, double param) {
  (void)seed;
  (void)param;
  mu = mu0;
}

void bench_run(void) { ipoint_orig_main(); }

uint64_t bench_sink(void) {
  union {
    float f;
    uint32_t u;
  } c;
  c.f = mu;
  return c.u;
}
