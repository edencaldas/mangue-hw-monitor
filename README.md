# Hardware Telemetry Monitoring Guide

This guide explains how to use the `mangue_monitor_gpu.py` and `mangue_monitor_cpu.py` scripts to collect high-resolution CPU and GPU logs. Both scripts are designed to flush data immediately to disk (`fsync`), ensuring that the telemetry survives sudden hardware lockups or power cuts.

---

## 🛠️ Step-by-Step Execution

To monitor both CPU and GPU metrics in real-time, open two separate terminal tabs or windows in the troubleshooting directory and execute the scripts:

### 1. Start the GPU Monitor (Tab 1)
```bash
./mangue_monitor_gpu.py
```
* **Telemetry tracked:** GPU Power Draw (W), Edge Temperature (°C), Junction Temperature (°C), Memory Temperature (°C), Fan Speed (RPM), and GFX Core Frequency (MHz).
* **Disk log file:** `gpu_monitor_log.csv`

### 2. Start the CPU Monitor (Tab 2)
```bash
./mangue_monitor_cpu.py
```
* **Telemetry tracked:** Average CPU Load (%), Core Temperatures (`Tctl` and `Tccd` in °C), Average Core Frequency (MHz), and individual core load percentages for all 12 threads.
* **Disk log file:** `cpu_monitor_log.csv`

---

## 📊 Console Layout Breakdown

### GPU Telemetry Console
The GPU monitor displays columns for:
* **Power (W):** Real-time board power draw.
* **Edge (°C):** Outer temperature of the silicon.
* **Junct (°C):** Temperature at the hottest spot on the GPU die (junction temp).
* **Mem (°C):** GPU VRAM temperature.
* **Fan (RPM):** Rotational fan speed.
* **GFX (MHz):** Core graphics clock speed.

### CPU Telemetry Console
The CPU monitor displays columns for:
* **Avg Load:** System-wide CPU utilization percentage.
* **Tctl (°C):** Main CPU temperature control signal.
* **Tccd (°C):** Individual Core Complex Die temperature.
* **Avg Freq (MHz):** Average clock speed across all logical threads.
* **Core Loads:** A compact visual string representing load on each of the 12 logical threads (e.g. `[003509*00115]`).
  * `0` to `9` representing `0-9%` through `90-99%` load.
  * `*` representing a fully loaded thread (`100%`).

---

## 🔍 Log Analysis After a Crash

If the computer crashes or powers off while gaming, reboot the system and inspect the final 10 lines of both log files:

```bash
# View last entries of the GPU log
tail -n 10 gpu_monitor_log.csv

# View last entries of the CPU log
tail -n 10 cpu_monitor_log.csv
```

### Common Troubleshooting Scenarios:

1. **Power Supply Failure (OCP/OPP Trip):**
   * *Log Signature:* Temperatures are completely safe (e.g., CPU < 80°C, GPU Junction < 90°C), GPU power is high (near max TDP), and the log simply stops dead in the middle of load.
   * *Verdict:* The PSU cut power instantly to protect against a transient power draw spike.

2. **CPU Thermal Shutdown:**
   * *Log Signature:* `Tctl` or `Tccd` rises past **95°C–105°C** in the final seconds of the CPU log before it cuts out.
   * *Verdict:* The system shutdown was triggered by CPU overheating (e.g., dry thermal paste or loose heatsink).

3. **GPU Thermal Shutdown:**
   * *Log Signature:* GPU `Junct` temp exceeds **110°C** or `Mem` temp exceeds **105°C** right before the log ends.
   * *Verdict:* The GPU turned itself off to protect its silicon.

4. **Silicon/Driver Hang (PC stays powered, but screen goes black):**
   * *Log Signature:* Clock speeds (`GFX` / `Avg Freq`) drop to `0` or near `0` while load is high, and the log continues to record for a few seconds before stopping or being manually shut down.
   * *Verdict:* The graphics driver or card VRM crashed, but the system remained powered.
