import socket


# for testing
def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
        print("a")
        response = str(sock.recv(1024), 'ascii')
        print("Received: {}".format(response))


if __name__ == "__main__":
    ip, port = "localhost", 7_777

    client(ip, port, "Hello World!")

