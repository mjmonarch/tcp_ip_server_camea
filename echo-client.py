import socket


IP = 'localhost'
PORT = 5050

if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((IP, PORT))
        s.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
        response = str(s.recv(1024), 'ascii')
        print("Received: {}".format(response))
