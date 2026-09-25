import glob, subprocess, time, datetime, sys
TARGET = {6, 7, 8, 9, 12, 13, 14, 15}
out_path = sys.argv[1]
def cores(s):
    out = set()
    for p in s.split(","):
        if not p:
            continue
        if "-" in p:
            a, b = p.split("-"); out |= set(range(int(a), int(b) + 1))
        else:
            out.add(int(p))
    return out
while True:
    n = t = 0
    for f in glob.glob("/proc/irq/*/smp_affinity_list"):
        try:
            lst = cores(open(f).read().strip())
        except Exception:
            continue
        t += 1; n += bool(lst & TARGET)
    ib = subprocess.run(["systemctl", "is-active", "irqbalance"], capture_output=True, text=True).stdout.strip()
    with open(out_path, "a") as out:
        out.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} irqs_on_target_cores={n}/{t} irqbalance={ib}\n")
    time.sleep(60)
