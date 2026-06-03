#!/usr/bin/env python3
import time
import os
import sys

CSV_PATH = "cpu_monitor_log.csv"

def find_k10temp_dir():
    # Scan hwmon directories to find k10temp dynamically
    base_dir = "/sys/class/hwmon"
    if not os.path.exists(base_dir):
        return None
    for hwmon in os.listdir(base_dir):
        path = os.path.join(base_dir, hwmon)
        name_file = os.path.join(path, "name")
        if os.path.exists(name_file):
            try:
                with open(name_file, 'r') as f:
                    if f.read().strip() == "k10temp":
                        return path
            except Exception:
                continue
    return None

def read_cpu_temps(hwmon_dir):
    if not hwmon_dir:
        return 0.0, 0.0
    tctl = 0.0
    tccd = 0.0
    try:
        for f in os.listdir(hwmon_dir):
            if f.endswith("_label"):
                label_path = os.path.join(hwmon_dir, f)
                with open(label_path, 'r') as file:
                    label = file.read().strip()
                
                prefix = f[:-6]  # Extract prefix like 'temp1' from 'temp1_label'
                input_path = os.path.join(hwmon_dir, f"{prefix}_input")
                
                if os.path.exists(input_path):
                    with open(input_path, 'r') as file:
                        val = float(file.read().strip()) / 1000.0
                    
                    if label == "Tctl":
                        tctl = val
                    elif label == "Tccd1":
                        tccd = val
    except Exception:
        pass
    return tctl, tccd


def get_cpu_freqs():
    freqs = []
    base_path = "/sys/devices/system/cpu"
    try:
        for cpu in os.listdir(base_path):
            if cpu.startswith("cpu") and cpu[3:].isdigit():
                freq_file = os.path.join(base_path, cpu, "cpufreq/scaling_cur_freq")
                if os.path.exists(freq_file):
                    with open(freq_file, 'r') as f:
                        freqs.append(float(f.read().strip()) / 1000.0) # convert KHz to MHz
    except Exception:
        pass
    return sum(freqs) / len(freqs) if freqs else 0.0

def read_proc_stat():
    # Reads /proc/stat and returns dictionary of {core_name: [user, nice, system, idle, iowait, irq, softirq, steal]}
    stats = {}
    try:
        with open("/proc/stat", 'r') as f:
            for line in f:
                if line.startswith("cpu"):
                    parts = line.split()
                    core_name = parts[0]
                    ticks = [float(x) for x in parts[1:9]]
                    stats[core_name] = ticks
    except Exception:
        pass
    return stats

def calculate_cpu_load(prev_ticks, curr_ticks):
    # Calculates load percentages for each core based on ticks difference
    loads = {}
    for core in curr_ticks:
        if core in prev_ticks:
            prev = prev_ticks[core]
            curr = curr_ticks[core]
            
            # Idle time = idle + iowait
            prev_idle = prev[3] + prev[4]
            curr_idle = curr[3] + curr[4]
            
            # Non-idle time = user + nice + system + irq + softirq + steal
            prev_non_idle = prev[0] + prev[1] + prev[2] + prev[5] + prev[6] + prev[7]
            curr_non_idle = curr[0] + curr[1] + curr[2] + curr[5] + curr[6] + curr[7]
            
            prev_total = prev_idle + prev_non_idle
            curr_total = curr_idle + curr_non_idle
            
            total_diff = curr_total - prev_total
            idle_diff = curr_idle - prev_idle
            
            if total_diff > 0:
                load_pct = (total_diff - idle_diff) / total_diff * 100.0
                loads[core] = load_pct
            else:
                loads[core] = 0.0
    return loads

def main():
    hwmon_dir = find_k10temp_dir()
    if not hwmon_dir:
        print("Warning: k10temp sensor directory not found. CPU temperatures will not be logged.")
    else:
        print(f"Located k10temp sensor at: {hwmon_dir}")

    # Set up CSV Header with individual core columns (assuming 12 threads)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w') as f:
            headers = ["timestamp", "cpu_avg_load", "temp_tctl", "temp_tccd", "avg_freq_mhz"]
            for i in range(12):
                headers.append(f"cpu{i}_load")
            f.write(",".join(headers) + "\n")

    print(f"Starting CPU Telemetry Logger...")
    print(f"Writing to: {os.path.abspath(CSV_PATH)}")
    print("Press Ctrl+C to stop.")
    print("-" * 100)
    print(f"{'Time':19} | {'Avg Load':8} | {'Tctl (°C)':9} | {'Tccd (°C)':9} | {'Avg Freq (MHz)':14} | Core Loads")
    print("-" * 100)

    # Prime the CPU ticks
    prev_stats = read_proc_stat()
    time.sleep(1)

    try:
        while True:
            t_str = time.strftime("%Y-%m-%d %H:%M:%S")
            curr_stats = read_proc_stat()
            loads = calculate_cpu_load(prev_stats, curr_stats)
            prev_stats = curr_stats

            # Core Metrics
            avg_load = loads.get("cpu", 0.0)
            tctl, tccd = read_cpu_temps(hwmon_dir)
            avg_freq = get_cpu_freqs()

            # Compile individual core loads (cpu0 to cpu11)
            core_loads_str = ""
            core_csv_values = []
            for i in range(12):
                core_name = f"cpu{i}"
                l_val = loads.get(core_name, 0.0)
                core_csv_values.append(f"{l_val:.1f}")
                # Compact output visual (0-9 scale, * for 100)
                symbol = str(int(l_val / 10)) if l_val < 100 else "*"
                core_loads_str += symbol

            # Print dashboard line
            print(f"{t_str} | {avg_load:7.1f}% | {tctl:9.1f} | {tccd:9.1f} | {avg_freq:14.1f} | [{core_loads_str}]")

            # Write to CSV and bypass OS caching
            with open(CSV_PATH, 'a') as f:
                csv_line = f"{t_str},{avg_load:.2f},{tctl:.1f},{tccd:.1f},{avg_freq:.1f}," + ",".join(core_csv_values) + "\n"
                f.write(csv_line)
                f.flush()
                os.fsync(f.fileno())

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
