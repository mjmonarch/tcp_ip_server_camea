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


LOG_FILE = "logs/log.log"
LOGGING_SETTINGS = {
    "handlers": [],
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "datefmt": "%d.%m.%Y %H:%M:%S",
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


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        data = str(self.request.recv(1024), 'ascii')
        cur_thread = threading.current_thread()
        response = bytes("{}: {}".format(cur_thread.name, data), 'ascii')
        # self.request.sendall(response)
        logger.info(response)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


# for testing
def client(ip, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((ip, port))
        sock.sendall(bytes(message, 'ascii'))
        response = str(sock.recv(1024), 'ascii')
        print("Received: {}".format(response))


if __name__ == "__main__":
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "localhost", 14_000

    # def __run_scheduler(interval=1):
    #     scheduler_event = threading.Event()

    #     class ScheduleThread(threading.Thread):
    #         @classmethod
    #         def run(cls):
    #             while not scheduler_event.is_set():
    #                 schedule.run_pending()
    #                 time.sleep(interval)

    #     continuous_thread = ScheduleThread()
    #     continuous_thread.start()
    #     return scheduler_event

    # def __atexit():
    #     stop_scheduler.set()

    # def __shutdown(server):
    #     logger.info("Server was shutdown because running time expired")
    #     server.shutdown()

    # Start the background thread
    # stop_scheduler = __run_scheduler()
    # atexit.register(__atexit)

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        ip, port = server.server_address

        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        server_thread = threading.Thread(target=server.serve_forever)
        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()
        # logger.info("Server loop running in thread:" + server_thread.name)

        # schedule.every(10).minutes.do(__shutdown, server)
        # logger.info("Terminate scheduler set for 10 minutes:" + server_thread.name)

        # client(ip, port, "Hello World 1")
        # client(ip, port, "Hello World 2")
        # client(ip, port, "Hello World 3")

