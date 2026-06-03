#!/usr/bin/env python3
import time
import os
import sys

# Paths to sysfs attributes for amdgpu hwmon1
HWMON_DIR = "/sys/class/drm/card1/device/hwmon/hwmon1"
CSV_PATH = "gpu_monitor_log.csv"

def read_sysfs(filename, divisor=1):
    path = os.path.join(HWMON_DIR, filename)
    try:
        with open(path, 'r') as f:
            val = f.read().strip()
            return float(val) / divisor
    except Exception:
        return 0.0

def main():
    if not os.path.exists(HWMON_DIR):
        print(f"Error: HWMON directory not found: {HWMON_DIR}")
        print("Please check if your RX 7600 is currently running and using the amdgpu driver.")
        sys.exit(1)

    print(f"Starting GPU Telemetry Logger...")
    print(f"Writing to: {os.path.abspath(CSV_PATH)}")
    print("Press Ctrl+C to stop.")
    print("-" * 80)
    print(f"{'Time':19} | {'Power (W)':9} | {'Edge (°C)':9} | {'Junct (°C)':10} | {'Mem (°C)':8} | {'Fan (RPM)':9} | {'GFX (MHz)':9}")
    print("-" * 80)

    # Initialize CSV if it doesn't exist
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w') as f:
            f.write("timestamp,power_watts,edge_temp_c,junction_temp_c,memory_temp_c,fan_rpm,gfx_freq_mhz\n")

    try:
        while True:
            # Timestamp
            t_str = time.strftime("%Y-%m-%d %H:%M:%S")

            # Metrics
            # power1_average is in microwatts, convert to Watts
            power = read_sysfs("power1_average", 1000000)
            
            # Temps are in millidegrees C, convert to C
            temp_edge = read_sysfs("temp1_input", 1000)
            temp_junc = read_sysfs("temp2_input", 1000)
            temp_mem = read_sysfs("temp3_input", 1000)
            
            # Fan speed in RPM
            fan = read_sysfs("fan1_input")
            
            # Frequencies are in Hz, convert to MHz
            gfx_freq = read_sysfs("freq1_input", 1000000)

            # Print to console
            print(f"{t_str} | {power:9.2f} | {temp_edge:9.1f} | {temp_junc:10.1f} | {temp_mem:8.1f} | {fan:9.0f} | {gfx_freq:9.0f}")

            # Append to CSV and force flush to disk
            with open(CSV_PATH, 'a') as f:
                f.write(f"{t_str},{power:.2f},{temp_edge:.1f},{temp_junc:.1f},{temp_mem:.1f},{fan:.0f},{gfx_freq:.0f}\n")
                f.flush()
                os.fsync(f.fileno())  # Bypass OS page cache and force physical write to disk

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
