import threading
import socket
import logging
import logging.config
import os
import schedule
import time
import atexit
import sys


# CONSTANTS
SERVER_TIMEOUT = 5


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

if __name__ == "__main__":
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "127.0.0.1", 7_777

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

    def __shutdown(s):
        logger.info("Server was shutdown because running time expired")
        s.close()
        stop_scheduler.set()

    def __send_keep_alive(conn):
        conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))

    # Start the background thread
    stop_scheduler = __run_scheduler()
    atexit.register(__atexit)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        s.settimeout(SERVER_TIMEOUT)

        socket_thread = threading.current_thread()
        logger.info("Start socket listening in thread:" + socket_thread.name)

        schedule.every(2).minutes.do(__shutdown, s)
        logger.info("Terminate scheduler set for 2 minutes:" + socket_thread.name)

        try:
            conn, addr = s.accept()
            with conn:
                # sending handhsake
                conn.sendall(bytearray(b'\x48\x53\x78\x78'))
                logger.info("Connection established with: " + str(addr))
                while True:
                    schedule.every(3).seconds.do(__send_keep_alive, conn)
                    logger.debug("Keep alive message send")

                    data = conn.recv(1024)
                    logger.info(f"Received data: '{data}' from {str(addr)}")
                    # conn.sendall(bytearray(b'\x48\x53\x78\x78'))
        except KeyboardInterrupt:
            __atexit()
