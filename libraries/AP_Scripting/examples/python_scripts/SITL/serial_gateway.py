import socket
import threading
import serial


SERIAL_PORT = 'COM9'
SERIAL_BAUD = 19200
TCP_PORT = 5001
TCP_HOST = '0.0.0.0'


def handle_serial_to_tcp(ser, conn):
    try:
        while True:
            data = ser.read(ser.in_waiting or 1)
            if data:
                conn.sendall(data)
    except Exception as e:
        print(f"[Serial->TCP] Connection closed or error: {e}")
    finally:
        conn.close()


def handle_tcp_to_serial(ser, conn):
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            print(f"Data received from TCP: {data.decode('utf-8', errors='replace')}")
            ser.write(data)
    except Exception as e:
        print(f"[TCP->Seral] Connection closed or error: {e}")
    finally:
        conn.close()


def start_server():
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=0)
    except serial.SerialException as e:
        print(f"Could not open serial port {SERIAL_PORT}: {e}")
        return

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((TCP_HOST, TCP_PORT))
    server_socket.listen(1)
    print(f"Listening for TCP connections on {TCP_HOST}:{TCP_PORT}...")

    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"TCP client connected from {addr}")

            serial_to_tcp = threading.Thread(target=handle_serial_to_tcp, args=(ser, conn), daemon=True)
            tcp_to_serial = threading.Thread(target=handle_tcp_to_serial, args=(ser, conn), daemon=True)

            serial_to_tcp.start()
            tcp_to_serial.start()

            print("TCP client disconnected.")
    except KeyboardInterrupt:
        print("\n[Interrupted]")

    ser.close()


if __name__ == "__main__":
    start_server();