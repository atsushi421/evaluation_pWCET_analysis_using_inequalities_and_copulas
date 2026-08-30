#!/usr/bin/env python3
"""Drive the Autoware rosbag-replay campaign: start the complete stack, pin the
instrumented processes to their cores, replay the sample rosbag, wait for the
localization initialization, set the goal, stop the stack when the bag ends,
collect the IPoint traces and judge the replay against the acceptance criteria.
Repeats until --min-replays replays were accepted and every callback has
--min-samples nominal samples (topic-count proxies). Resumable: existing
replay_XXXX directories with a replay.json are counted, incomplete ones are set
aside.

    source ~/autoware/install/setup.bash
    run_replay_campaign.py --out traces/autoware [--rate 1.0] [--min-replays 470]
        [--min-samples 1e5] [--max-replays N] [--rest-cores 0-5] [--no-pin]
        [--map DIR] [--bag DIR] [--targets targets.json] [--idle-load 10]

Per replay: replay_XXXX/{ipoint/ (per-thread .bin + meta.json of every
instrumented process), launch.log, play.log, counts.json, replay.json}.
campaign.json in --out records the environment, arguments and progress.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
AW = os.path.dirname(HERE)
IPOINT = os.path.dirname(AW)

GOAL = ('{header: {frame_id: map}, pose: {position: {x: 89518.9453125, y: 42437.75390625, z: 0.0}, '
        'orientation: {x: 0.0, y: 0.0, z: 0.8494069322413849, w: 0.5277384422801502}}}')
GOAL_POSE = {"x": 89518.9453125, "y": 42437.75390625, "qz": 0.8494069322413849, "qw": 0.5277384422801502}

# topic -> (minimum count for an accepted 1.0x replay, callback it counts)
# thresholds: the pilot (20 replays, init 8.5-11 s) gave 1004-1125 odometry, 623-712 control,
# 190-215 ground-filter, 190-212 lane-departure and 200-230 NDT messages per replay
COUNT_TOPICS = {
    "/localization/pose_twist_fusion_filter/kinematic_state": (900, "cb1"),
    "/localization/acceleration": (900, "cb2"),
    "/localization/kinematic_state": (900, "cb3"),
    "/control/trajectory_follower/control_cmd": (550, "cb4"),
    "/perception/obstacle_segmentation/pointcloud": (170, "cb5"),
    "/control/trajectory_follower/lane_departure_checker_node/debug/processing_time_ms": (150, "cb6"),
    "/localization/pose_estimator/pose": (170, "cb7"),
    "/sensing/lidar/concatenated/pointcloud": (295, None),
    "/planning/trajectory": (130, None),
}
CONCAT_MAX = 303
AUTOWARE_PROC_RE = re.compile(r"component_container|autoware_.*_node|ros2 launch|ros2 bag|robot_state_publisher|"
                              r"rviz2|_node\b")


def parse_cores(s: str):
    out = set()
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out |= set(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return sorted(out)


def now() -> float:
    return time.time()


def read_cmdline(pid: int):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return [c.decode(errors="replace") for c in f.read().split(b"\0") if c]
    except OSError:
        return None


def all_pids():
    return [int(p) for p in os.listdir("/proc") if p.isdigit()]


def autoware_pids(exclude=()):
    out = []
    me = os.getpid()
    for pid in all_pids():
        if pid == me or pid in exclude:
            continue
        cl = read_cmdline(pid)
        if not cl:
            continue
        s = " ".join(cl)
        if AUTOWARE_PROC_RE.search(s) and "run_replay_campaign" not in s:
            out.append(pid)
    return out


def match_process(spec_args, exclude=()):
    """pids whose cmdline contains every required argument (exact when prefixed with '=')."""
    hits = []
    for pid in all_pids():
        if pid in exclude:
            continue
        cl = read_cmdline(pid)
        if not cl:
            continue
        ok = True
        for req in spec_args:
            if req.startswith("="):
                ok = ok and (req[1:] in cl)
            else:
                ok = ok and any(req in c for c in cl)
        if ok:
            hits.append(pid)
    return hits


def pin(pid: int, cores):
    n = 0
    for tid in os.listdir(f"/proc/{pid}/task"):
        try:
            os.sched_setaffinity(int(tid), cores)
            n += 1
        except OSError:
            pass
    return n


def cpu_snapshot():
    with open("/proc/stat") as f:
        parts = f.readline().split()
    v = list(map(int, parts[1:]))
    return sum(v), v[3] + v[4]


def percpu_snapshot():
    """core -> (total jiffies, idle jiffies)"""
    out = {}
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("cpu") and line[3].isdigit():
                p = line.split()
                v = list(map(int, p[1:]))
                out[int(p[0][3:])] = (sum(v), v[3] + v[4])
    return out


def core_load(cores, seconds: float):
    """busy % of each of the given cores over `seconds` (nothing of ours runs there
    before a replay, so this is foreign activity: desktop, root jobs, kernel)."""
    a = percpu_snapshot()
    time.sleep(seconds)
    b = percpu_snapshot()
    out = {}
    for c in cores:
        if c in a and c in b:
            tot, idle = b[c][0] - a[c][0], b[c][1] - a[c][1]
            out[c] = round(100.0 * (tot - idle) / tot, 1) if tot else 0.0
    return out


def pid_uid(pid: int):
    try:
        return os.stat(f"/proc/{pid}").st_uid
    except OSError:
        return None


def confine_user_processes(cores, exclude=()):
    """Move every process of this user that is not excluded (the runner, the Autoware
    processes) to `cores`: the desktop (browser, editor, shell) then never runs on
    the cores dedicated to the instrumented callbacks. Children inherit the mask.
    Processes of other users (root daemons) cannot be moved without privileges."""
    me, uid = os.getpid(), os.getuid()
    moved, failed = 0, 0
    for pid in all_pids():
        if pid == me or pid in exclude or pid_uid(pid) != uid:
            continue
        try:
            if set(os.sched_getaffinity(pid)) <= set(cores):
                continue
            pin(pid, cores)
            moved += 1
        except OSError:
            failed += 1
    return moved, failed


def isolated_cpus():
    try:
        with open("/sys/devices/system/cpu/isolated") as f:
            return f.read().strip()
    except OSError:
        return ""


def irqs_on_cores(cores):
    """number of IRQs whose affinity intersects `cores` (readable without privileges)"""
    n = tot = 0
    for p in glob.glob("/proc/irq/*/smp_affinity_list"):
        try:
            with open(p) as f:
                lst = set(parse_cores(f.read().strip()))
        except (OSError, ValueError):
            continue
        tot += 1
        if lst & set(cores):
            n += 1
    return n, tot


class ForeignSampler(threading.Thread):
    """Every 0.5 s, count the runnable threads of processes other than the given
    Autoware pids whose last CPU is one of the target cores (purity of the
    isolated cores during the measurement phase)."""

    def __init__(self, target_cores, autoware, period=0.5):
        super().__init__(daemon=True)
        self.cores, self.aw, self.period = set(target_cores), set(autoware), period
        # only the isolated target cores are guaranteed foreign-free (root jobs cannot enter
        # them); on non-isolated target cores (multi-core groups need load balancing, which
        # isolcpus removes) foreign activity is reported but does not reject the replay
        self.iso_cores = set(parse_cores(isolated_cpus())) & self.cores or self.cores
        self.samples = 0
        self.hits = 0
        self.hits_isolated = 0
        self.offenders = {}
        self.stop_flag = threading.Event()

    def run(self):
        me = os.getpid()
        while not self.stop_flag.is_set():
            self.samples += 1
            for pid in all_pids():
                if pid in self.aw or pid == me:
                    continue
                try:
                    for tid in os.listdir(f"/proc/{pid}/task"):
                        with open(f"/proc/{pid}/task/{tid}/stat") as f:
                            st = f.read()
                        rp = st.rindex(")")
                        fields = st[rp + 2:].split()
                        if fields[0] == "R" and int(fields[36]) in self.cores:
                            self.hits += 1
                            if int(fields[36]) in self.iso_cores:
                                self.hits_isolated += 1
                            name = st[st.index("(") + 1:rp]
                            self.offenders[name] = self.offenders.get(name, 0) + 1
                except (OSError, ValueError, IndexError):
                    continue
            self.stop_flag.wait(self.period)

    def stop(self):
        self.stop_flag.set()
        self.join(timeout=5)
        top = sorted(self.offenders.items(), key=lambda x: -x[1])[:6]
        return {"samples": self.samples, "foreign_runnable_on_target_cores": self.hits,
                "hits_isolated": self.hits_isolated, "isolated_target_cores": sorted(self.iso_cores), "top": top}


def proc_cpu_snapshot():
    d = {}
    for pid in all_pids():
        try:
            with open(f"/proc/{pid}/stat") as f:
                st = f.read()
            rp = st.rindex(")")
            f_ = st[rp + 2:].split()
            d[pid] = int(f_[11]) + int(f_[12])
        except (OSError, ValueError):
            pass
    return d


def non_autoware_load(seconds: float = 3.0):
    """CPU% (sum over cores) of processes that are not part of Autoware or this runner."""
    hz = os.sysconf("SC_CLK_TCK")
    a = proc_cpu_snapshot()
    time.sleep(seconds)
    b = proc_cpu_snapshot()
    aw = set(autoware_pids())
    tot = 0.0
    top = []
    for pid, v in b.items():
        if pid in aw or pid == os.getpid():
            continue
        d = (v - a.get(pid, v)) * 100.0 / hz / seconds
        if d > 0.5:
            cl = read_cmdline(pid)
            top.append((round(d, 1), pid, " ".join(cl)[:80] if cl else "?"))
        tot += d
    top.sort(reverse=True)
    return round(tot, 1), top[:8]


class Monitor:
    """rclpy node: counts messages on the health topics (raw subscriptions), tracks the
    localization / routing state and publishes the goal."""

    def __init__(self, topics):
        import rclpy
        from rclpy.node import Node
        from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
        from rosidl_runtime_py.utilities import get_message
        from geometry_msgs.msg import PoseStamped
        self.rclpy = rclpy
        rclpy.init(args=None)
        self.node: Node = rclpy.create_node("ipoint_replay_monitor")
        self.counts = {t: 0 for t in topics}
        self.first = {}
        self.last = {}
        self.lock = threading.Lock()
        self.init_state = None
        self.route_state = None
        self.subs = []
        self.pending = list(topics)
        self.be = QoSProfile(depth=10, reliability=QoSReliabilityPolicy.BEST_EFFORT)
        self.get_message = get_message
        self._subscribe_pending()
        # topics advertised later (e.g. by nodes that finish loading their map) are picked up here
        self.retry_timer = self.node.create_timer(2.0, self._subscribe_pending)
        tl = QoSProfile(depth=1, reliability=QoSReliabilityPolicy.RELIABLE,
                        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        from autoware_adapi_v1_msgs.msg import LocalizationInitializationState, RouteState
        self.subs.append(self.node.create_subscription(LocalizationInitializationState, "/localization/initialization_state",
                                                       self._init_cb, tl))
        self.subs.append(self.node.create_subscription(RouteState, "/api/routing/state", self._route_cb, tl))
        self.goal_pub = self.node.create_publisher(PoseStamped, "/planning/mission_planning/goal", 1)
        self.PoseStamped = PoseStamped
        self.thread = threading.Thread(target=rclpy.spin, args=(self.node,), daemon=True)
        self.thread.start()

    def _subscribe_pending(self):
        if not self.pending:
            return
        types = dict(self.node.get_topic_names_and_types())
        for t in list(self.pending):
            if t in types:
                mt = self.get_message(types[t][0])
                self.subs.append(self.node.create_subscription(mt, t, self._counter(t), self.be, raw=True))
                self.pending.remove(t)

    def _counter(self, t):
        def cb(_msg):
            with self.lock:
                self.counts[t] += 1
                ts = now()
                self.first.setdefault(t, ts)
                self.last[t] = ts
        return cb

    def _init_cb(self, msg):
        self.init_state = int(msg.state)

    def _route_cb(self, msg):
        self.route_state = int(msg.state)

    def publish_goal(self):
        m = self.PoseStamped()
        m.header.frame_id = "map"
        m.pose.position.x, m.pose.position.y = GOAL_POSE["x"], GOAL_POSE["y"]
        m.pose.orientation.z, m.pose.orientation.w = GOAL_POSE["qz"], GOAL_POSE["qw"]
        self.goal_pub.publish(m)

    def snapshot(self):
        with self.lock:
            return dict(self.counts), dict(self.first), dict(self.last)

    def missing_topics(self):
        return list(self.pending)

    def close(self):
        try:
            self.node.destroy_node()
            self.rclpy.shutdown()
        except Exception:
            pass


class Replay:
    def __init__(self, a, spec, k: int, out_dir: str, log):
        self.a, self.spec, self.k, self.dir, self.log = a, spec, k, out_dir, log
        self.timeline = {}
        self.result = {"index": k, "accepted": False, "reasons": []}
        self.procs = []
        self.sampler = None

    def stamp(self, name):
        self.timeline[name] = now()
        self.log(f"[replay {self.k}] {name} (+{self.timeline[name] - self.timeline.get('launch_start', self.timeline[name]):.1f}s)")

    def popen(self, cmd, logname, env):
        f = open(os.path.join(self.dir, logname), "w")
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self.procs.append((p, f))
        return p

    def wait_topics(self, needed, timeout):
        t0 = now()
        while now() - t0 < timeout:
            r = subprocess.run(["ros2", "topic", "list"], capture_output=True, text=True)
            have = set(r.stdout.split())
            if all(t in have for t in needed):
                return True
            time.sleep(2)
        return False

    def run(self):
        a, spec = self.a, self.spec
        ip_dir = os.path.join(self.dir, "ipoint")
        os.makedirs(ip_dir, exist_ok=True)
        env = dict(os.environ)
        env["IPOINT_OUT_DIR"] = ip_dir
        env.setdefault("IPOINT_BUF_RECORDS", str(a.buf_records))
        load, top = non_autoware_load(2.0)
        self.result["non_autoware_load_before"] = {"cpu_pct": load, "top": top}
        if not a.no_pin and not a.no_confine:
            moved, failed = confine_user_processes(a.rest_core_list)
            self.result["user_processes_confined"] = {"moved": moved, "failed": failed}
            self.log(f"[replay {self.k}] confined {moved} processes of this user to cores {a.rest_cores} ({failed} failed)")
        self.result["target_core_load_before"] = core_load(a.target_core_list, 2.0)
        self.stamp("launch_start")
        # start-up and localization initialization use every core; the partition
        # (targets on their cores, the rest on --rest-cores) is applied once initialized
        all_cores = list(range(os.cpu_count()))
        if not a.no_pin:
            os.sched_setaffinity(0, all_cores)
        launch = self.popen(["ros2", "launch", "autoware_launch", "logging_simulator.launch.xml",
                             f"map_path:={a.map}", "vehicle_model:=sample_vehicle", "sensor_model:=sample_sensor_kit",
                             "rviz:=false", f"sigterm_timeout:={a.sigterm_timeout}", f"sigkill_timeout:={a.sigkill_timeout}"],
                            "launch.log", env)
        if not a.no_pin:
            os.sched_setaffinity(0, a.rest_core_list)
        try:
            if not self.wait_topics(["/localization/initialization_state", "/api/routing/state"], a.launch_timeout):
                self.result["reasons"].append("launch_timeout")
                return self.result
            self.stamp("launch_ready")
            time.sleep(3.0)
            # pin the instrumented processes
            pids = {}
            for name, ps in spec["processes"].items():
                hits = match_process(ps["match"])
                pids[name] = hits
                if not a.no_pin and not ps["pin_after_init"] and ps["cores"] and not ps["init_cores"]:
                    for pid in hits:
                        n = pin(pid, ps["cores"])
                        self.log(f"[replay {self.k}] pinned {name} pid {pid} ({n} threads) to cores {ps['cores']}")
                if not a.no_pin and ps["init_cores"]:
                    for pid in hits:
                        n = pin(pid, ps["init_cores"])
                        self.log(f"[replay {self.k}] pinned {name} pid {pid} ({n} threads) to cores {ps['init_cores']} for the initialization")
                if len(hits) != 1:
                    self.result["reasons"].append(f"{name}: {len(hits)} matching processes")
            self.result["pids"] = pids
            mon = Monitor(list(COUNT_TOPICS))
            sampler = None
            time.sleep(2.0)
            cpu0 = cpu_snapshot()
            self.stamp("play_start")
            play = self.popen(["ros2", "bag", "play", a.bag, "-r", str(a.rate), "-s", "sqlite3"], "play.log", env)
            # localization initialization
            init_ok = False
            while play.poll() is None:
                if mon.init_state == 3:
                    init_ok = True
                    break
                time.sleep(0.5)
            self.stamp("init_done")
            init_s = self.timeline["init_done"] - self.timeline["play_start"]
            self.result["init_ok"] = init_ok
            self.result["init_s"] = round(init_s, 2)
            if not init_ok:
                self.result["reasons"].append("localization_not_initialized")
            elif init_s > a.init_timeout / a.rate:
                self.result["reasons"].append(f"localization initialized after {init_s:.1f} s > {a.init_timeout / a.rate:.1f} s")
            if init_ok and not a.no_pin:
                for name, ps in spec["processes"].items():
                    if (ps["pin_after_init"] or ps["init_cores"]) and ps["cores"]:
                        for pid in pids.get(name, []):
                            n = pin(pid, ps["cores"])
                            self.log(f"[replay {self.k}] pinned {name} pid {pid} ({n} threads) to cores {ps['cores']} (after init)")
                # unpinned targets (empty core list) stay with the rest of the stack
                targets = {pid for name, hits in pids.items() if spec["processes"][name]["cores"] for pid in hits}
                rest = [pid for pid in autoware_pids() if pid not in targets]
                for pid in rest:
                    pin(pid, a.rest_core_list)  # includes the init_cores processes without measurement cores
                self.log(f"[replay {self.k}] confined {len(rest)} other processes to cores {a.rest_cores}")
                self.result["rest_pids"] = len(rest)
                if not a.no_confine:
                    confine_user_processes(a.rest_core_list, exclude=set(autoware_pids()))
                sampler = ForeignSampler(a.target_core_list, autoware_pids())
                sampler.start()
            self.result["affinity"] = {name: [sorted(os.sched_getaffinity(pid)) for pid in hits if os.path.exists(f"/proc/{pid}")]
                                       for name, hits in pids.items() if hits}
            route_ok = False
            if init_ok:
                for _ in range(20):
                    mon.publish_goal()
                    if "goal_published" not in self.timeline:
                        self.stamp("goal_published")
                    for _ in range(4):
                        time.sleep(0.5)
                        if mon.route_state == 2:
                            route_ok = True
                            break
                    if route_ok or play.poll() is not None:
                        break
                self.stamp("route_set")
            self.result["route_ok"] = route_ok
            if not route_ok:
                self.result["reasons"].append("route_not_set")
            # wait for the end of the bag
            deadline = self.timeline["play_start"] + a.bag_duration / a.rate + 60
            while play.poll() is None and now() < deadline:
                time.sleep(1.0)
            if play.poll() is None:
                self.result["reasons"].append("play_timeout")
                os.killpg(play.pid, signal.SIGINT)
            self.stamp("play_end")
            cpu1 = cpu_snapshot()
            tot, idle = cpu1[0] - cpu0[0], cpu1[1] - cpu0[1]
            self.result["cpu_util_pct_during_play"] = round(100.0 * (tot - idle) / tot, 1) if tot else None
            if sampler is not None:
                fs = sampler.stop()
                self.result["foreign_on_target_cores"] = fs
                iso_n = max(1, fs["samples"] * max(1, len(sampler.iso_cores)))
                frac = fs["hits_isolated"] / iso_n
                self.result["foreign_fraction"] = round(frac, 4)
                if frac > a.max_foreign_fraction:
                    self.result["reasons"].append(f"foreign threads runnable on the isolated target cores in {100 * frac:.1f}% of core-samples ({fs['top'][:3]})")
            time.sleep(1.0)
            counts, first, last = mon.snapshot()
            mon.close()
            self.result["counts"] = counts
            self.result["topics_never_seen"] = mon.missing_topics()
            self.result["count_first_s"] = {t: round(first[t] - self.timeline["play_start"], 2) for t in first}
            self.result["count_last_s"] = {t: round(last[t] - self.timeline["play_start"], 2) for t in last}
            with open(os.path.join(self.dir, "counts.json"), "w") as f:
                json.dump({"counts": counts, "first_s": self.result["count_first_s"], "last_s": self.result["count_last_s"]}, f, indent=1)
            # the count thresholds were calibrated at real-time rate (pilot replays)
            if a.rate == 1.0:
                for t, (mn, cb) in COUNT_TOPICS.items():
                    c = counts.get(t, 0)
                    if c < mn:
                        self.result["reasons"].append(f"count {t} = {c} < {mn}")
            cc = counts.get("/sensing/lidar/concatenated/pointcloud", 0)
            if cc > CONCAT_MAX:
                self.result["reasons"].append(f"concatenated pointcloud count {cc} > {CONCAT_MAX}")
        finally:
            # graceful shutdown: release the pinning, SIGINT to the launch process group, then wait
            self.stamp("shutdown_start")
            all_cores = list(range(os.cpu_count()))
            for pid in autoware_pids():
                try:
                    pin(pid, all_cores)
                except OSError:
                    pass
            try:
                os.kill(launch.pid, signal.SIGINT)  # launch forwards one SIGINT to every child
            except ProcessLookupError:
                pass
            t0 = now()
            while now() - t0 < a.shutdown_timeout:
                if launch.poll() is not None and not autoware_pids():
                    break
                time.sleep(1.0)
            self.result["shutdown_s"] = round(now() - t0, 1)
            left = autoware_pids()
            if left:
                self.result["reasons"].append(f"{len(left)} processes left after SIGINT, killed")
                for pid in left:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                time.sleep(2.0)
            for p, f in self.procs:
                try:
                    p.wait(timeout=5)
                except Exception:
                    pass
                f.close()
            self.stamp("teardown_done")
        # traces of every instrumented process
        metas = {}
        for name, hits in self.result.get("pids", {}).items():
            for pid in hits:
                ms = glob.glob(os.path.join(ip_dir, f"*_{pid}.meta.json"))
                if not ms:
                    bins = glob.glob(os.path.join(ip_dir, f"*_{pid}_*.bin"))
                    self.result["reasons"].append(f"{name}: no meta.json for pid {pid} ({len(bins)} trace files, "
                                                  f"{sum(os.path.getsize(b) for b in bins) // 16} records)")
                    continue
                with open(ms[0]) as f:
                    m = json.load(f)
                ov = sum(t["overflow"] for t in m["threads"])
                fij = sum(t["flush_in_job"] for t in m["threads"])
                metas[name] = {"pid": pid, "jobs_total": m["jobs_total"], "records": sum(t["records"] for t in m["threads"]),
                               "overflow": ov, "flush_in_job": fij, "threads": len(m["threads"]), "tsc_hz": m.get("tsc_hz")}
                if ov:
                    self.result["reasons"].append(f"{name}: {ov} records overflowed")
                if m["jobs_total"] and metas[name]["records"] / m["jobs_total"] > a.max_records_per_job:
                    self.result["reasons"].append(f"{name}: {metas[name]['records'] / m['jobs_total']:.0f} records per job > {a.max_records_per_job} (exclude the per-element loops)")
                if m["jobs_total"] == 0:
                    self.result["reasons"].append(f"{name}: no jobs recorded")
        self.result["traces"] = metas
        self.result["timeline"] = {k: round(v - self.timeline["launch_start"], 2) for k, v in self.timeline.items()}
        self.result["wall_s"] = round(now() - self.timeline["launch_start"], 1)
        self.result["accepted"] = not self.result["reasons"]
        return self.result


def load_spec(path):
    with open(path) as f:
        spec = json.load(f)
    procs = {}
    for name, ps in spec["processes"].items():
        pg = ps["pgrep"]
        if name == "cb5":
            match = ["__node:=pointcloud_container", "=__ns:=/"]
        elif pg.startswith("__node:="):
            match = ["=" + pg]
        else:
            match = [pg]
        procs[name] = {"match": ps.get("match", match), "cores": ps["cores"], "packages": ps["packages"],
                       "pin_after_init": bool(ps.get("pin_after_init", False)), "init_cores": ps.get("init_cores", [])}
    spec["processes"] = procs
    return spec


def git_head(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rate", type=float, default=1.0)
    ap.add_argument("--min-replays", type=int, default=470)
    ap.add_argument("--min-samples", type=float, default=1e5, help="nominal samples (topic-count proxy) per callback")
    ap.add_argument("--max-replays", type=int, default=100000)
    ap.add_argument("--rest-cores", default="0-5,10-11", help="cores of the runner, the bag player and the rest of the stack (incl. unpinned targets)")
    ap.add_argument("--no-pin", action="store_true")
    ap.add_argument("--map", default=os.path.expanduser("~/autoware_map/sample-map-rosbag"))
    ap.add_argument("--bag", default=os.path.expanduser("~/autoware_map/sample-rosbag"))
    ap.add_argument("--bag-duration", type=float, default=29.9)
    ap.add_argument("--targets", default=os.path.join(AW, "targets.json"))
    ap.add_argument("--ws", default=os.path.expanduser("~/autoware"))
    ap.add_argument("--idle-load", type=float, default=10.0, help="max CPU%% of non-Autoware processes before a replay")
    ap.add_argument("--idle-wait", type=float, default=600.0, help="seconds to wait for the machine to become idle")
    ap.add_argument("--launch-timeout", type=float, default=180.0)
    ap.add_argument("--init-timeout", type=float, default=16.0, help="max accepted localization initialization time after play start (s)")
    ap.add_argument("--shutdown-timeout", type=float, default=150.0)
    # Autoware's motion_planning_container ignores SIGINT and only dies (SIGSEGV) on SIGTERM;
    # the instrumented processes exit on SIGINT within seconds and flush continuously anyway
    ap.add_argument("--sigterm-timeout", type=float, default=10.0)
    ap.add_argument("--sigkill-timeout", type=float, default=10.0)
    ap.add_argument("--buf-records", type=int, default=1 << 20)
    ap.add_argument("--max-records-per-job", type=float, default=50000, help="trace volume guard per callback invocation")
    ap.add_argument("--no-confine", action="store_true", help="do not move this user's other processes (desktop) to --rest-cores")
    ap.add_argument("--target-idle", type=float, default=5.0, help="max busy %% of a target core before a replay (foreign activity)")
    ap.add_argument("--max-foreign-fraction", type=float, default=0.02, help="reject a replay when foreign runnable threads were seen on the target cores in more than this fraction of core-samples")
    ap.add_argument("--max-consecutive-failures", type=int, default=3)
    a = ap.parse_args(argv)

    if "AMENT_PREFIX_PATH" not in os.environ:
        sys.exit("source the Autoware workspace (install/setup.bash) first")
    rest = parse_cores(a.rest_cores)
    a.rest_core_list = rest
    if not a.no_pin:
        os.sched_setaffinity(0, rest)
    spec = load_spec(a.targets)
    a.target_core_list = sorted({c for ps in spec["processes"].values() for c in ps["cores"]})
    os.makedirs(a.out, exist_ok=True)
    logf = open(os.path.join(a.out, "campaign.log"), "a")

    def log(msg):
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, file=sys.stderr, flush=True)
        logf.write(line + "\n")
        logf.flush()

    # resume
    done = []
    for d in sorted(glob.glob(os.path.join(a.out, "replay_[0-9]*"))):
        if os.path.exists(os.path.join(d, "replay.json")):
            with open(os.path.join(d, "replay.json")) as f:
                done.append(json.load(f))
        elif os.path.isdir(d) and not d.endswith(".incomplete"):
            shutil.move(d, d + ".incomplete")
            log(f"set aside incomplete {d}")
    k = max([r["index"] for r in done], default=-1) + 1
    camp_path = os.path.join(a.out, "campaign.json")
    if not os.path.exists(camp_path):
        sysinfo = {}
        try:
            sysinfo = json.loads(subprocess.run([os.path.join(IPOINT, "tools", "sysinfo.sh")], capture_output=True, text=True).stdout or "{}")
        except Exception as e:  # noqa: BLE001
            sysinfo = {"error": str(e)}
        camp = {"args": vars(a), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "sysinfo": sysinfo,
                "processes": spec["processes"], "count_topics": {t: v for t, v in COUNT_TOPICS.items()},
                "commits": {r: git_head(os.path.join(a.ws, "src", r)) for r in ("core/autoware_core", "universe/autoware_universe", "launcher/autoware_launch")},
                "cpu_boost": open("/sys/devices/system/cpu/cpufreq/boost").read().strip() if os.path.exists("/sys/devices/system/cpu/cpufreq/boost") else None,
                "isolated_cpus": isolated_cpus(), "target_cores": a.target_core_list, "rest_cores": rest,
                "irqs_on_target_cores": irqs_on_cores(a.target_core_list),
                "cpu_khz": open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read().strip() if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq") else None}
        with open(camp_path, "w") as f:
            json.dump(camp, f, indent=1)

    def progress():
        acc = [r for r in done if r["accepted"]]
        samples = {}
        for r in acc:
            for t, (mn, cb) in COUNT_TOPICS.items():
                if cb:
                    samples[cb] = samples.get(cb, 0) + r.get("counts", {}).get(t, 0)
        return acc, samples

    consecutive = 0
    while True:
        acc, samples = progress()
        with open(camp_path) as f:
            camp = json.load(f)
        camp["progress"] = {"replays": len(done), "accepted": len(acc), "samples": samples,
                            "updated": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(camp_path, "w") as f:
            json.dump(camp, f, indent=1)
        enough = len(acc) >= a.min_replays and all(v >= a.min_samples for v in samples.values()) and samples
        if enough or len(done) >= a.max_replays:
            log(f"done: {len(acc)} accepted replays, samples {samples}")
            break
        if autoware_pids():
            log("Autoware processes are still running; waiting")
            time.sleep(10)
            continue
        # the target cores must be idle before a replay (the rest cores may be busy with the desktop)
        if not a.no_confine and not a.no_pin:
            moved, failed = confine_user_processes(rest)
            if moved or failed:
                log(f"moved {moved} processes of this user to cores {a.rest_cores} ({failed} failed)")
        tl = core_load(a.target_core_list, 3.0)
        t_wait = now()
        while max(tl.values(), default=0.0) > a.target_idle and now() - t_wait < a.idle_wait:
            load, top = non_autoware_load(2.0)
            log(f"target cores busy {tl} (> {a.target_idle}%; non-Autoware load {load}%: {top[:3]}); waiting")
            time.sleep(30)
            tl = core_load(a.target_core_list, 3.0)
        d = os.path.join(a.out, f"replay_{k:04d}")
        os.makedirs(d, exist_ok=True)
        rep = Replay(a, spec, k, d, log)
        try:
            res = rep.run()
        except Exception as e:  # noqa: BLE001
            res = rep.result
            res["reasons"].append(f"exception: {e!r}")
            for pid in autoware_pids():
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        with open(os.path.join(d, "replay.json"), "w") as f:
            json.dump(res, f, indent=1)
        done.append(res)
        log(f"replay {k}: {'ACCEPTED' if res['accepted'] else 'REJECTED ' + '; '.join(res['reasons'])} "
            f"({res.get('wall_s')} s, counts {res.get('counts', {}).get('/control/trajectory_follower/control_cmd')} ctrl / "
            f"{res.get('counts', {}).get('/localization/kinematic_state')} odom)")
        consecutive = 0 if res["accepted"] else consecutive + 1
        if consecutive >= a.max_consecutive_failures:
            log(f"{consecutive} consecutive rejected replays; stopping")
            return 2
        k += 1
        time.sleep(3.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
