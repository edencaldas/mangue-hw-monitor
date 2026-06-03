# Hardware Telemetry Monitoring Guide

This guide explains how to use the `mangue_monitor_gpu.py` and `mangue_monitor_cpu.py` scripts to collect high-resolution CPU and GPU telemetry logs. Both scripts are designed to bypass system write caching and flush data immediately to disk (`fsync`), ensuring that data is saved up to the final second before a sudden hardware crash or power loss.

Both scripts automatically discover their active sensor and device paths dynamically in the `/sys` filesystem at startup, ensuring they work across different motherboard, driver, and GPU configurations.

---

## 🛠️ Step-by-Step Execution

To monitor both CPU and GPU metrics in real-time, open two separate terminal tabs or windows in the troubleshooting directory and execute:

### 1. Start the GPU Monitor (Tab 1)
```bash
./mangue_monitor_gpu.py
```
* **Telemetry tracked:** Board Power Draw (W), Core Graphics Voltage (V), Edge Temp (°C), Junction Temp (°C), VRAM Temp (°C), Fan Speed (RPM/%), GFX Core Frequency (MHz), VRAM Memory Clock Speed (MHz), VRAM Allocation (Used/Total MB), and GTT System Memory Allocation (Used/Total MB).
* **Disk log file:** `gpu_monitor_log.csv`

### 2. Start the CPU Monitor (Tab 2)
```bash
# Standard user run (Power and Volt will show N/A unless zenpower is loaded)
./mangue_monitor_cpu.py

# Root user run (unlocks real-time CPU Package Power via RAPL fallback!)
sudo ./mangue_monitor_cpu.py
```
* **Telemetry tracked:** Average CPU Load (%), Core Temperatures (`Tctl` and `Tccd` in °C), Average Core Frequency (MHz), Core Power (W), SVI2 Core Voltage (V), System RAM Allocation (Used/Total GB), Swap Allocation (Used/Total GB), and individual load percentages for all logical threads.
* **Disk log file:** `cpu_monitor_log.csv`

---

## 📊 Console Layout & Columns

### GPU Telemetry Console
* **Power (W):** Real-time board power consumption.
* **Volt (V):** Core graphics engine voltage (VDDGFX) in Volts (e.g. `0.875 V`).
* **Edge (°C):** Primary GPU package core temperature.
* **Junct (°C):** Silicon junction temperature (hottest spot on die). Displays `N/A` on older cards like the RX 550.
* **Mem (°C):** Graphic VRAM memory temperature. Displays `N/A` on older cards like the RX 550.
* **Fan (RPM/%):** Cooler rotational speed. Displays raw RPM if supported, falls back to PWM duty cycle percentage (e.g., `29%`) if the card's RPM tachometer sensor is unsupported/returns errors, and displays `N/A` for passively cooled or unmonitored cards.
* **GFX (MHz):** Core graphics engine clock speed (SCLK).
* **VRAM Clk (MHz):** Core graphics memory clock speed (MCLK).
* **VRAM (Used/Total):** Dedicated video memory usage in MB.
* **GTT (Used/Total):** Graphics Translation Table memory (shared RAM allocated to graphics) in MB.

### CPU Telemetry Console
* **Avg Load:** System-wide CPU utilization percentage.
* **Tctl (°C):** Main CPU thermal control sensor.
* **Tccd (°C):** Core Complex Die temperature.
* **Avg Freq (MHz):** Average real-time frequency across all threads.
* **Power (W):** CPU Package Power. Under normal users, it requires `zenpower`. **If run under `sudo`, the script uses the RAPL fallback** to read and calculate CPU Package Power dynamically.
* **Volt (V):** CPU Core SVI2 Voltage (requires the `zenpower` module; displays `N/A` under standard `k10temp` even with `sudo`).
* **RAM (Used/Total):** System RAM utilization in GB.
* **Core Loads:** Visual thread utilization indicator in brackets (e.g. `[003509*00115]` represents thread load from 0-9 scale, with `*` representing 100% load).

---

## 🚨 Color-Coded Thermal & Allocation Warnings

To make real-time monitoring easy to read, both scripts output ANSI color indicators on the console:
* **Bold Yellow:** Warns when hardware is getting hot or memory is filling up:
  * CPU `Tctl`/`Tccd` temp is $\ge 75^\circ\text{C}$
  * GPU `Edge` temp is $\ge 75^\circ\text{C}$
  * GPU `Junct`/`Mem` temp is $\ge 85^\circ\text{C}$
  * System RAM or VRAM allocation is $\ge 85\%$ of capacity
* **Bold Red:** Indicates critical thresholds near thermal throttling or exhaustion:
  * CPU `Tctl`/`Tccd` temp is $\ge 85^\circ\text{C}$
  * GPU `Edge` temp is $\ge 85^\circ\text{C}$
  * GPU `Junct`/`Mem` temp is $\ge 95^\circ\text{C}$
  * System RAM or VRAM allocation is $\ge 95\%$ of capacity

---

## 💾 Versioning & Schema Verification

Both scripts follow a 3-number **Semantic Versioning** scheme (`MAJOR.MINOR.PATCH`).
* The baseline feature-complete release is tagged **`0.1.0`**.
* The current script version is logged inside **every row** of the CSV log files in the second column (`script_version`). This ensures that if logs are shared, the producing code version is explicitly identifiable.
* **Automatic Schema Replacement:** If a script detects an existing log file with a mismatched header schema (e.g. from an older version), it will automatically delete and replace the old file with a fresh log containing the correct header layout to prevent data misalignment.

---

## 🔍 Log Analysis After a Crash

To diagnose a crash after rebooting, view the final 10 seconds of telemetry from both log files:

```bash
# Inspect final logs
tail -n 10 gpu_monitor_log.csv
tail -n 10 cpu_monitor_log.csv
```

### Common Diagnostic Signatures:

1. **Power Supply Cut (OCP/OPP Trip):**
   * *Log Signature:* CPU and GPU temperatures are low/safe, but GPU power was at maximum load, and the log files abruptly stop mid-entry.
   * *Verdict:* The PSU tripped its protection limit due to a transient power spike.

2. **CPU Thermal Throttling/Shutdown:**
   * *Log Signature:* CPU `Tctl` or `Tccd` rises past **$90^\circ\text{C}$–$100^\circ\text{C}$** (rendering in bold red on console) in the final seconds before logging terminates.
   * *Verdict:* High thermal stress due to heatsink contact issues.

3. **Memory Exhaustion (Out-of-Memory Lockup):**
   * *Log Signature:* System RAM or VRAM ratio reads at $\ge 98\%$ (rendering in bold red on console) before the log freezes.
   * *Verdict:* RAM/VRAM leak or overuse.
