#include "bench_api.h"
#include "bench_rng.h"

typedef struct IMMENSE { unsigned long l, r; } immense;
void des(immense inp, immense key, int *newkey, int isw, immense *out);

static immense inp, key, out;
static int newkey, isw;

const char *const bench_name = "ndes";
const char *const bench_entry_function = "des";

void bench_setup(void) {}

/* 64-bit block and key drawn uniformly; the key schedule is recomputed every
 * run (newkey = 1) so that runs do not depend on each other; isw selects
 * encryption or decryption with equal probability. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  inp.l = (unsigned long)(uint32_t)rng_next(&r);
  inp.r = (unsigned long)(uint32_t)rng_next(&r);
  key.l = (unsigned long)(uint32_t)rng_next(&r);
  key.r = (unsigned long)(uint32_t)rng_next(&r);
  isw = (int)(rng_next(&r) >> 63);
  newkey = 1;
}

void bench_run(void) { des(inp, key, &newkey, isw, &out); }

uint64_t bench_sink(void) { return ((uint64_t)(uint32_t)out.l << 32) | (uint32_t)out.r; }
