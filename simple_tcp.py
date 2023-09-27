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


class mTCPHandler(socketserver.StreamRequestHandler):

    def handle(self):
        # data = str(self.request.recv(1024), 'ascii')
        # data = self.request.recv(1024)
        data = self.rfile.readline().strip()
        logger.info(data.hex())
        cur_thread = threading.current_thread()
        response = bytes("{}: {}".format(cur_thread.name, data), 'ascii')
        # self.request.sendall(response)
        logger.info(response)


if __name__ == "__main__":
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "", 7_777

    def __run_scheduler(interval=1):
        scheduler_event = threading.Event()

        class ScheduleThread(threading.Thread):
            @classmethod
            def run(cls):
                while not scheduler_event.is_set():
                    schedule.run_pending()
                    time.sleep(interval)

        continuous_thread = ScheduleThread()
        continuous_thread.start()
        return scheduler_event

    def __atexit():
        stop_scheduler.set()

    def __shutdown(server):
        logger.info("Server was shutdown because running time expired")
        server.shutdown()
        stop_scheduler.set()

    # Start the background thread
    stop_scheduler = __run_scheduler()
    atexit.register(__atexit)

    server = socketserver.TCPServer((HOST, PORT), mTCPHandler, bind_and_activate=True)
    with server:
        ip, port = server.server_address

        server_thread = threading.current_thread()
        logger.info("Server loop running in thread:" + server_thread.name)

        schedule.every(180).minutes.do(__shutdown, server)
        logger.info("Terminate scheduler set for 180 minutes:" + server_thread.name)

        server.serve_forever()
