#include "bench_api.h"
#include "bench_rng.h"

float sqrtfcn(float val);

static float val;
static float result;

const char *const bench_name = "sqrt";
const char *const bench_entry_function = "sqrtfcn";

void bench_setup(void) {}

/* val ~ U(0, 65536); with probability param the input is exactly 0 so that
 * the val == 0 branch is exercised. */
void bench_gen_input(uint64_t seed, double param) {
  bench_rng_t r;
  rng_seed(&r, seed);
  double u = rng_double(&r);
  if (rng_double(&r) < param)
    val = 0.0f;
  else
    val = (float)(u * 65536.0);
}

void bench_run(void) { result = sqrtfcn(val); }

uint64_t bench_sink(void) {
  union {
    float f;
    uint32_t u;
  } c;
  c.f = result;
  return c.u;
}
