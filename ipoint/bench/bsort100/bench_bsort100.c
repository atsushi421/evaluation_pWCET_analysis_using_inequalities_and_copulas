#include "bench_api.h"
#include "bench_rng.h"

#define NUMELEMS 100
extern int Array[];
void BubbleSort(int Array[]);

const char *const bench_name = "bsort100";
const char *const bench_entry_function = "BubbleSort";

void bench_setup(void) {}

/* bsort100.ann: ASSIGN Array 32 32 100 TOP_INT, i.e. every element is an
 * unconstrained 32-bit integer. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 1; i <= NUMELEMS; i++) Array[i] = (int)(uint32_t)rng_next(&r);
}

void bench_run(void) { BubbleSort(Array); }

uint64_t bench_sink(void) {
  uint64_t s = 0;
  for (int i = 1; i <= NUMELEMS; i++) s = s * 31 + (uint32_t)Array[i];
  return s;
}
