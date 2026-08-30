#include "bench_api.h"
#include "bench_rng.h"

/* MAXSIZE of the size-patched kernel (cnt.size.patch: 10 -> 100, the value
 * the upstream comment records as the original). */
#define MAXSIZE 100
typedef int matrix[MAXSIZE][MAXSIZE];
extern matrix Array;
extern int Postotal, Negtotal, Poscnt, Negcnt;
void Sum(matrix Array);

const char *const bench_name = "cnt";
const char *const bench_entry_function = "Sum";

void bench_setup(void) {}

/* Signed values with the magnitude of the kernel's own generator ([0, 8095))
 * so that the positive and the negative branch are both taken. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 0; i < MAXSIZE; i++)
    for (int j = 0; j < MAXSIZE; j++) Array[i][j] = (int)rng_below(&r, 2 * 8095) - 8095;
}

void bench_run(void) { Sum(Array); }

uint64_t bench_sink(void) {
  uint64_t s = (uint32_t)Postotal;
  s = s * 31 + (uint32_t)Negtotal;
  s = s * 31 + (uint32_t)Poscnt;
  return s * 31 + (uint32_t)Negcnt;
}
