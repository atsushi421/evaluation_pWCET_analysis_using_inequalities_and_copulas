/* splitmix64 (seed derivation) + xoshiro256** (input generation). */
#ifndef BENCH_RNG_H
#define BENCH_RNG_H
#include <stdint.h>

static inline uint64_t splitmix64(uint64_t *x) {
  uint64_t z = (*x += 0x9E3779B97F4A7C15ull);
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
  return z ^ (z >> 31);
}

/* seed of run r for campaign seed0: splitmix64 applied to seed0 + r */
static inline uint64_t bench_run_seed(uint64_t seed0, uint64_t run) {
  uint64_t x = seed0 + run;
  return splitmix64(&x);
}

typedef struct {
  uint64_t s[4];
} bench_rng_t;

static inline void rng_seed(bench_rng_t *r, uint64_t seed) {
  uint64_t x = seed;
  for (int i = 0; i < 4; i++) r->s[i] = splitmix64(&x);
}

static inline uint64_t rng_rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }

static inline uint64_t rng_next(bench_rng_t *r) {
  uint64_t *s = r->s;
  uint64_t result = rng_rotl(s[1] * 5, 7) * 9;
  uint64_t t = s[1] << 17;
  s[2] ^= s[0];
  s[3] ^= s[1];
  s[1] ^= s[2];
  s[0] ^= s[3];
  s[2] ^= t;
  s[3] = rng_rotl(s[3], 45);
  return result;
}

/* uniform integer in [0, n) without modulo bias (Lemire's method, n < 2^32) */
static inline uint32_t rng_below(bench_rng_t *r, uint32_t n) {
  uint64_t x = rng_next(r) >> 32;
  return (uint32_t)((x * (uint64_t)n) >> 32);
}

/* uniform double in [0, 1) */
static inline double rng_double(bench_rng_t *r) { return (double)(rng_next(r) >> 11) * 0x1.0p-53; }

#endif
