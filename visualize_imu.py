import socket
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import collections
import threading

# Configuration
# HOST = '0.0.0.0' # Listen on all interfaces
PORT = 8080        # Port to listen on

# Data storage
MAX_POINTS = 100
accel_x = collections.deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
accel_y = collections.deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
accel_z = collections.deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
gyro_x = collections.deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
gyro_y = collections.deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)
gyro_z = collections.deque([0.0] * MAX_POINTS, maxlen=MAX_POINTS)

lock = threading.Lock()

def server_thread():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', PORT))
        s.listen()
        print(f"Server listening on port {PORT}...")
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            buffer = ""
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        # Expected format: "AX,AY,AZ,GX,GY,GZ"
                        parts = line.strip().split(',')
                        if len(parts) == 6:
                            with lock:
                                accel_x.append(float(parts[0]))
                                accel_y.append(float(parts[1]))
                                accel_z.append(float(parts[2]))
                                gyro_x.append(float(parts[3]))
                                gyro_y.append(float(parts[4]))
                                gyro_z.append(float(parts[5]))
                    except ValueError:
                        print(f"Invalid data: {line}")

# Start server in a separate thread
t = threading.Thread(target=server_thread, daemon=True)
t.start()

# Setup Plot
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

line_ax, = ax1.plot(accel_x, label='Accel X')
line_ay, = ax1.plot(accel_y, label='Accel Y')
line_az, = ax1.plot(accel_z, label='Accel Z')
ax1.set_title("Accelerometer Data (g)")
ax1.set_ylim(-2, 2)
ax1.legend(loc='upper right')

line_gx, = ax2.plot(gyro_x, label='Gyro X')
line_gy, = ax2.plot(gyro_y, label='Gyro Y')
line_gz, = ax2.plot(gyro_z, label='Gyro Z')
ax2.set_title("Gyroscope Data (dps)")
ax2.set_ylim(-500, 500)
ax2.legend(loc='upper right')

def animate(i):
    with lock:
        line_ax.set_ydata(accel_x)
        line_ay.set_ydata(accel_y)
        line_az.set_ydata(accel_z)
        line_gx.set_ydata(gyro_x)
        line_gy.set_ydata(gyro_y)
        line_gz.set_ydata(gyro_z)
    return line_ax, line_ay, line_az, line_gx, line_gy, line_gz

ani = animation.FuncAnimation(fig, animate, interval=50, blit=True)
plt.tight_layout()
plt.show()
