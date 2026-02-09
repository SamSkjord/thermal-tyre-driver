#!/usr/bin/env python3
"""
Real-time thermal tyre data visualizer
Reads JSON from Pico serial port and displays temperature data
"""

import serial
import serial.tools.list_ports
import json
import time
import sys
from collections import deque
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
import numpy as np


class TyreVisualizer:
    """Real-time visualizer for thermal tyre data"""

    def __init__(self, port=None, baudrate=115200, history_length=100):
        """
        Initialize visualizer

        Args:
            port: Serial port path (auto-detect if None)
            baudrate: Serial baud rate
            history_length: Number of frames to keep in history
        """
        self.history_length = history_length
        self.baudrate = baudrate

        # Find port if not specified
        if port is None:
            port = self._find_pico_port()
            if port is None:
                raise RuntimeError("No Pico device found. Specify port manually.")

        print(f"Connecting to {port} at {baudrate} baud...")
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Wait for connection to stabilize
        print("Connected!")

        # Data storage
        self.temps_history = {
            "left": deque(maxlen=history_length),
            "centre": deque(maxlen=history_length),
            "right": deque(maxlen=history_length),
        }
        self.confidence_history = deque(maxlen=history_length)
        self.gradient_history = deque(maxlen=history_length)
        self.frame_numbers = deque(maxlen=history_length)
        self.warnings = []
        self.latest_data = None
        self.latest_profile = None

        # Statistics
        self.frames_received = 0
        self.frames_dropped = 0
        self.start_time = time.time()
        self.last_frame_time = time.time()

        # Setup plot
        self._setup_plot()

    def _find_pico_port(self):
        """Auto-detect Pico USB port"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Look for common Pico identifiers
            if "usbmodem" in port.device.lower() or "ttyACM" in port.device:
                print(f"Found potential Pico at: {port.device}")
                return port.device
        return None

    def _setup_plot(self):
        """Setup matplotlib figure and subplots"""
        self.fig = plt.figure(figsize=(16, 9))
        self.fig.canvas.manager.set_window_title("Thermal Tyre Monitor")
        gs = GridSpec(3, 3, figure=self.fig, hspace=0.3, wspace=0.3)

        # Temperature bars (current values)
        self.ax_bars = self.fig.add_subplot(gs[0, 0])
        self.ax_bars.set_title("Current Temperatures", fontweight="bold")
        self.ax_bars.set_ylabel("Temperature (°C)")
        self.ax_bars.set_ylim(0, 100)
        self.ax_bars.grid(True, alpha=0.3)

        # Temperature history
        self.ax_history = self.fig.add_subplot(gs[0, 1:])
        self.ax_history.set_title("Temperature History", fontweight="bold")
        self.ax_history.set_xlabel("Frame")
        self.ax_history.set_ylabel("Temperature (°C)")
        self.ax_history.grid(True, alpha=0.3)
        self.ax_history.legend(["Left", "Centre", "Right"], loc="upper left")

        # Confidence meter
        self.ax_confidence = self.fig.add_subplot(gs[1, 0])
        self.ax_confidence.set_title("Detection Confidence", fontweight="bold")
        self.ax_confidence.set_xlim(0, 1)
        self.ax_confidence.set_ylim(0, 1)
        self.ax_confidence.set_xticks([0, 0.5, 1.0])
        self.ax_confidence.set_xticklabels(["0%", "50%", "100%"])
        self.ax_confidence.set_yticks([])

        # Temperature profile (1D heatmap)
        self.ax_profile = self.fig.add_subplot(gs[1, 1:])
        self.ax_profile.set_title(
            "Temperature Profile (32 pixels across sensor)", fontweight="bold"
        )
        self.ax_profile.set_xlabel("Pixel")
        self.ax_profile.set_ylabel("Temperature (°C)")

        # Gradient history
        self.ax_gradient = self.fig.add_subplot(gs[2, :2])
        self.ax_gradient.set_title("Lateral Temperature Gradient", fontweight="bold")
        self.ax_gradient.set_xlabel("Frame")
        self.ax_gradient.set_ylabel("Gradient (°C)")
        self.ax_gradient.grid(True, alpha=0.3)

        # Stats and warnings panel
        self.ax_stats = self.fig.add_subplot(gs[2, 2])
        self.ax_stats.set_title("Status", fontweight="bold")
        self.ax_stats.axis("off")

        plt.tight_layout()

    def _read_data(self):
        """Read and parse one line of JSON or CSV data"""
        try:
            # Read all available lines and keep only the latest
            # This prevents frame buffer buildup when visualization is slower than data rate
            lines = []
            while self.serial.in_waiting > 0:
                line = self.serial.readline()
                if line:
                    lines.append(line)

            # If no new data, try to read one line with timeout
            if not lines:
                line = self.serial.readline()
                if not line:
                    return None
                lines = [line]

            # Use the most recent line
            line_str = lines[-1].decode("utf-8").strip()

            # Count dropped frames if we skipped any
            if len(lines) > 1:
                self.frames_dropped += len(lines) - 1

            # Try JSON first
            if line_str.startswith('{'):
                data = json.loads(line_str)
            else:
                # Parse new CSV format: Frame,FPS,L_avg,L_med,C_avg,C_med,R_avg,R_med,Width,Conf,Det
                parts = line_str.split(',')
                if len(parts) >= 11:
                    frame_num = int(parts[0])
                    fps = float(parts[1])
                    l_avg = float(parts[2])
                    l_med = float(parts[3])
                    c_avg = float(parts[4])
                    c_med = float(parts[5])
                    r_avg = float(parts[6])
                    r_med = float(parts[7])
                    width = int(parts[8])
                    conf = float(parts[9])
                    detected = int(parts[10])

                    data = {
                        "frame_number": frame_num,
                        "fps": fps,
                        "analysis": {
                            "left": {"avg": l_avg, "median": l_med},
                            "centre": {"avg": c_avg, "median": c_med},
                            "right": {"avg": r_avg, "median": r_med},
                            "lateral_gradient": 0  # Could calculate from l/c/r if needed
                        },
                        "detection": {
                            "confidence": conf,
                            "detected": detected,
                            "tyre_width": width,
                            "span_start": 0,
                            "span_end": width  # Approximate
                        },
                        "temperature_profile": [],
                        "warnings": []
                    }
                else:
                    return None

            self.frames_received += 1
            self.last_frame_time = time.time()
            return data

        except (json.JSONDecodeError, ValueError, IndexError):
            self.frames_dropped += 1
            return None
        except Exception as e:
            print(f"Error reading data: {e}")
            return None

    def _update_data(self, data):
        """Update internal data structures with new frame"""
        if data is None:
            return

        self.latest_data = data

        # Extract temperatures
        analysis = data.get("analysis", {})
        left = analysis.get("left", {}).get("avg", 0)
        centre = analysis.get("centre", {}).get("avg", 0)
        right = analysis.get("right", {}).get("avg", 0)

        self.temps_history["left"].append(left)
        self.temps_history["centre"].append(centre)
        self.temps_history["right"].append(right)

        # Extract other data
        detection = data.get("detection", {})
        confidence = detection.get("confidence", 0)
        self.confidence_history.append(confidence)

        gradient = analysis.get("lateral_gradient", 0)
        self.gradient_history.append(gradient)

        frame_num = data.get("frame_number", 0)
        self.frame_numbers.append(frame_num)

        # Temperature profile
        profile = data.get("temperature_profile", [])
        if profile:
            self.latest_profile = profile

        # Warnings
        self.warnings = data.get("warnings", [])

    def _update_plot(self, frame):
        """Update plot with latest data (called by animation)"""
        # Read new data
        data = self._read_data()
        self._update_data(data)

        if len(self.temps_history["left"]) == 0:
            return

        # Clear axes
        self.ax_bars.clear()
        self.ax_history.clear()
        self.ax_confidence.clear()
        self.ax_profile.clear()
        self.ax_gradient.clear()
        self.ax_stats.clear()

        # --- Temperature bars ---
        self.ax_bars.set_title("Current Temperatures (Average)", fontweight="bold")
        self.ax_bars.set_ylabel("Temperature (°C)")
        self.ax_bars.set_ylim(0, 100)
        self.ax_bars.grid(True, alpha=0.3)

        current_temps = [
            self.temps_history["left"][-1],
            self.temps_history["centre"][-1],
            self.temps_history["right"][-1],
        ]
        bars = self.ax_bars.bar(
            ["Left", "Centre", "Right"],
            current_temps,
            color=["#3498db", "#e74c3c", "#2ecc71"],
        )

        # Color bars by temperature
        for bar, temp in zip(bars, current_temps):
            if temp > 60:
                bar.set_color("#e74c3c")  # Hot - red
            elif temp > 40:
                bar.set_color("#f39c12")  # Warm - orange
            else:
                bar.set_color("#3498db")  # Cool - blue

        # Add value labels
        for bar, temp in zip(bars, current_temps):
            height = bar.get_height()
            self.ax_bars.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{temp:.1f}°C",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        # --- Temperature history ---
        self.ax_history.set_title("Temperature History", fontweight="bold")
        self.ax_history.set_xlabel("Frame")
        self.ax_history.set_ylabel("Temperature (°C)")
        self.ax_history.grid(True, alpha=0.3)

        frames = list(range(len(self.temps_history["left"])))
        self.ax_history.plot(
            frames, list(self.temps_history["left"]), "b-", label="Left", linewidth=2
        )
        self.ax_history.plot(
            frames,
            list(self.temps_history["centre"]),
            "r-",
            label="Centre",
            linewidth=2,
        )
        self.ax_history.plot(
            frames, list(self.temps_history["right"]), "g-", label="Right", linewidth=2
        )
        self.ax_history.legend(loc="upper left")

        # --- Confidence meter ---
        self.ax_confidence.set_title("Detection Confidence", fontweight="bold")
        self.ax_confidence.set_xlim(0, 1)
        self.ax_confidence.set_ylim(0, 1)
        self.ax_confidence.set_xticks([0, 0.5, 1.0])
        self.ax_confidence.set_xticklabels(["0%", "50%", "100%"])
        self.ax_confidence.set_yticks([])

        if len(self.confidence_history) > 0:
            conf = self.confidence_history[-1]
            # Color based on confidence
            if conf > 0.8:
                color = "#2ecc71"  # Green
            elif conf > 0.5:
                color = "#f39c12"  # Orange
            else:
                color = "#e74c3c"  # Red

            self.ax_confidence.barh([0.5], [conf], height=0.5, color=color)
            self.ax_confidence.text(
                conf / 2,
                0.5,
                f"{conf:.0%}",
                ha="center",
                va="center",
                fontweight="bold",
                fontsize=14,
                color="white",
            )

        # --- Temperature profile ---
        self.ax_profile.set_title(
            "Temperature Profile (32 pixels across sensor)", fontweight="bold"
        )
        self.ax_profile.set_xlabel("Pixel")
        self.ax_profile.set_ylabel("Temperature (°C)")

        if self.latest_profile:
            pixels = list(range(len(self.latest_profile)))
            self.ax_profile.plot(pixels, self.latest_profile, "b-", linewidth=2)
            self.ax_profile.fill_between(pixels, self.latest_profile, alpha=0.3)

            # Mark tyre span if available
            if self.latest_data:
                detection = self.latest_data.get("detection", {})
                span_start = detection.get("span_start", 0)
                span_end = detection.get("span_end", 0)
                if span_start < span_end:
                    self.ax_profile.axvspan(
                        span_start, span_end, alpha=0.2, color="red"
                    )
                    self.ax_profile.text(
                        (span_start + span_end) / 2,
                        max(self.latest_profile) * 0.9,
                        "TYRE",
                        ha="center",
                        fontweight="bold",
                    )
        else:
            # No profile data available (CSV mode)
            self.ax_profile.text(
                0.5, 0.5,
                "Profile data not available in CSV mode",
                ha="center", va="center",
                transform=self.ax_profile.transAxes,
                fontsize=10, style="italic", color="gray"
            )

        # --- Gradient history ---
        self.ax_gradient.set_title("Lateral Temperature Gradient", fontweight="bold")
        self.ax_gradient.set_xlabel("Frame")
        self.ax_gradient.set_ylabel("Gradient (°C)")
        self.ax_gradient.grid(True, alpha=0.3)

        if len(self.gradient_history) > 0:
            frames = list(range(len(self.gradient_history)))
            self.ax_gradient.plot(
                frames, list(self.gradient_history), "purple", linewidth=2
            )
            self.ax_gradient.axhline(
                y=10,
                color="r",
                linestyle="--",
                alpha=0.5,
                label="High gradient threshold",
            )

        # --- Stats and warnings ---
        self.ax_stats.set_title("Status", fontweight="bold")
        self.ax_stats.axis("off")

        # Calculate actual frame rate
        elapsed = time.time() - self.start_time
        actual_fps = self.frames_received / elapsed if elapsed > 0 else 0

        # Get device FPS and detection info
        device_fps = self.latest_data.get("fps", 0) if self.latest_data else 0
        detection = self.latest_data.get("detection", {}) if self.latest_data else {}
        detected = detection.get("detected", 0)
        tyre_width = detection.get("tyre_width", 0)

        stats_text = f"Frame: {self.frame_numbers[-1] if self.frame_numbers else 0}\n"
        stats_text += f"Received: {self.frames_received}\n"
        stats_text += f"Dropped: {self.frames_dropped}\n"
        stats_text += f"Device FPS: {device_fps:.1f}\n"
        stats_text += f"Display FPS: {actual_fps:.1f}\n"
        stats_text += f"Elapsed: {elapsed:.1f}s\n\n"

        # Detection status
        if detected:
            stats_text += f"✓ TYRE DETECTED\n"
            stats_text += f"  Width: {tyre_width} pixels\n\n"
        else:
            stats_text += "○ No tyre detected\n\n"

        if self.warnings:
            stats_text += "WARNINGS:\n"
            for warning in self.warnings[:5]:  # Show first 5 warnings
                stats_text += f"• {warning}\n"
        else:
            stats_text += "✓ No warnings"

        self.ax_stats.text(
            0.05,
            0.95,
            stats_text,
            transform=self.ax_stats.transAxes,
            verticalalignment="top",
            fontfamily="monospace",
            fontsize=9,
        )

    def run(self):
        """Start the visualization"""
        print("Starting visualization... Close window to exit.")
        print("Note: Visualization may drop frames to keep display responsive.")
        # Increase interval to 250ms (4 fps max) to prevent frame buildup
        # The visualizer will skip frames to always show the latest data
        ani = animation.FuncAnimation(
            self.fig, self._update_plot, interval=250, cache_frame_data=False
        )
        plt.show()

    def close(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Serial connection closed")


def list_ports():
    """List available serial ports"""
    ports = serial.tools.list_ports.comports()
    print("\nAvailable serial ports:")
    for i, port in enumerate(ports):
        print(f"{i+1}. {port.device} - {port.description}")
    print()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Real-time thermal tyre data visualizer"
    )
    parser.add_argument(
        "-p", "--port", help="Serial port (e.g., /dev/tty.usbmodem14201 or COM3)"
    )
    parser.add_argument(
        "-b", "--baudrate", type=int, default=115200, help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List available serial ports and exit"
    )
    parser.add_argument(
        "--history",
        type=int,
        default=100,
        help="Number of frames to keep in history (default: 100)",
    )

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    try:
        visualizer = TyreVisualizer(
            port=args.port, baudrate=args.baudrate, history_length=args.history
        )
        visualizer.run()
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")
        print("\nTry running with --list to see available ports")
        sys.exit(1)
    finally:
        if "visualizer" in locals():
            visualizer.close()


if __name__ == "__main__":
    main()
