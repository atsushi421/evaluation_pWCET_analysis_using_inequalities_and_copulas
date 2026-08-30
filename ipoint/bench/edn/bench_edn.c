#include "bench_api.h"
#include "bench_rng.h"

/* The kernel's main() is renamed by the Makefile (-Dmain=ipoint_orig_main) and
 * is the instrumented entry (keep_main). Its inputs are the constant arrays
 * declared inside main, so every run executes the same single path. */
int ipoint_orig_main(void);

static int result;

const char *const bench_name = "edn";
const char *const bench_entry_function = "main";

void bench_setup(void) {}

void bench_gen_input(uint64_t seed, double param) {
  (void)seed;
  (void)param;
}

void bench_run(void) { result = ipoint_orig_main(); }

uint64_t bench_sink(void) { return (uint64_t)(uint32_t)result; }
