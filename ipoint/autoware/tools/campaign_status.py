#!/usr/bin/env python3
"""Progress of a replay campaign: accepted/rejected replays, nominal samples per
callback (topic-count proxies), wall time per replay, rejection reasons.

    campaign_status.py --campaign traces/autoware [--last 5]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--last", type=int, default=5)
    a = ap.parse_args(argv)
    reps = []
    for d in sorted(glob.glob(os.path.join(a.campaign, "replay_[0-9]*"))):
        p = os.path.join(d, "replay.json")
        if os.path.exists(p):
            with open(p) as f:
                reps.append(json.load(f))
    camp = {}
    if os.path.exists(os.path.join(a.campaign, "campaign.json")):
        with open(os.path.join(a.campaign, "campaign.json")) as f:
            camp = json.load(f)
    acc = [r for r in reps if r.get("accepted")]
    rej = [r for r in reps if not r.get("accepted")]
    print(f"{len(reps)} replays: {len(acc)} accepted, {len(rej)} rejected; started {camp.get('started')}, boost={camp.get('cpu_boost')} cur_khz={camp.get('cpu_khz')}")
    prog = camp.get("progress", {})
    if prog:
        print("samples (topic proxies):", prog.get("samples"), "updated", prog.get("updated"))
    if acc:
        walls = [r["wall_s"] for r in acc if r.get("wall_s")]
        inits = [r["init_s"] for r in acc if r.get("init_s") is not None]
        print(f"wall per accepted replay: mean {sum(walls)/len(walls):.0f} s (min {min(walls):.0f}, max {max(walls):.0f}); init mean {sum(inits)/len(inits):.1f} s")
        recs = collections.defaultdict(int)
        for r in acc:
            for cb, t in r.get("traces", {}).items():
                recs[cb] += t.get("records", 0)
        print("trace records per callback:", {k: f"{v/1e6:.1f}M" for k, v in sorted(recs.items())})
    reasons = collections.Counter()
    for r in rej:
        for x in r.get("reasons", []):
            reasons[x.split(" = ")[0].split(":")[0]] += 1
    if reasons:
        print("rejection reasons:", dict(reasons.most_common(8)))
    for r in reps[-a.last:]:
        print(f"  replay {r['index']:4d} {'ACC' if r.get('accepted') else 'REJ'} wall {r.get('wall_s')} init {r.get('init_s')} "
              f"ctrl {r.get('counts', {}).get('/control/trajectory_follower/control_cmd')} {('; '.join(r.get('reasons', []))[:100])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
