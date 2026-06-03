# Linux Hardware Diagnostic Reference Guide

This document contains a catalog of commands used to diagnose motherboard, CPU, GPU, memory, and power supply issues on Fedora Linux. These commands do not require root privileges (except where noted) and extract data directly from system logs or the `/sys` filesystem.

---

## 1. System & Motherboard Identification

These commands read DMI (Desktop Management Interface) tables to identify the board and BIOS.

```bash
# Read motherboard details directly from sysfs
cat /sys/class/dmi/id/board_vendor
cat /sys/class/dmi/id/board_name
cat /sys/class/dmi/id/product_name
cat /sys/class/dmi/id/bios_version

# Retrieve CPU specifications
lscpu | grep -E "Model name|Vendor ID|Core\(s\) per socket|Socket\(s\)"
```

---

## 2. Memory Diagnostics & Verification

Use these to check capacity, verify dual-channel layout detection, and look for memory hardware errors.

```bash
# Check memory allocation and availability
free -h

# Check RAM layout and slots (requires root)
sudo dmidecode -t memory | grep -E "Size|Speed|Locator|Type|Clock"

# Search logs for memory parity errors or Correctable/Uncorrectable EDAC logs
journalctl -b 0 | grep -i -E "edac|mce|machine check|correctable|uncorrectable"
```

---

## 3. PCI Express & GPU Link Diagnostics

These commands check if the physical PCIe connection between the motherboard and graphics card is operating at full width/speed and check for interface errors.

```bash
# List all active graphics controllers and active kernel drivers
lspci -k | grep -A 3 -E "VGA|3D"

# Find PCIe link speeds/widths via sysfs (avoiding lspci permission limits)
# Run this to find paths to speed and width attributes:
find /sys/devices/ -name "current_link_speed" -o -name "current_link_width"

# Once you have the path (e.g., using GPU PCI Address 00:03.1 / 09:00.0), check status:
cat /sys/devices/pci0000:00/0000:00:03.1/0000:09:00.0/current_link_speed
cat /sys/devices/pci0000:00/0000:00:03.1/0000:09:00.0/current_link_width
cat /sys/devices/pci0000:00/0000:00:03.1/0000:09:00.0/max_link_speed
cat /sys/devices/pci0000:00/0000:00:03.1/0000:09:00.0/max_link_width

# Check current boot logs for PCIe AER (Advanced Error Reporting) bus errors
journalctl -b 0 | grep -i -E "pcie|aer|bus error" | tail -n 50
```

---

## 4. Temperature & Sensor Telemetry

Monitor system temperatures and hardware status.

```bash
# Basic temperature, voltage, and fan metrics
sensors

# Retrieve raw hardware monitor temperatures directly from sysfs (loop through all zones)
for file in /sys/class/hwmon/hwmon*/name; do
  dir=$(dirname "$file")
  name=$(cat "$file")
  echo "HWMON: $name"
  for t in "$dir"/temp*_input; do
    if [ -f "$t" ]; then
      label_file="${t%_input}_label"
      label=""
      [ -f "$label_file" ] && label="($(cat "$label_file"))"
      val=$(cat "$t")
      echo "  temp: $((val / 1000))°C $label"
    fi
  done
done
```

---

## 5. System Crash & Stability Logs (journalctl)

These commands are used to inspect logs right before an unexpected reboot or shutdown, as well as to check driver health.

```bash
# List historical boot sessions (shows timestamps of reboots/power cycles)
journalctl --list-boots

# View the final logs of the PREVIOUS boot session to find pre-crash events
journalctl -b -1 -n 250 --no-pager

# Check current boot logs specifically for critical system/kernel errors
journalctl -b 0 -p 3 -n 50 --no-pager

# Scan ALL boots for GPU driver reset attempts (driver crashes and recovery)
journalctl | grep -i -E "amdgpu.*reset|ring.*timeout|gpu.*hang|reset.*gpu" | tail -n 50
```

---

## 6. Real-Time Telemetry Logging (Fsync-Enabled)

To capture GPU metrics during gameplay in a way that survives a hard power loss (without getting lost in the OS disk cache), we used a custom Python monitoring loop that writes directly to `gpu_monitor_log.csv` and calls:
* `f.flush()`
* `os.fsync(f.fileno())`

This forces the SSD to commit the exact telemetry state to physical storage every second, so that the final entry represents the hardware status right at the moment of the crash.
