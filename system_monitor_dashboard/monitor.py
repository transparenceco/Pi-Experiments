#!/usr/bin/env python3
import curses
import json
import os
import shutil
import subprocess
import time


REMOTE_HOST = os.environ.get("PI_MONITOR_REMOTE_HOST", "192.168.68.68")
REMOTE_USER = os.environ.get("PI_MONITOR_REMOTE_USER", "b")
REMOTE_KEY = os.environ.get(
    "PI_MONITOR_REMOTE_KEY", "/home/bruno/.ssh/id_ed25519_pi_monitor"
)

SKIP_FS = {
    "proc",
    "sysfs",
    "tmpfs",
    "devtmpfs",
    "devpts",
    "overlay",
    "squashfs",
    "cgroup",
    "cgroup2",
    "pstore",
    "debugfs",
    "tracefs",
    "securityfs",
    "mqueue",
    "hugetlbfs",
    "configfs",
    "fusectl",
}

DISK_DEV_PREFIXES = ("sd", "nvme", "mmcblk")


def read_cpu_lines():
    lines = []
    with open("/proc/stat", "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("cpu"):
                break
            parts = line.strip().split()
            lines.append((parts[0], [int(p) for p in parts[1:]]))
    return lines


def cpu_usage(prev, curr):
    prev_idle = prev[3] + prev[4]
    curr_idle = curr[3] + curr[4]
    prev_total = sum(prev)
    curr_total = sum(curr)
    total_delta = curr_total - prev_total
    idle_delta = curr_idle - prev_idle
    if total_delta <= 0:
        return 0.0
    return (total_delta - idle_delta) / total_delta * 100.0


def read_meminfo():
    info = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, val = line.split(":", 1)
            info[key.strip()] = int(val.strip().split()[0])
    return info


def read_loadavg():
    with open("/proc/loadavg", "r", encoding="utf-8") as f:
        parts = f.read().strip().split()
    return parts[:3]


def read_uptime_seconds():
    with open("/proc/uptime", "r", encoding="utf-8") as f:
        return float(f.read().split()[0])


def read_net_bytes():
    data = {}
    with open("/proc/net/dev", "r", encoding="utf-8") as f:
        lines = f.readlines()[2:]
    for line in lines:
        if ":" not in line:
            continue
        iface, body = line.split(":", 1)
        parts = body.split()
        if len(parts) < 16:
            continue
        data[iface.strip()] = (int(parts[0]), int(parts[8]))
    return data


def read_diskstats():
    stats = {}
    with open("/proc/diskstats", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            name = parts[2]
            if not name.startswith(DISK_DEV_PREFIXES):
                continue
            read_sectors = int(parts[5])
            write_sectors = int(parts[9])
            stats[name] = (read_sectors, write_sectors)
    return stats


def list_mounts():
    mounts = []
    seen = set()
    with open("/proc/mounts", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            mount = parts[1]
            fstype = parts[2]
            if fstype in SKIP_FS:
                continue
            if mount in seen:
                continue
            seen.add(mount)
            mounts.append((mount, fstype))
    mounts.sort(key=lambda m: m[0])
    return mounts


def read_temps_c():
    temps = []
    base = "/sys/class/thermal"
    if os.path.isdir(base):
        for name in os.listdir(base):
            if not name.startswith("thermal_zone"):
                continue
            path = os.path.join(base, name, "temp")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                val = int(raw)
                temps.append(val / 1000.0 if val > 1000 else float(val))
            except (OSError, ValueError):
                continue
    if temps:
        return temps
    hwmon = "/sys/class/hwmon"
    if os.path.isdir(hwmon):
        for root, _, files in os.walk(hwmon):
            for name in files:
                if not name.startswith("temp") or not name.endswith("_input"):
                    continue
                path = os.path.join(root, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw = f.read().strip()
                    val = int(raw)
                    temps.append(val / 1000.0 if val > 1000 else float(val))
                except (OSError, ValueError):
                    continue
    return temps


def read_top_processes(sort_field, limit):
    cmd = ["ps", "-eo", "pid,comm,%cpu,%mem", "--sort", sort_field]
    try:
        out = subprocess.check_output(cmd, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    lines = out.strip().splitlines()[1 : limit + 1]
    procs = []
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, comm, cpu, mem = parts
        procs.append((pid, comm, cpu, mem))
    return procs


def collect_local_raw():
    return {
        "cpu_lines": read_cpu_lines(),
        "meminfo": read_meminfo(),
        "loadavg": read_loadavg(),
        "uptime": read_uptime_seconds(),
        "net_bytes": read_net_bytes(),
        "diskstats": read_diskstats(),
        "mounts": list_mounts(),
        "temps": read_temps_c(),
        "top_cpu": read_top_processes("-%cpu", 5),
        "top_mem": read_top_processes("-%mem", 5),
    }


def ssh_remote_raw():
    script = """
import json
import os
import shutil
import subprocess

SKIP_FS = {
    "proc",
    "sysfs",
    "tmpfs",
    "devtmpfs",
    "devpts",
    "overlay",
    "squashfs",
    "cgroup",
    "cgroup2",
    "pstore",
    "debugfs",
    "tracefs",
    "securityfs",
    "mqueue",
    "hugetlbfs",
    "configfs",
    "fusectl",
}
DISK_DEV_PREFIXES = ("sd", "nvme", "mmcblk")


def read_cpu_lines():
    lines = []
    with open("/proc/stat", "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("cpu"):
                break
            parts = line.strip().split()
            lines.append((parts[0], [int(p) for p in parts[1:]]))
    return lines


def read_meminfo():
    info = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        for line in f:
            key, val = line.split(":", 1)
            info[key.strip()] = int(val.strip().split()[0])
    return info


def read_loadavg():
    with open("/proc/loadavg", "r", encoding="utf-8") as f:
        parts = f.read().strip().split()
    return parts[:3]


def read_uptime_seconds():
    with open("/proc/uptime", "r", encoding="utf-8") as f:
        return float(f.read().split()[0])


def read_net_bytes():
    data = {}
    with open("/proc/net/dev", "r", encoding="utf-8") as f:
        lines = f.readlines()[2:]
    for line in lines:
        if ":" not in line:
            continue
        iface, body = line.split(":", 1)
        parts = body.split()
        if len(parts) < 16:
            continue
        data[iface.strip()] = (int(parts[0]), int(parts[8]))
    return data


def read_diskstats():
    stats = {}
    with open("/proc/diskstats", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10:
                continue
            name = parts[2]
            if not name.startswith(DISK_DEV_PREFIXES):
                continue
            read_sectors = int(parts[5])
            write_sectors = int(parts[9])
            stats[name] = (read_sectors, write_sectors)
    return stats


def list_mounts():
    mounts = []
    seen = set()
    with open("/proc/mounts", "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            mount = parts[1]
            fstype = parts[2]
            if fstype in SKIP_FS:
                continue
            if mount in seen:
                continue
            seen.add(mount)
            mounts.append((mount, fstype))
    mounts.sort(key=lambda m: m[0])
    return mounts


def read_temps_c():
    temps = []
    base = "/sys/class/thermal"
    if os.path.isdir(base):
        for name in os.listdir(base):
            if not name.startswith("thermal_zone"):
                continue
            path = os.path.join(base, name, "temp")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
                val = int(raw)
                temps.append(val / 1000.0 if val > 1000 else float(val))
            except (OSError, ValueError):
                continue
    if temps:
        return temps
    hwmon = "/sys/class/hwmon"
    if os.path.isdir(hwmon):
        for root, _, files in os.walk(hwmon):
            for name in files:
                if not name.startswith("temp") or not name.endswith("_input"):
                    continue
                path = os.path.join(root, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        raw = f.read().strip()
                    val = int(raw)
                    temps.append(val / 1000.0 if val > 1000 else float(val))
                except (OSError, ValueError):
                    continue
    return temps


def read_top_processes(sort_field, limit):
    cmd = ["ps", "-eo", "pid,comm,%cpu,%mem", "--sort", sort_field]
    try:
        out = subprocess.check_output(cmd, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    lines = out.strip().splitlines()[1 : limit + 1]
    procs = []
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, comm, cpu, mem = parts
        procs.append((pid, comm, cpu, mem))
    return procs


def disk_usage_for_mounts(mounts):
    usage = []
    for mount, fstype in mounts:
        try:
            total, used, _ = shutil.disk_usage(mount)
            usage.append((mount, fstype, total, used))
        except OSError:
            continue
    return usage


data = {
    "cpu_lines": read_cpu_lines(),
    "meminfo": read_meminfo(),
    "loadavg": read_loadavg(),
    "uptime": read_uptime_seconds(),
    "net_bytes": read_net_bytes(),
    "diskstats": read_diskstats(),
    "mounts": list_mounts(),
    "temps": read_temps_c(),
    "top_cpu": read_top_processes("-%cpu", 5),
    "top_mem": read_top_processes("-%mem", 5),
    "disk_usage": disk_usage_for_mounts(list_mounts()),
}
print(json.dumps(data))
"""

    cmd = [
        "ssh",
        "-i",
        REMOTE_KEY,
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=2",
        f"{REMOTE_USER}@{REMOTE_HOST}",
        "python3",
        "-",
    ]
    try:
        result = subprocess.run(
            cmd,
            input=script,
            text=True,
            capture_output=True,
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        return None, "ssh timeout"
    if result.returncode != 0:
        err = result.stderr.strip() or "ssh failed"
        return None, err
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, "invalid remote data"
    return data, None


def fmt_bytes(num):
    num = float(num)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}PB"


def fmt_duration(seconds):
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}h {mins:02d}m"
    return f"{hours:02d}h {mins:02d}m {secs:02d}s"


def draw_bar(value, width):
    value = max(0.0, min(100.0, value))
    filled = int(round(value / 100.0 * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def safe_addstr(stdscr, y, x, text):
    try:
        stdscr.addstr(y, x, text)
    except curses.error:
        pass


def compute_metrics(raw, prev, now):
    metrics = {}
    cpu_lines = raw.get("cpu_lines", [])
    if prev and prev.get("cpu_lines"):
        cpu_pcts = []
        for (name, curr), (_, prev_vals) in zip(cpu_lines, prev["cpu_lines"]):
            cpu_pcts.append((name, cpu_usage(prev_vals, curr)))
        metrics["cpu_pcts"] = cpu_pcts
    else:
        metrics["cpu_pcts"] = [(name, 0.0) for name, _ in cpu_lines]

    meminfo = raw.get("meminfo", {})
    mem_total = meminfo.get("MemTotal", 0) * 1024
    mem_avail = meminfo.get("MemAvailable", meminfo.get("MemFree", 0)) * 1024
    mem_used = max(mem_total - mem_avail, 0)
    swap_total = meminfo.get("SwapTotal", 0) * 1024
    swap_free = meminfo.get("SwapFree", 0) * 1024
    swap_used = max(swap_total - swap_free, 0)

    metrics["mem_total"] = mem_total
    metrics["mem_used"] = mem_used
    metrics["swap_total"] = swap_total
    metrics["swap_used"] = swap_used

    metrics["loadavg"] = raw.get("loadavg", ["0.00", "0.00", "0.00"])
    metrics["uptime"] = raw.get("uptime", 0.0)
    metrics["temps"] = raw.get("temps", [])

    net_rates = {}
    if prev and prev.get("net_bytes"):
        delta = max(now - prev.get("time", now), 0.001)
        for iface, (rx, tx) in raw.get("net_bytes", {}).items():
            prev_rx, prev_tx = prev["net_bytes"].get(iface, (rx, tx))
            net_rates[iface] = ((rx - prev_rx) / delta, (tx - prev_tx) / delta)
    metrics["net_rates"] = net_rates

    disk_rates = {}
    if prev and prev.get("diskstats"):
        delta = max(now - prev.get("time", now), 0.001)
        for dev, (rsec, wsec) in raw.get("diskstats", {}).items():
            prev_r, prev_w = prev["diskstats"].get(dev, (rsec, wsec))
            disk_rates[dev] = (
                (rsec - prev_r) * 512.0 / delta,
                (wsec - prev_w) * 512.0 / delta,
            )
    metrics["disk_rates"] = disk_rates

    if "disk_usage" in raw:
        metrics["disk_usage"] = raw.get("disk_usage", [])
    else:
        usage = []
        for mount, fstype in raw.get("mounts", []):
            try:
                total, used, _ = shutil.disk_usage(mount)
                usage.append((mount, fstype, total, used))
            except OSError:
                continue
        metrics["disk_usage"] = usage

    metrics["top_cpu"] = raw.get("top_cpu", [])
    metrics["top_mem"] = raw.get("top_mem", [])

    return metrics


def build_panel_lines(metrics, title, width):
    lines = []
    lines.append(title)

    cpu_pcts = metrics.get("cpu_pcts", [])
    if cpu_pcts:
        total_pct = cpu_pcts[0][1]
        bar_width = max(8, min(30, width - 18))
        lines.append(f"CPU  {total_pct:5.1f}% {draw_bar(total_pct, bar_width)}")
        for name, pct in cpu_pcts[1:9]:
            lines.append(f"{name:4s} {pct:5.1f}%")
    else:
        lines.append("CPU  N/A")

    mem_total = metrics.get("mem_total", 0)
    mem_used = metrics.get("mem_used", 0)
    mem_pct = (mem_used / mem_total * 100.0) if mem_total else 0.0
    bar_width = max(8, min(30, width - 18))
    lines.append(
        f"MEM  {mem_pct:5.1f}% {draw_bar(mem_pct, bar_width)} {fmt_bytes(mem_used)} / {fmt_bytes(mem_total)}"
    )

    swap_total = metrics.get("swap_total", 0)
    swap_used = metrics.get("swap_used", 0)
    swap_pct = (swap_used / swap_total * 100.0) if swap_total else 0.0
    lines.append(
        f"SWAP {swap_pct:5.1f}% {draw_bar(swap_pct, bar_width)} {fmt_bytes(swap_used)} / {fmt_bytes(swap_total)}"
    )

    temps = metrics.get("temps", [])
    if temps:
        temps_text = ", ".join(f"{t:.1f}C" for t in temps[:3])
    else:
        temps_text = "N/A"
    lines.append(f"TEMP {temps_text}")

    load1, load5, load15 = metrics.get("loadavg", ["0.00", "0.00", "0.00"])
    lines.append(f"LOAD {load1} {load5} {load15}")
    lines.append(f"UPTIME {fmt_duration(metrics.get('uptime', 0.0))}")

    lines.append("NET")
    for iface, (rx, tx) in sorted(metrics.get("net_rates", {}).items())[:5]:
        lines.append(f"  {iface:8s} RX {fmt_bytes(rx)}/s TX {fmt_bytes(tx)}/s")

    lines.append("DISK USAGE")
    for mount, fstype, total, used in metrics.get("disk_usage", [])[:4]:
        pct = (used / total * 100.0) if total else 0.0
        lines.append(f"  {mount:10.10s} {pct:5.1f}% {fmt_bytes(used)} / {fmt_bytes(total)}")

    lines.append("DISK IO")
    for dev, (r_bps, w_bps) in sorted(metrics.get("disk_rates", {}).items())[:4]:
        lines.append(f"  {dev:8s} R {fmt_bytes(r_bps)}/s W {fmt_bytes(w_bps)}/s")

    lines.append("TOP CPU")
    for pid, comm, cpu, mem in metrics.get("top_cpu", [])[:3]:
        lines.append(f"  {pid:>5s} {comm[:10]:10s} {cpu:>5s}% {mem:>5s}%")

    lines.append("TOP MEM")
    for pid, comm, cpu, mem in metrics.get("top_mem", [])[:3]:
        lines.append(f"  {pid:>5s} {comm[:10]:10s} {cpu:>5s}% {mem:>5s}%")

    return [line[:width] for line in lines]


def render_panel(stdscr, lines, x, y, width, height):
    for i, line in enumerate(lines[:height]):
        safe_addstr(stdscr, y + i, x, line[:width])


def dashboard(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)

    prev_local = {}
    prev_remote = {}

    while True:
        now = time.time()
        local_raw = collect_local_raw()
        local_metrics = compute_metrics(local_raw, prev_local, now)
        prev_local = {
            "cpu_lines": local_raw.get("cpu_lines", []),
            "net_bytes": local_raw.get("net_bytes", {}),
            "diskstats": local_raw.get("diskstats", {}),
            "time": now,
        }

        remote_raw, remote_err = ssh_remote_raw()
        if remote_raw:
            remote_metrics = compute_metrics(remote_raw, prev_remote, now)
            prev_remote = {
                "cpu_lines": remote_raw.get("cpu_lines", []),
                "net_bytes": remote_raw.get("net_bytes", {}),
                "diskstats": remote_raw.get("diskstats", {}),
                "time": now,
            }
        else:
            remote_metrics = None

        stdscr.erase()
        height, width = stdscr.getmaxyx()

        title = "System Monitor Dashboard (press q to quit)"
        safe_addstr(stdscr, 0, 0, title[: width - 1])

        gap = 2
        col_width = (width - gap) // 2
        if col_width < 40:
            local_lines = build_panel_lines(local_metrics, "LOCAL", width - 1)
            render_panel(stdscr, local_lines, 0, 2, width - 1, height - 3)
            safe_addstr(stdscr, height - 1, 0, "Widen terminal for remote panel")
        else:
            local_lines = build_panel_lines(local_metrics, "LOCAL", col_width)
            render_panel(stdscr, local_lines, 0, 2, col_width, height - 3)

            if remote_metrics:
                remote_lines = build_panel_lines(remote_metrics, "REMOTE", col_width)
            else:
                remote_lines = ["REMOTE", f"Error: {remote_err or 'no data'}"]
            render_panel(
                stdscr, remote_lines, col_width + gap, 2, col_width, height - 3
            )

        safe_addstr(stdscr, height - 1, 0, f"Updated: {time.strftime('%H:%M:%S')}")
        stdscr.refresh()

        try:
            key = stdscr.getkey()
        except curses.error:
            key = None
        if key in ("q", "Q"):
            break

        time.sleep(0.5)


def main():
    curses.wrapper(dashboard)


if __name__ == "__main__":
    main()
