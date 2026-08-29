/* Interface each benchmark adapter (bench/<name>/bench_<name>.c) implements. */
#ifndef BENCH_API_H
#define BENCH_API_H
#include <stdint.h>

extern const char *const bench_name;
extern const char *const bench_entry_function;

void bench_setup(void);
/* Fill the kernel's input from the run seed. param is a benchmark-specific
 * knob given on the command line (--param), e.g. the probability of val == 0
 * for sqrt. */
void bench_gen_input(uint64_t seed, double param);
/* One measured execution of the kernel's entry function. */
void bench_run(void);
/* Checksum of the kernel output so the compiler cannot discard the work. */
uint64_t bench_sink(void);

#endif
