# System Monitor Dashboard

Terminal-based system monitor for Raspberry Pi and Linux. Displays CPU, memory, temperature, load, uptime, and network throughput in real time.

## Requirements

- Python 3.8+
- Linux with `/proc` and `/sys`

## Run

```bash
python3 monitor.py
```

Press `q` to quit.

## Remote Pi (SSH)

This dashboard expects passwordless SSH using an SSH key. The default target is `b@192.168.68.68`.

```bash
ssh -i /home/bruno/.ssh/id_ed25519_pi_monitor b@192.168.68.68
```

If you need to override defaults, set:

- `PI_MONITOR_REMOTE_HOST`
- `PI_MONITOR_REMOTE_USER`
- `PI_MONITOR_REMOTE_KEY`

## Notes

- Temperature reads from `/sys/class/thermal/thermal_zone0/temp` or `/sys/class/hwmon/hwmon0/temp1_input`.
- Network stats aggregate all interfaces from `/proc/net/dev`.
