import socket
import threading
import socketserver
import logging
import logging.config
import os
import schedule
import time
import atexit
import sys
from errors import SocketCorrupted


LOG_FILE = "logs/log.log"
LOGGING_SETTINGS = {
    "handlers": [],
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "datefmt": "%d.%m.%Y %H:%M:%S,uuu",
    "level": logging.DEBUG,
}
file_handler = logging.handlers.RotatingFileHandler(
    filename=os.path.join(os.getcwd(), LOG_FILE),
    encoding="utf-8",
    mode="a",
    maxBytes=1_000_000,
    backupCount=5,
)
file_handler.setLevel(logging.INFO)
LOGGING_SETTINGS["handlers"].append(file_handler)

stream_handler = logging.StreamHandler(stream=sys.stdout)
LOGGING_SETTINGS["handlers"].append(stream_handler)

logging.basicConfig(**LOGGING_SETTINGS)
logger = logging.getLogger(__name__)


# for testing
def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
        response = str(sock.recv(1024), 'ascii')
        print("Received: {}".format(response))


if __name__ == "__main__":
    HOST, PORT = "localhost", 50501
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logger.info(f'Connecting to Camea XXX at {HOST}: {PORT}')
    conn.connect((HOST, PORT))
    # handshake
    # conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
    # logger.info(f"Handshake was sent to {conn.getpeername()}")
    # s2_response = str(conn.recv(1024), 'ascii')
    # logger.info((f"Received data: '{s2_response}'"
    #              + f"from {HOST}:{PORT}"))

    while conn:
        try:
            data = conn.recv(1024)
        except AttributeError:
            raise SocketCorrupted("can't read from socket")    
        try:
            data = data.decode('ISO-8859-1')
        except Exception as e:
            logger.error(f"Failed to decode: '{data}' - " + str(e))
        logger.info(f"Data received: {data}")
