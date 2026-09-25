#include "bench_api.h"
#include "bench_rng.h"

unsigned char prime(unsigned int n);

static unsigned int x;
static unsigned char result;

const char *const bench_name = "prime";
const char *const bench_entry_function = "prime";

void bench_setup(void) {}

/* x ~ U(0, 65535^2): even and small-factor inputs leave the trial-division
 * loop early, primes (about 1/ln(x) of the inputs) run it up to sqrt(x)/2
 * times. x stays below 65535^2 so that i*i in the loop cannot wrap around
 * uint32 and the static loop bound 32767 (i <= 65535) holds for every input;
 * primes above 65535^2 would iterate 103,620 times through wrapped i*i, and
 * adversarial values near 2^32 whose exit condition is never met by an odd
 * quadratic residue would iterate ~2^31 times. */
void bench_gen_input(uint64_t seed, double param) {
  (void)param;
  bench_rng_t r;
  rng_seed(&r, seed);
  x = rng_below(&r, 0xFFFE0001u); /* 65535^2 */
}

void bench_run(void) { result = prime(x); }

uint64_t bench_sink(void) { return ((uint64_t)x << 8) | result; }
