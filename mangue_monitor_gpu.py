#!/usr/bin/env python3
import time
import os
import sys

CSV_PATH = "gpu_monitor_log.csv"

def find_gpu_paths():
    # Scan cards in sysfs dynamically
    base_dir = "/sys/class/drm"
    if not os.path.exists(base_dir):
        return None, None
    for card in os.listdir(base_dir):
        if card.startswith("card") and not "-" in card:
            card_path = os.path.join(base_dir, card, "device")
            hwmon_base = os.path.join(card_path, "hwmon")
            if os.path.exists(hwmon_base):
                for hwmon in os.listdir(hwmon_base):
                    hwmon_path = os.path.join(hwmon_base, hwmon)
                    name_file = os.path.join(hwmon_path, "name")
                    if os.path.exists(name_file):
                        try:
                            with open(name_file, 'r') as f:
                                if f.read().strip() == "amdgpu":
                                    return card_path, hwmon_path
                        except Exception:
                            continue
    return None, None

def read_sysfs(hwmon_dir, filename, divisor=1):
    path = os.path.join(hwmon_dir, filename)
    try:
        with open(path, 'r') as f:
            val = f.read().strip()
            return float(val) / divisor
    except Exception:
        return 0.0

def read_gpu_mem(device_path, filename):
    path = os.path.join(device_path, filename)
    try:
        with open(path, 'r') as f:
            val = int(f.read().strip())
            return val / 1024 / 1024  # bytes to MB
    except Exception:
        return 0.0

def read_gpu_voltage(hwmon_dir):
    try:
        # Scan for label containing "vdd" dynamically
        for f in os.listdir(hwmon_dir):
            if f.startswith("in") and f.endswith("_label"):
                label_path = os.path.join(hwmon_dir, f)
                with open(label_path, 'r') as file:
                    label = file.read().strip().lower()
                if "vdd" in label:
                    prefix = f[:-6]  # e.g., 'in0' from 'in0_label'
                    input_path = os.path.join(hwmon_dir, f"{prefix}_input")
                    if os.path.exists(input_path):
                        with open(input_path, 'r') as file:
                            return float(file.read().strip()) / 1000.0  # mV to V
        
        # Fallback to in0_input if vddgfx is in0
        volt_file = os.path.join(hwmon_dir, "in0_input")
        if os.path.exists(volt_file):
            with open(volt_file, 'r') as file:
                return float(file.read().strip()) / 1000.0
    except Exception:
        pass
    return 0.0

def color_value(val, warn_limit, crit_limit, width, format_spec=".1f"):
    val_str = f"{val:{width}{format_spec}}"
    if val <= 0.0:
        return val_str
    if val >= crit_limit:
        return f"\033[1m\033[31m{val_str}\033[0m"  # Bold Red
    elif val >= warn_limit:
        return f"\033[1m\033[33m{val_str}\033[0m"  # Bold Yellow
    return val_str

def main():
    device_path, hwmon_dir = find_gpu_paths()
    if not hwmon_dir:
        print("Error: Active AMD GPU hwmon directory not found.")
        print("Please check if your GPU is running and using the amdgpu driver.")
        sys.exit(1)

    print(f"Starting GPU Telemetry Logger...")
    print(f"Located GPU Device at: {device_path}")
    print(f"Located GPU HWMON at:  {hwmon_dir}")
    print(f"Writing to:            {os.path.abspath(CSV_PATH)}")
    print("Press Ctrl+C to stop.")
    print("-" * 146)
    print(f"{'Time':19} | {'Power (W)':9} | {'Volt (V)':8} | {'Edge (°C)':9} | {'Junct (°C)':10} | {'Mem (°C)':8} | {'Fan (RPM)':9} | {'GFX (MHz)':9} | {'VRAM Clk (MHz)':14} | {'VRAM (Used/Total)':17} | {'GTT (Used/Total)':16}")
    print("-" * 146)

    # Initialize CSV if it doesn't exist
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, 'w') as f:
            f.write("timestamp,power_watts,gpu_volt_v,edge_temp_c,junction_temp_c,memory_temp_c,fan_rpm,gfx_freq_mhz,vram_freq_mhz,vram_used_mb,vram_total_mb,gtt_used_mb,gtt_total_mb\n")

    try:
        while True:
            t_str = time.strftime("%Y-%m-%d %H:%M:%S")

            # Metrics
            power = read_sysfs(hwmon_dir, "power1_average", 1000000)
            gpu_volt = read_gpu_voltage(hwmon_dir)
            temp_edge = read_sysfs(hwmon_dir, "temp1_input", 1000)
            temp_junc = read_sysfs(hwmon_dir, "temp2_input", 1000)
            temp_mem = read_sysfs(hwmon_dir, "temp3_input", 1000)
            fan = read_sysfs(hwmon_dir, "fan1_input")
            gfx_freq = read_sysfs(hwmon_dir, "freq1_input", 1000000)
            vram_freq = read_sysfs(hwmon_dir, "freq2_input", 1000000)

            # Memory allocation
            vram_total = read_gpu_mem(device_path, "mem_info_vram_total")
            vram_used = read_gpu_mem(device_path, "mem_info_vram_used")
            gtt_total = read_gpu_mem(device_path, "mem_info_gtt_total")
            gtt_used = read_gpu_mem(device_path, "mem_info_gtt_used")

            # Warning boundaries: Edge (75C/85C), Junction/Mem (85C/95C)
            power_str = f"{power:9.2f}"
            volt_str = f"{gpu_volt:8.3f}" if gpu_volt > 0 else f"{'N/A':>8}"
            edge_str = color_value(temp_edge, 75.0, 85.0, 9, ".1f")
            junc_str = color_value(temp_junc, 85.0, 95.0, 10, ".1f") if temp_junc > 0 else f"{'N/A':>10}"
            mem_str  = color_value(temp_mem, 85.0, 95.0, 8, ".1f") if temp_mem > 0 else f"{'N/A':>8}"
            
            # Check if fan sensor exists physically (so 0 RPM is shown as 0 instead of N/A)
            fan_exists = os.path.exists(os.path.join(hwmon_dir, "fan1_input"))
            fan_str  = f"{fan:9.0f}" if fan_exists else f"{'N/A':>9}"
            
            gfx_str  = f"{gfx_freq:9.0f}"
            vram_clk_str = f"{vram_freq:14.0f}" if vram_freq > 0 else f"{'N/A':>14}"
            
            # Formatting Memory Allocations
            vram_ratio_str = f"{vram_used:5.0f}/{vram_total:<5.0f} MB"
            if vram_total > 0:
                vram_pct = (vram_used / vram_total) * 100.0
                if vram_pct >= 95.0:
                    vram_ratio_str = f"\033[1m\033[31m{vram_ratio_str}\033[0m"
                elif vram_pct >= 85.0:
                    vram_ratio_str = f"\033[1m\033[33m{vram_ratio_str}\033[0m"
            
            gtt_ratio_str = f"{gtt_used:5.0f}/{gtt_total:<5.0f} MB"

            # Print to console
            print(f"{t_str} | {power_str} | {volt_str} | {edge_str} | {junc_str} | {mem_str} | {fan_str} | {gfx_str} | {vram_clk_str} | {vram_ratio_str:17} | {gtt_ratio_str:16}")

            # Write to CSV
            with open(CSV_PATH, 'a') as f:
                f.write(f"{t_str},{power:.2f},{gpu_volt:.3f},{temp_edge:.1f},{temp_junc:.1f},{temp_mem:.1f},{fan:.0f},{gfx_freq:.0f},{vram_freq:.0f},{vram_used:.1f},{vram_total:.1f},{gtt_used:.1f},{gtt_total:.1f}\n")
                f.flush()
                os.fsync(f.fileno())

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
