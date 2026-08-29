#include "bench_api.h"
#include "bench_rng.h"

extern long fir_int[36];
extern long in_data[701];
void fir_filter_int(long *in, long *out, long in_len, long *coef, long coef_len, long scale);

static long output[720];

const char *const bench_name = "fir";
const char *const bench_entry_function = "fir_filter_int";

void bench_setup(void) {}

/* 7-bit samples, the value range of the hard-coded in_data; the sentinel
 * in_data[700] stays 0 and the coefficients are the kernel's own. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 0; i < 700; i++) in_data[i] = (long)rng_below(&r, 128);
  in_data[700] = 0;
}

void bench_run(void) { fir_filter_int(in_data, output, 700, fir_int, 35, 285); }

uint64_t bench_sink(void) {
  uint64_t s = 0;
  for (int i = 0; i < 700; i++) s = s * 31 + (uint64_t)output[i];
  return s;
}
