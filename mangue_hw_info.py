#!/usr/bin/env python3
import os
import sys
import subprocess
import platform
import datetime

# Script to collect system, motherboard, CPU, GPU, and hwmon sensor information.
# Writes a report to mangue_hw_info_report.txt and outputs to stdout.

REPORT_FILE = "mangue_hw_info_report.txt"

def main():
    lines = []
    
    def log(msg=""):
        print(msg)
        lines.append(msg)
        
    log("=" * 80)
    log("               MANGUE HARDWARE MONITOR - DIAGNOSTIC REPORT")
    log(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 80)
    log()
    
    # 1. System & Kernel Information
    log("--- [1. System & Kernel Information] ---")
    log(f"Kernel Release: {platform.release()}")
    log(f"Platform:       {platform.platform()}")
    log(f"Python Version: {platform.python_version()}")
    
    os_release = "Unknown"
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_release = line.strip().split("=")[1].strip('"')
        except Exception as e:
            os_release = f"Error reading /etc/os-release: {e}"
    log(f"OS/Distro:      {os_release}")
    log()
    
    # 2. Motherboard & BIOS Info (sysfs DMI)
    log("--- [2. Motherboard & BIOS Information] ---")
    dmi_files = {
        "board_vendor": "/sys/class/dmi/id/board_vendor",
        "board_name": "/sys/class/dmi/id/board_name",
        "product_name": "/sys/class/dmi/id/product_name",
        "bios_version": "/sys/class/dmi/id/bios_version",
        "bios_date": "/sys/class/dmi/id/bios_date",
        "sys_vendor": "/sys/class/dmi/id/sys_vendor",
    }
    for key, path in dmi_files.items():
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    val = f.read().strip()
                log(f"{key:15}: {val}")
            except PermissionError:
                log(f"{key:15}: Permission Denied (requires root)")
            except Exception as e:
                log(f"{key:15}: Error ({e})")
        else:
            log(f"{key:15}: Not Found")
    log()
    
    # 3. CPU Details
    log("--- [3. CPU Specifications] ---")
    try:
        cpu_info = subprocess.run(["lscpu"], capture_output=True, text=True, check=True)
        interesting_fields = [
            "Architecture", "CPU(s):", "Thread(s) per core:", "Core(s) per socket:",
            "Socket(s):", "Vendor ID:", "Model name:", "CPU min MHz:", "CPU max MHz:"
        ]
        for line in cpu_info.stdout.splitlines():
            for field in interesting_fields:
                if line.startswith(field):
                    log(line)
    except Exception as e:
        log(f"Could not run lscpu: {e}")
        if os.path.exists("/proc/cpuinfo"):
            try:
                models = set()
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.strip().startswith("model name"):
                            models.add(line.split(":", 1)[1].strip())
                for m in models:
                    log(f"Model name (proc/cpuinfo): {m}")
            except Exception as ex:
                log(f"Error reading /proc/cpuinfo: {ex}")
    log()
    
    # 4. Memory details
    log("--- [4. System Memory & Swap] ---")
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if any(line.startswith(p) for p in ("MemTotal:", "MemFree:", "MemAvailable:", "SwapTotal:", "SwapFree:")):
                        log(line.strip())
        except Exception as e:
            log(f"Error reading /proc/meminfo: {e}")
    log()
    
    # 5. HWMON Directories and Sensors
    log("--- [5. HWMON Sensor Scan] ---")
    base_hwmon = "/sys/class/hwmon"
    if os.path.exists(base_hwmon):
        for hwmon in sorted(os.listdir(base_hwmon)):
            hwmon_path = os.path.join(base_hwmon, hwmon)
            name_path = os.path.join(hwmon_path, "name")
            drv_name = "unknown"
            if os.path.exists(name_path):
                try:
                    with open(name_path, "r") as f:
                        drv_name = f.read().strip()
                except Exception as e:
                    drv_name = f"Error ({e})"
            log(f"HWMON Directory: {hwmon} | Driver/Device Name: {drv_name}")
            
            try:
                files = os.listdir(hwmon_path)
                prefixes = sorted(list(set(
                    f.split("_")[0] for f in files 
                    if any(f.startswith(p) for p in ("temp", "in", "fan", "power", "pwm"))
                )))
                
                for prefix in prefixes:
                    matching_files = sorted([f for f in files if f.startswith(prefix)])
                    for mf in matching_files:
                        file_path = os.path.join(hwmon_path, mf)
                        try:
                            if os.path.isdir(file_path):
                                continue
                            with open(file_path, "r") as f:
                                val = f.read().strip()
                            log(f"  {mf:25} = {val}")
                        except PermissionError:
                            log(f"  {mf:25} = Permission Denied")
                        except Exception as e:
                            log(f"  {mf:25} = Error reading ({e})")
            except Exception as e:
                log(f"  Error scanning directory: {e}")
            log()
    else:
        log("No /sys/class/hwmon directory found.")
    log()
    
    # 6. GPU drm device diagnostics
    log("--- [6. GPU DRM/Device Diagnostics] ---")
    base_drm = "/sys/class/drm"
    if os.path.exists(base_drm):
        cards = sorted([c for c in os.listdir(base_drm) if c.startswith("card") and "-" not in c])
        for card in cards:
            device_path = os.path.join(base_drm, card, "device")
            log(f"DRM Card: {card} -> Device Path: {device_path}")
            if os.path.exists(device_path):
                uevent_path = os.path.join(device_path, "uevent")
                if os.path.exists(uevent_path):
                    try:
                        with open(uevent_path, "r") as f:
                            log("  [uevent]")
                            for line in f:
                                log(f"    {line.strip()}")
                    except Exception as e:
                        log(f"  Error reading uevent: {e}")
                
                mem_files = [
                    "mem_info_vram_total", "mem_info_vram_used", 
                    "mem_info_gtt_total", "mem_info_gtt_used",
                    "mem_info_vis_vram_total", "mem_info_vis_vram_used",
                    "mem_info_vram_vendor", "gpu_busy_percent"
                ]
                log("  [Memory Info & Usage]")
                for mf in mem_files:
                    mf_path = os.path.join(device_path, mf)
                    if os.path.exists(mf_path):
                        try:
                            with open(mf_path, "r") as f:
                                val = f.read().strip()
                            log(f"    {mf:25} = {val}")
                        except Exception as e:
                            log(f"    {mf:25} = Error ({e})")
                    else:
                        log(f"    {mf:25} = Not Found")
                
                pp_files = ["pp_dpm_sclk", "pp_dpm_mclk", "pp_od_clk_voltage", "power_dpm_force_performance_level"]
                log("  [Clock & Performance profiles]")
                for pf in pp_files:
                    pf_path = os.path.join(device_path, pf)
                    if os.path.exists(pf_path):
                        try:
                            with open(pf_path, "r") as f:
                                val_lines = f.read().strip().splitlines()
                            log(f"    {pf}:")
                            for vl in val_lines[:15]:
                                log(f"      {vl}")
                            if len(val_lines) > 15:
                                log("      ...")
                        except Exception as e:
                            log(f"    {pf} = Error reading ({e})")
                    else:
                        log(f"    {pf} = Not Found")
            log()
    else:
        log("No /sys/class/drm directory found.")
    log()
    
    # 7. Check if running with sudo
    log("--- [7. Privilege Status] ---")
    is_root = os.geteuid() == 0
    log(f"Running as root/sudo: {is_root}")
    if not is_root:
        log("NOTE: Some hardware parameters (like raw dmidecode, parts of powercap, BIOS details) are restricted.")
        log("If needed, run this script with 'sudo python3 mangue_hw_info.py' to extract additional restricted fields.")
    log()
    
    log("=" * 80)
    log(f"Report written to file: {os.path.abspath(REPORT_FILE)}")
    log("Please share the contents of this report file for troubleshooting.")
    log("=" * 80)
    
    try:
        with open(REPORT_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"Error writing report file {REPORT_FILE}: {e}")

if __name__ == "__main__":
    main()
