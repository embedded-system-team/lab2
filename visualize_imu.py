#!/usr/bin/env python3
"""
IMU Real-Time Visualization Server
Receives TCP data from B-L475E-IOT01A1 and visualizes accelerometer/gyroscope data.
Pops up a notification when significant motion is detected.

Data format from device:
  Normal:  "AX,AY,AZ,GX,GY,GZ\n"  (floats in g and dps)
  Event:   "EVENT:SIG_MOTION\n"

Usage:
  python visualize_imu.py [--host 0.0.0.0] [--port 8080]
"""

import socket
import threading
import argparse
import time
import collections
from datetime import datetime

import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation

# ── Try OS-level notification backends ──────────────────────────────────────
try:
    from plyer import notification as plyer_notify
    _PLYER = True
except ImportError:
    _PLYER = False

try:
    import tkinter as tk
    from tkinter import messagebox
    _TKINTER = True
except ImportError:
    _TKINTER = False

# ── Config ───────────────────────────────────────────────────────────────────
WINDOW = 200          # number of samples to display
ALERT_HOLD = 3.0      # seconds to keep the alert banner visible

# ── Shared state (written by network thread, read by GUI thread) ─────────────
data_lock = threading.Lock()

_buf: dict = {
    'ax': collections.deque([0.0] * WINDOW, maxlen=WINDOW),
    'ay': collections.deque([0.0] * WINDOW, maxlen=WINDOW),
    'az': collections.deque([0.0] * WINDOW, maxlen=WINDOW),
    'gx': collections.deque([0.0] * WINDOW, maxlen=WINDOW),
    'gy': collections.deque([0.0] * WINDOW, maxlen=WINDOW),
    'gz': collections.deque([0.0] * WINDOW, maxlen=WINDOW),
    'sig_motion': False,        # set True on event, cleared after ALERT_HOLD
    'sig_motion_time': 0.0,
    'sig_motion_count': 0,
    'last_sample': None,        # latest (ax,ay,az,gx,gy,gz) tuple
    'connected': False,
}


# ── Notification helpers ─────────────────────────────────────────────────────

def _os_notify(count: int):
    """Send an OS-level desktop notification."""
    title = "Significant Motion Detected!"
    msg = f"Event #{count} at {datetime.now().strftime('%H:%M:%S')}"
    if _PLYER:
        try:
            plyer_notify.notify(title=title, message=msg,
                                app_name="IMU Visualizer", timeout=5)
            return
        except Exception:
            pass
    if _TKINTER:
        def _popup():
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning(title, msg)
            root.destroy()
        t = threading.Thread(target=_popup, daemon=True)
        t.start()


# ── TCP server ────────────────────────────────────────────────────────────────

def _handle_client(conn: socket.socket, addr):
    print(f"[server] Client connected: {addr}")
    with data_lock:
        _buf['connected'] = True

    leftover = b''
    try:
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            leftover += chunk
            while b'\n' in leftover:
                line, leftover = leftover.split(b'\n', 1)
                line = line.strip().decode('ascii', errors='ignore')
                if not line:
                    continue
                _parse_line(line)
    except (ConnectionResetError, OSError):
        pass
    finally:
        conn.close()
        with data_lock:
            _buf['connected'] = False
        print(f"[server] Client disconnected: {addr}")


def _parse_line(line: str):
    if line == 'EVENT:SIG_MOTION':
        with data_lock:
            _buf['sig_motion'] = True
            _buf['sig_motion_time'] = time.time()
            _buf['sig_motion_count'] += 1
            count = _buf['sig_motion_count']
        print(f"[event] *** SIGNIFICANT MOTION #{count} ***")
        _os_notify(count)
        return

    parts = line.split(',')
    if len(parts) == 6:
        try:
            ax, ay, az, gx, gy, gz = (float(p) for p in parts)
        except ValueError:
            return
        with data_lock:
            _buf['ax'].append(ax)
            _buf['ay'].append(ay)
            _buf['az'].append(az)
            _buf['gx'].append(gx)
            _buf['gy'].append(gy)
            _buf['gz'].append(gz)
            _buf['last_sample'] = (ax, ay, az, gx, gy, gz)


def _server_thread(host: str, port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(1)
        print(f"[server] Listening on {host}:{port}")
        while True:
            try:
                conn, addr = srv.accept()
                t = threading.Thread(target=_handle_client,
                                     args=(conn, addr), daemon=True)
                t.start()
            except OSError:
                break


# ── Matplotlib real-time plot ────────────────────────────────────────────────

def _build_figure():
    fig, (ax_accel, ax_gyro) = plt.subplots(2, 1, figsize=(12, 7),
                                             sharex=True)
    fig.patch.set_facecolor('#1e1e2e')
    for ax in (ax_accel, ax_gyro):
        ax.set_facecolor('#2a2a3e')
        ax.tick_params(colors='#cdd6f4')
        ax.xaxis.label.set_color('#cdd6f4')
        ax.yaxis.label.set_color('#cdd6f4')
        for spine in ax.spines.values():
            spine.set_edgecolor('#45475a')

    xs = list(range(WINDOW))

    # Accelerometer lines
    ln_ax, = ax_accel.plot(xs, list(_buf['ax']), color='#f38ba8', lw=1.2, label='Ax (g)')
    ln_ay, = ax_accel.plot(xs, list(_buf['ay']), color='#a6e3a1', lw=1.2, label='Ay (g)')
    ln_az, = ax_accel.plot(xs, list(_buf['az']), color='#89b4fa', lw=1.2, label='Az (g)')
    ax_accel.set_ylabel('Acceleration (g)', color='#cdd6f4')
    ax_accel.set_ylim(-4, 4)
    ax_accel.legend(loc='upper left', facecolor='#313244', labelcolor='#cdd6f4',
                    framealpha=0.8)
    ax_accel.set_title('IMU Real-Time Data', color='#cdd6f4', fontsize=13, pad=10)

    # Gyroscope lines
    ln_gx, = ax_gyro.plot(xs, list(_buf['gx']), color='#fab387', lw=1.2, label='Gx (dps)')
    ln_gy, = ax_gyro.plot(xs, list(_buf['gy']), color='#cba6f7', lw=1.2, label='Gy (dps)')
    ln_gz, = ax_gyro.plot(xs, list(_buf['gz']), color='#94e2d5', lw=1.2, label='Gz (dps)')
    ax_gyro.set_ylabel('Angular Rate (dps)', color='#cdd6f4')
    ax_gyro.set_ylim(-500, 500)
    ax_gyro.set_xlabel(f'Samples (last {WINDOW})', color='#cdd6f4')
    ax_gyro.legend(loc='upper left', facecolor='#313244', labelcolor='#cdd6f4',
                   framealpha=0.8)

    # Alert banner (hidden by default)
    alert_text = fig.text(0.5, 0.965, '', ha='center', va='top',
                          fontsize=13, fontweight='bold',
                          color='#1e1e2e',
                          bbox=dict(boxstyle='round,pad=0.4',
                                    facecolor='#f38ba8', alpha=0.0,
                                    edgecolor='none'))

    # Status bar
    status_text = fig.text(0.01, 0.01, 'Waiting for connection…',
                           color='#6c7086', fontsize=9)

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))

    state = {'alert_end': 0.0}

    def update(_frame):
        with data_lock:
            ax_d = list(_buf['ax'])
            ay_d = list(_buf['ay'])
            az_d = list(_buf['az'])
            gx_d = list(_buf['gx'])
            gy_d = list(_buf['gy'])
            gz_d = list(_buf['gz'])
            sig  = _buf['sig_motion']
            sig_t = _buf['sig_motion_time']
            count = _buf['sig_motion_count']
            sample = _buf['last_sample']
            connected = _buf['connected']
            if sig:
                state['alert_end'] = sig_t + ALERT_HOLD
                _buf['sig_motion'] = False  # consume the flag

        # Update lines
        ln_ax.set_ydata(ax_d)
        ln_ay.set_ydata(ay_d)
        ln_az.set_ydata(az_d)
        ln_gx.set_ydata(gx_d)
        ln_gy.set_ydata(gy_d)
        ln_gz.set_ydata(gz_d)

        # Alert banner visibility
        now = time.time()
        if now < state['alert_end']:
            alert_text.set_text(f"⚠  SIGNIFICANT MOTION DETECTED  (#{count})  ⚠")
            alert_text.get_bbox_patch().set_alpha(0.92)
        else:
            alert_text.set_text('')
            alert_text.get_bbox_patch().set_alpha(0.0)

        # Status bar
        if connected:
            if sample:
                ax_, ay_, az_, gx_, gy_, gz_ = sample
                status_text.set_text(
                    f"● Connected  |  "
                    f"Accel: [{ax_:+.2f}, {ay_:+.2f}, {az_:+.2f}] g  |  "
                    f"Gyro: [{gx_:+.2f}, {gy_:+.2f}, {gz_:+.2f}] dps  |  "
                    f"Events: {count}"
                )
                status_text.set_color('#a6e3a1')
            else:
                status_text.set_text('● Connected — awaiting data…')
                status_text.set_color('#a6e3a1')
        else:
            status_text.set_text('○ Waiting for connection…')
            status_text.set_color('#6c7086')

        return (ln_ax, ln_ay, ln_az, ln_gx, ln_gy, ln_gz,
                alert_text, status_text)

    ani = FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
    return fig, ani


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='IMU TCP visualizer')
    parser.add_argument('--host', default='0.0.0.0',
                        help='IP to listen on (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080,
                        help='TCP port (default: 8080, matches SERVER_PORT in firmware)')
    args = parser.parse_args()

    if not _PLYER and not _TKINTER:
        print("[warn] Neither plyer nor tkinter found — no OS popup notifications.")
        print("       Install plyer for desktop notifications:  pip install plyer")

    srv = threading.Thread(target=_server_thread,
                           args=(args.host, args.port), daemon=True)
    srv.start()

    fig, ani = _build_figure()
    plt.show()


if __name__ == '__main__':
    main()
