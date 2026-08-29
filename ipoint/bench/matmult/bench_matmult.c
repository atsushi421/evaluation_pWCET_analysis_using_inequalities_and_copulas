#include "bench_api.h"
#include "bench_rng.h"

#define UPPERLIMIT 20
typedef int matrix[UPPERLIMIT][UPPERLIMIT];
extern matrix ArrayA, ArrayB, ResultArray;
void Multiply(matrix A, matrix B, matrix Res);

const char *const bench_name = "matmult";
const char *const bench_entry_function = "Multiply";

void bench_setup(void) {}

/* Same value range as the kernel's own generator RandomInteger(): [0, 8095). */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  for (int i = 0; i < UPPERLIMIT; i++)
    for (int j = 0; j < UPPERLIMIT; j++) {
      ArrayA[i][j] = (int)rng_below(&r, 8095);
      ArrayB[i][j] = (int)rng_below(&r, 8095);
    }
}

void bench_run(void) { Multiply(ArrayA, ArrayB, ResultArray); }

uint64_t bench_sink(void) {
  uint64_t s = 0;
  for (int i = 0; i < UPPERLIMIT; i++)
    for (int j = 0; j < UPPERLIMIT; j++) s = s * 31 + (uint32_t)ResultArray[i][j];
  return s;
}
