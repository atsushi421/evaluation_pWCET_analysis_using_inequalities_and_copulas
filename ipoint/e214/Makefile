# E2-14 probes: the OFF-mode kernel objects of the campaign builds (bench/build/<bench>/off/kernel.o,
# produced by run_campaign.py) linked with a timing driver that feeds chosen inputs.
#   make -C ipoint/e214
IPOINT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
CC ?= gcc
CFLAGS := -O2 -std=gnu11 -Wall -I$(IPOINT_DIR)/bench/common
all: probe_bsort100 killer_qsort
probe_bsort100: probe_bsort100.c $(IPOINT_DIR)/bench/build/bsort100/off/kernel.o
	$(CC) $(CFLAGS) $^ -o $@
killer_qsort: killer_qsort.c $(IPOINT_DIR)/bench/build/qsort-exam/off/kernel.o
	$(CC) $(CFLAGS) $^ -o $@ -lm
clean:
	rm -f probe_bsort100 killer_qsort
.PHONY: all clean
