# ipoint/autoware: unit-level traces of Autoware callbacks

Instrumentation, driver and post-processing for the Autoware case study of the
paper (design: `notes/autoware_campaign_design.md` in the paper repository).
Seven callbacks of an OSS Autoware workspace are instrumented with the same
`ipoint.h` probes as the Mälardalen kernels and driven by the rosbag replay
simulation of the Autoware tutorial; every callback invocation is one run.

| cb | job function | process | trigger |
|---|---|---|---|
| cb1 | `EKFLocalizer::timer_callback` (+ `EKFModule::*`) | `autoware_ekf_localizer_node` | 50 Hz timer |
| cb2 | `Twist2Accel::callback_odometry` (+ `AccelEstimator::estimate`) | `autoware_twist2accel_node` | odometry, 50 Hz |
| cb3 | `StopFilterNode::callback_odometry` (+ `StopFilter::*`) | `autoware_stop_filter_node` | EKF output, 50 Hz |
| cb4 | `Controller::callbackTimerControl` (+ `MpcLateralController::*`, `MPC::*`, `PidLongitudinalController::*`) | `/control/trajectory_follower_container` (dedicated) | 33 Hz timer |
| cb5 | `ScanGroundFilterComponent::faster_filter` (+ `GridGroundFilter::*`) | `/pointcloud_container` | concatenated point cloud, 10 Hz |
| cb6 | `LaneDepartureCheckerNode::onTimer` | `/control/control_check_container` | 10 Hz timer |
| cb7 | `NDTScanMatcher::callback_sensor_points` | `autoware_ndt_scan_matcher_node` (not pinned) | point cloud, 10 Hz |

```
autoware/
├── targets.json            what to instrument: files, job, callees, id bases, bounds, process -> cores
├── ipoint_runtime/         ament package (ipoint.h + the implementation TU), copied into <ws>/src
├── tools/
│   ├── instrument_autoware.py   runs ipoint_instrument.py --lang c++ in place, patches CMake/package.xml
│   ├── patch_launch.py          dedicated container for cb4 (NDT num_threads stays 4)
│   ├── run_replay_campaign.py   the replay loop (launch, pin, play, goal, stop, collect, accept)
│   ├── autoware_trace_merge.py  per-thread job files -> trace.bin + meta.json for ipoint_parse.py
│   ├── merge_campaign.py        merge + parse of a whole campaign per callback
│   ├── prune_from_pilot.py      pilot statistics -> exclude_units (timing granularity)
│   └── campaign_status.py       progress of a running campaign
├── run_production.sh       preflight (boost off, no Autoware running) + nohup runner
├── apply.sh                install + instrument + patch + build (IPOINT_MODE=TIMING|OFF)
├── make_patches.sh         git diffs of the touched files -> patches/*.patch + base.json
├── schemas/<pkg>/          schema.json, scope tree and bounds of every instrumented file
└── patches/                the instrumentation as patches against the recorded commits
```

## Workflow

```bash
# 0. the workspace was built once with compile_commands (needed by libclang):
#    colcon build --symlink-install --packages-select <targets> --cmake-args ... -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
# 1. instrument, patch and build (TIMING); OFF builds the same sources with empty probes
./apply.sh                       # or ./apply.sh --mode OFF
./make_patches.sh                # record the diff of the three repositories
# 2. measurement conditions: fixed clock, idle desktop, no system jobs (sudo)
sudo ../scripts/fix_frequencies.bash
# 3. the campaign (resumable); the runner pins itself, the bag player and the rest of the stack to --rest-cores
source ~/autoware/install/setup.bash
python3 tools/run_replay_campaign.py --out traces/autoware --rate 1.0 --min-replays 470 --min-samples 1e5
# 4. per callback: merge the job files of its process over all accepted replays, then parse
python3 tools/autoware_trace_merge.py --out traces/autoware/merged/cb1 traces/autoware/replay_*/ipoint:<pid>...
python3 ../tools/ipoint_parse.py --schema schemas/autoware_ekf_localizer/ekf_localizer.cpp.schema.json \
    --schema schemas/autoware_ekf_localizer/ekf_module.cpp.schema.json --trace-dir traces/autoware/merged/cb1 \
    --out traces/autoware/parsed/cb1 --ns
```

`tools/merge_campaign.py --campaign traces/autoware` does step 4 for every
callback: it reads `replay_*/replay.json` for the pid of each process, merges
the accepted replays and parses them with the schemas of the packages loaded
into that process; `merge_summary.json` lists runs, units and the parser's
consistency counters per callback.

## Runbook: pilot, pruning, production

```bash
source ~/autoware/install/setup.bash
cd ipoint/autoware
# 1. pilot at full depth (the per-point loops of cb5 are already excluded): 20 replays
python3 tools/run_replay_campaign.py --out traces/pilot --max-replays 20 --min-replays 20 --min-samples 1
python3 tools/merge_campaign.py --campaign traces/pilot
# 2. prune units whose median is below 300 ns, re-instrument and rebuild
python3 tools/prune_from_pilot.py --campaign traces/pilot --apply --report traces/pilot/prune.json
<restore the target sources: git checkout -- <files> in the three repositories>
./apply.sh && ./make_patches.sh
# 3. verification pilot (a few replays), then the production campaign
python3 tools/run_replay_campaign.py --out traces/verify --max-replays 3 --min-replays 3 --min-samples 1
./run_production.sh --out traces/autoware --min-replays 470 --min-samples 1e5   # nohup; resumable
python3 tools/campaign_status.py --campaign traces/autoware
python3 tools/merge_campaign.py --campaign traces/autoware
```

The instrumented sources are tracked by the git diff of the three repositories
(`make_patches.sh`); `instrument_autoware.py` refuses to touch a file that
already contains probes, so restore the sources before re-instrumenting.

## How a job is recorded

`IPOINT_JOB_BEGIN(id)` at the entry of the callback writes the run sentinels
(run index = process-wide invocation counter, seed = thread id) and the entry
probe; `IPOINT_JOB_END(id)` at every exit writes the exit probe and the end
sentinel, and flushes the thread's buffer to
`$IPOINT_OUT_DIR/<comm>_<pid>_<tid>.bin` once it holds more than the high-water
mark (default 4096 records = 64 KiB, outside the measured interval), so that a
process killed at shutdown loses at most that much per thread. Every 64 jobs
of a thread and at process exit, `<comm>_<pid>.meta.json` is (re)written with
the TSC calibration pairs, per-thread record counts, overflows and forced
in-job flushes. A thread that never called `ipoint_thread_init` allocates its
state (heap, never freed, 1 M records) on its first probe; the thread-local
variable only holds the pointer, so the registry stays valid after threads exit.

Callback invocations that leave through an early `return` are runs too; the
parser classifies them by their path signature (`paths.csv`) and the analysis
excludes the initialization-phase paths (design note, sec. 3.1).

## Measurement conditions (design note, sec. 5)

The runner sets its own affinity to `--rest-cores` (default 0-5), so the
launch and the bag player inherit it; after the stack is up it moves every
instrumented process to the cores of `targets.json` (cb1 6, cb2+cb3 7, cb4 8,
cb6 9, cb5 12-15) with `sched_setaffinity` on all threads once the
localization initialized (start-up and the initial pose estimation use every
core), confines the remaining processes to `--rest-cores` (0-5,10-11) and
releases the pinning before the stack is stopped. cb7 (NDT) is not pinned:
two dedicated cores made the alignment five times slower; it shares the rest
cores and is the non-isolated callback of the study.

Foreign activity on the target cores is handled in three layers:

1. before every replay (and again once the partition is applied) the runner
   moves every other process of the same user (browser, editor, desktop
   shell, ...) to the rest cores as well (`--no-confine` disables it), waits
   until the target cores are idle (`--target-idle`, default 5 % busy) and
   records the remaining load in `replay.json`;
2. during the measurement phase a sampler counts, every 0.5 s, the runnable
   threads of processes other than Autoware whose last CPU is a target core
   (`foreign_on_target_cores` in `replay.json`; a replay is rejected above
   `--max-foreign-fraction`, default 2 % of the core-samples). Root daemons
   cannot be moved without privileges and show up here;
3. `sudo ../scripts/isolate_cores.bash` moves the interrupt affinities to the
   rest cores and stops irqbalance (no reboot); with `--grub` it sets
   `isolcpus=6-9 nohz_full=6-9 rcu_nocbs=6-9` on the kernel command line for
   the next boot. Only the single-core targets are isolated: the scheduler
   does not balance load between isolated CPUs, so a multi-threaded process
   pinned to a group of isolated cores piles up on one of them (and processes
   with the default affinity cannot use them at all, which is why start-up and
   the initial pose estimation run before the partition is applied). The
   multi-core group of cb5 (12-15) stays non-isolated; the replay is rejected
   on foreign activity on the isolated cores, while activity on 12-15 (root
   jobs only) is reported in `replay.json`. `campaign.json` records the
   isolated CPUs and the number of IRQs still allowed on the target cores.

A replay
is accepted only if the localization initialized within 15 s, the route was
set, the health topics reached their expected counts, every instrumented
process wrote its meta.json without overflow and no process had to be killed.
`campaign.json` records the commits, boost/frequency state, arguments and
progress; `replay_XXXX/replay.json` the timeline, pids, affinities, counts and
acceptance reasons of every replay.

## Limitations

* Statements produced by macro expansions (`RCLCPP_*`, `DEBUG_INFO`) are
  opaque: they belong to the enclosing unit.
* Lambdas, local classes and `switch` statements are not decomposed.
* Only the listed source files are instrumented; calls into other libraries
  (`ndt_omp::align`, OSQP inside `MPC::executeOptimization`, the boundary
  departure checker) are leaves inside the calling unit's self time.
* The per-point loops of the ground filter are excluded up front
  (`exclude_units`); the granularity of everything else is pruned by the
  pilot (median < 300 ns) as for the benchmarks.

## Parsing C++ with libclang

The instrumenter needs a libclang whose version matches the clang resource
directory it uses (`select_libclang`, `clang_resource_dir`; `IPOINT_LIBCLANG`
overrides). With the pip `libclang` wheel alone, GCC's intrinsics headers do
not parse, and libclang then drops every statement whose expression uses an
unresolved type from the AST *silently*: returns lose their exit probes and
whole branches disappear. On this machine `/usr/lib/llvm-14/lib/libclang-14.so.1`
with `/usr/lib/llvm-14/lib/clang/14.0.6` parses all target files without
errors. The instrumenter also compares the `return` keywords of every function
body with the return statements in the AST and refuses to instrument on a
mismatch (`--allow-missing-returns` downgrades it to a warning).
