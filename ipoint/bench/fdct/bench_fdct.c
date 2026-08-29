#include "bench_api.h"
#include "bench_rng.h"

extern short int block[64];
void fdct(short int *blk, int lx);

const char *const bench_name = "fdct";
const char *const bench_entry_function = "fdct";

void bench_setup(void) {}

/* 8-bit image samples, the value range of the hard-coded block. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 0; i < 64; i++) block[i] = (short)rng_below(&r, 256);
}

void bench_run(void) { fdct(block, 8); }

uint64_t bench_sink(void) {
  uint64_t s = 0;
  for (int i = 0; i < 64; i++) s = s * 31 + (uint16_t)block[i];
  return s;
}
