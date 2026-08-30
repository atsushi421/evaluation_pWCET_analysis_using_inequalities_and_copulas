# Build one benchmark in one mode.
#   make BENCH=bsort100 MODE=timing SRC=build/bsort100/bsort100.ipoint.c
# MODE: off | timing | coverage.  The kernel is compiled with KERNEL_CFLAGS
# (paper setting: -O2 -fno-builtin) and its main() is renamed away.
IPOINT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
BENCH ?= bsort100
MODE ?= timing
TS_IMPL ?= IPOINT_TS_RDTSCP_LFENCE
SRC ?= build/$(BENCH)/$(BENCH).ipoint.c
BUILD ?= build/$(BENCH)/$(MODE)
CC ?= gcc
KERNEL_CFLAGS ?= -O2 -fno-builtin
# extra flags for the kernel object only (e.g. -std=c11 -Dselect=mrtc_select for
# the kernel whose function clashes with libc); run_campaign.py sets them from
# BENCHES[b]["kernel_flags"]
KERNEL_DEFS ?=
HARNESS_CFLAGS ?= -O2
LDLIBS ?= -lm
MODE_UPPER := $(shell echo $(MODE) | tr a-z A-Z)
CFLAGS_COMMON := -std=gnu11 -Wall -I$(IPOINT_DIR)/include -I$(IPOINT_DIR)/bench/common \
                 -DIPOINT_MODE_$(MODE_UPPER) -DIPOINT_TS_IMPL=$(TS_IMPL)
EXE := $(BUILD)/bench_$(BENCH)

all: $(EXE) $(BUILD)/kernel.objdump

$(BUILD):
	mkdir -p $@

$(BUILD)/kernel.o: $(SRC) $(IPOINT_DIR)/include/ipoint.h | $(BUILD)
	$(CC) $(KERNEL_CFLAGS) $(CFLAGS_COMMON) -Dmain=ipoint_orig_main $(KERNEL_DEFS) -c $< -o $@

$(BUILD)/kernel.objdump: $(BUILD)/kernel.o
	objdump -d $< > $@

$(BUILD)/harness.o: $(IPOINT_DIR)/bench/common/bench_main.c $(IPOINT_DIR)/include/ipoint.h | $(BUILD)
	$(CC) $(HARNESS_CFLAGS) $(CFLAGS_COMMON) -c $< -o $@

$(BUILD)/adapter.o: $(IPOINT_DIR)/bench/$(BENCH)/bench_$(BENCH).c | $(BUILD)
	$(CC) $(HARNESS_CFLAGS) $(CFLAGS_COMMON) -c $< -o $@

$(EXE): $(BUILD)/kernel.o $(BUILD)/harness.o $(BUILD)/adapter.o
	$(CC) $^ -o $@ $(LDLIBS)

clean:
	rm -rf build

.PHONY: all clean
