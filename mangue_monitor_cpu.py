#!/usr/bin/env python3
import time
import os
import sys

CSV_PATH = "cpu_monitor_log.csv"
RAPL_ENERGY_FILE = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
rapl_state = {"prev_energy": 0.0, "prev_time": 0.0}

def find_cpu_hwmon_dirs():
    # Scan hwmon directories to find k10temp or zenpower dynamically
    base_dir = "/sys/class/hwmon"
    paths = []
    if not os.path.exists(base_dir):
        return paths
    for hwmon in os.listdir(base_dir):
        path = os.path.join(base_dir, hwmon)
        name_file = os.path.join(path, "name")
        if os.path.exists(name_file):
            try:
                with open(name_file, 'r') as f:
                    drv_name = f.read().strip()
                    if drv_name in ("k10temp", "zenpower"):
                        paths.append((drv_name, path))
            except Exception:
                continue
    return paths

def read_cpu_temps(hwmon_dirs):
    if not hwmon_dirs:
        return 0.0, 0.0
    tctl = 0.0
    tccd = 0.0
    
    # Sort to prioritize zenpower over k10temp if both are present
    sorted_dirs = sorted(hwmon_dirs, key=lambda x: 0 if x[0] == "zenpower" else 1)
    
    for drv_name, path in sorted_dirs:
        try:
            for f in os.listdir(path):
                if f.endswith("_label"):
                    label_path = os.path.join(path, f)
                    with open(label_path, 'r') as file:
                        label = file.read().strip()
                    
                    prefix = f[:-6]  # Extract prefix like 'temp1' from 'temp1_label'
                    input_path = os.path.join(path, f"{prefix}_input")
                    
                    if os.path.exists(input_path):
                        with open(input_path, 'r') as file:
                            val = float(file.read().strip()) / 1000.0
                        
                        # Match Tctl or Tdie for main CPU temp
                        if label in ("Tctl", "Tdie") and tctl == 0.0:
                            tctl = val
                        # Match Tccd1 or general Tccd label for Core Complex temp
                        elif (label == "Tccd1" or "Tccd" in label) and tccd == 0.0:
                            tccd = val
        except Exception:
            pass

    # Fallback to temp1_input if no label matching succeeded
    if tctl == 0.0:
        for drv_name, path in sorted_dirs:
            fallback_path = os.path.join(path, "temp1_input")
            if os.path.exists(fallback_path):
                try:
                    with open(fallback_path, 'r') as file:
                        tctl = float(file.read().strip()) / 1000.0
                        break
                except Exception:
                    pass
                    
    return tctl, tccd

def read_rapl_power():
    global rapl_state
    if not os.path.exists(RAPL_ENERGY_FILE):
        return 0.0
    try:
        with open(RAPL_ENERGY_FILE, 'r') as f:
            curr_energy = float(f.read().strip())
        curr_time = time.time()
        
        power = 0.0
        if rapl_state["prev_energy"] > 0.0 and curr_time > rapl_state["prev_time"]:
            diff_energy = curr_energy - rapl_state["prev_energy"]
            diff_time = curr_time - rapl_state["prev_time"]
            power = (diff_energy / diff_time) / 1000000.0  # uJ to W
        
        # Update state
        rapl_state["prev_energy"] = curr_energy
        rapl_state["prev_time"] = curr_time
        return power
    except Exception:
        return 0.0

def read_cpu_power_voltage(hwmon_dirs):
    power = 0.0
    voltage = 0.0
    for drv_name, path in hwmon_dirs:
        if drv_name == "zenpower":
            try:
                # Scan for SVI2 Core Voltage dynamically using labels
                for f in os.listdir(path):
                    if f.startswith("in") and f.endswith("_label"):
                        label_path = os.path.join(path, f)
                        with open(label_path, 'r') as file:
                            label = file.read().strip().lower()
                        
                        # Match "svi2_core", "svi2 core", or similar voltage label
                        if "svi2" in label and "core" in label and "volt" in label:
                            prefix = f[:-6]  # e.g., 'in0' from 'in0_label'
                            input_path = os.path.join(path, f"{prefix}_input")
                            if os.path.exists(input_path):
                                with open(input_path, 'r') as file:
                                    voltage = float(file.read().strip()) / 1000000.0  # uV to V
                                    break
                        elif "svi2_core" in label or "svi2 core" in label or "vcore" in label:
                            prefix = f[:-6]
                            input_path = os.path.join(path, f"{prefix}_input")
                            if os.path.exists(input_path):
                                with open(input_path, 'r') as file:
                                    voltage = float(file.read().strip()) / 1000000.0  # uV to V
                                    break

                # Fallback if label scan did not yield a result
                if voltage == 0.0:
                    volt_file = os.path.join(path, "in0_input")
                    if os.path.exists(volt_file):
                        with open(volt_file, 'r') as file:
                            voltage = float(file.read().strip()) / 1000000.0  # uV to V
                
                # SVI2 Core Power (in microwatts)
                power_file = os.path.join(path, "power1_input")
                if os.path.exists(power_file):
                    with open(power_file, 'r') as file:
                        power = float(file.read().strip()) / 1000000.0  # uW to W
            except Exception:
                pass

    # Fallback to CPU RAPL package power if zenpower power is not available (e.g. running under sudo)
    if power == 0.0:
        power = read_rapl_power()
        
    return power, voltage

def get_cpu_freqs():
    freqs = []
    base_path = "/sys/devices/system/cpu"
    try:
        for cpu in os.listdir(base_path):
            if cpu.startswith("cpu") and cpu[3:].isdigit():
                freq_file = os.path.join(base_path, cpu, "cpufreq/scaling_cur_freq")
                if os.path.exists(freq_file):
                    with open(freq_file, 'r') as f:
                        freqs.append(float(f.read().strip()) / 1000.0)  # KHz to MHz
    except Exception:
        pass
    return sum(freqs) / len(freqs) if freqs else 0.0

def read_mem_info():
    mem_total = 0.0
    mem_avail = 0.0
    swap_total = 0.0
    swap_free = 0.0
    try:
        with open("/proc/meminfo", 'r') as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem_total = float(line.split()[1]) / 1024 / 1024  # KB to GB
                elif line.startswith("MemAvailable:"):
                    mem_avail = float(line.split()[1]) / 1024 / 1024
                elif line.startswith("SwapTotal:"):
                    swap_total = float(line.split()[1]) / 1024 / 1024
                elif line.startswith("SwapFree:"):
                    swap_free = float(line.split()[1]) / 1024 / 1024
    except Exception:
        pass
    
    mem_used = mem_total - mem_avail
    mem_pct = (mem_used / mem_total * 100.0) if mem_total > 0 else 0.0
    
    swap_used = swap_total - swap_free
    swap_pct = (swap_used / swap_total * 100.0) if swap_total > 0 else 0.0
    
    return mem_total, mem_used, mem_pct, swap_total, swap_used, swap_pct

def read_proc_stat():
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
    loads = {}
    for core in curr_ticks:
        if core in prev_ticks:
            prev = prev_ticks[core]
            curr = curr_ticks[core]
            
            prev_idle = prev[3] + prev[4]
            curr_idle = curr[3] + curr[4]
            
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

def color_value(val, warn_limit, crit_limit, width, format_spec=".1f"):
    val_str = f"{val:{width}{format_spec}}"
    if val >= crit_limit:
        return f"\033[1m\033[31m{val_str}\033[0m"  # Bold Red
    elif val >= warn_limit:
        return f"\033[1m\033[33m{val_str}\033[0m"  # Bold Yellow
    return val_str

def main():
    hwmon_dirs = find_cpu_hwmon_dirs()
    if not hwmon_dirs:
        print("Warning: Neither k10temp nor zenpower sensor directory found. CPU temperatures/power will not be logged.")
    else:
        paths_str = ", ".join([f"{drv_name} ({path})" for drv_name, path in hwmon_dirs])
        print(f"Located CPU sensor(s) at: {paths_str}")

    # Set up CSV Header with individual core columns (assuming 12 threads)
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w') as f:
            headers = [
                "timestamp", "cpu_avg_load", "temp_tctl", "temp_tccd", 
                "avg_freq_mhz", "cpu_power_w", "cpu_volt_v",
                "ram_used_gb", "ram_total_gb", "ram_pct",
                "swap_used_gb", "swap_total_gb"
            ]
            for i in range(12):
                headers.append(f"cpu{i}_load")
            f.write(",".join(headers) + "\n")

    print(f"Starting CPU Telemetry Logger...")
    print(f"Writing to: {os.path.abspath(CSV_PATH)}")
    print("Press Ctrl+C to stop.")
    print("-" * 125)
    print(f"{'Time':19} | {'Avg Load':8} | {'Tctl (°C)':9} | {'Tccd (°C)':9} | {'Avg Freq (MHz)':14} | {'Power (W)':9} | {'Volt (V)':8} | {'RAM (Used/Total)':16} | Core Loads")
    print("-" * 125)

    # Prime CPU ticks and RAPL state
    prev_stats = read_proc_stat()
    read_rapl_power()
    time.sleep(1)

    try:
        while True:
            t_str = time.strftime("%Y-%m-%d %H:%M:%S")
            curr_stats = read_proc_stat()
            loads = calculate_cpu_load(prev_stats, curr_stats)
            prev_stats = curr_stats

            # Metrics
            avg_load = loads.get("cpu", 0.0)
            tctl, tccd = read_cpu_temps(hwmon_dirs)
            avg_freq = get_cpu_freqs()
            cpu_power, cpu_volt = read_cpu_power_voltage(hwmon_dirs)
            
            # RAM & Swap Info
            mem_total, mem_used, mem_pct, swap_total, swap_used, swap_pct = read_mem_info()

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

            # Formatting & Color-Coding
            load_str = color_value(avg_load, 85.0, 95.0, 7, ".1f") + "%"
            tctl_str = color_value(tctl, 75.0, 85.0, 9, ".1f")
            tccd_str = color_value(tccd, 75.0, 85.0, 9, ".1f")
            freq_str = f"{avg_freq:14.1f}"
            
            # CPU Power & Voltage Display (N/A if not available)
            power_str = f"{cpu_power:9.2f}" if cpu_power > 0 else f"{'N/A':>9}"
            volt_str = f"{cpu_volt:8.3f}" if cpu_volt > 0 else f"{'N/A':>8}"
            
            # RAM Formatting
            ram_ratio_str = f"{mem_used:4.1f}/{mem_total:<4.1f} GB"
            if mem_pct >= 95.0:
                ram_ratio_str = f"\033[1m\033[31m{ram_ratio_str}\033[0m"
            elif mem_pct >= 85.0:
                ram_ratio_str = f"\033[1m\033[33m{ram_ratio_str}\033[0m"

            # Print to console
            print(f"{t_str} | {load_str} | {tctl_str} | {tccd_str} | {freq_str} | {power_str} | {volt_str} | {ram_ratio_str:16} | [{core_loads_str}]")

            # Write to CSV and bypass OS caching
            with open(CSV_PATH, 'a') as f:
                csv_line = (
                    f"{t_str},{avg_load:.2f},{tctl:.1f},{tccd:.1f},{avg_freq:.1f},"
                    f"{cpu_power:.2f},{cpu_volt:.3f},{mem_used:.2f},{mem_total:.2f},{mem_pct:.1f},"
                    f"{swap_used:.2f},{swap_total:.2f}," + ",".join(core_csv_values) + "\n"
                )
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
