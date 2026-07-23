#!/usr/bin/env python3
# Hybrid shell for the DSL-224:
#   - commands are injected over the serial console (small, lossless)
#   - output is redirected to a file on the router and pulled over Ethernet via nc
# This avoids dropped bytes on the UART for long output. Shell state (cd, env)
# persists because every command runs in the same console shell on the router.

import serial
import socket
import time

SERIAL_DEV = "/dev/ttyUSB2"     # adjust after re-enumeration
BAUD       = 115200
ROUTER_IP  = "192.168.1.1"
NC_PORT    = 8200
# BusyBox nc listen syntax varies. If you get "nc: bad port" etc, try:
#   "nc -l -p {p}"   or   "nc -lp {p}"   or   "nc -l {p}"
NC_LISTEN  = f"nc -l -p {NC_PORT}"

ser = serial.Serial(SERIAL_DEV, BAUD, timeout=1)

def run(cmd):
    # run command, capture stdout+stderr to a file, then serve that file once
    payload = f"{cmd} > /tmp/out.txt; {NC_LISTEN} < /tmp/out.txt\n"
    ser.reset_input_buffer()
    ser.write(payload.encode())

    # give the router time to execute and start listening, then pull with retries
    time.sleep(0.4)
    sock = None
    for _ in range(25):
        try:
            sock = socket.create_connection((ROUTER_IP, NC_PORT), timeout=2)
            break
        except OSError:
            time.sleep(0.2)
    if sock is None:
        return "[!] could not reach nc on router (wrong port syntax? router still booting?)"
    
    data = b""
    with sock:
        sock.settimeout(3)
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass

    time.sleep(0.3)  # let the router's nc fully tear down before next command
    return data.decode(errors="replace")

def main():
    print(f"[*] serial {SERIAL_DEV}@{BAUD}, output via nc {ROUTER_IP}:{NC_PORT}")
    print("[*] type 'exit' to quit\n")
    try:
        while True:
            cmd = input("$ ").strip()
            if cmd in ("exit", "quit"):
                break
            if not cmd:
                continue
            out = run(cmd)
            print(out, end="" if out.endswith("\n") else "\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        ser.close()

if __name__ == "__main__":
    main()
