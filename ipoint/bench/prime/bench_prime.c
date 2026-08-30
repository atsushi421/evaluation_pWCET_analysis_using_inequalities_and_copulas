#include "bench_api.h"
#include "bench_rng.h"

unsigned char prime(unsigned int n);

static unsigned int x;
static unsigned char result;

const char *const bench_name = "prime";
const char *const bench_entry_function = "prime";

void bench_setup(void) {}

/* x ~ U(0, 2^32): even and small-factor inputs leave the trial-division loop
 * early, primes (about 1/ln(2^32) of the inputs) run it up to sqrt(x)/2 times. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  x = (unsigned int)(rng_next(&r) >> 32);
}

void bench_run(void) { result = prime(x); }

uint64_t bench_sink(void) { return ((uint64_t)x << 8) | result; }
