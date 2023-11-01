import atexit
import logging
import logging.config
import os
import random
import re
import schedule
import socket
import sys
import time
import threading
import zoneinfo
from datetime import datetime, timedelta
from image_generator import generate_image_base64, generate_lpr_image_base64


# CONSTANTS
SERVER_TIMEOUT = 11
BUFFER = 1024
MODULE_ID = 'KY-DV-D2'  # move to settings file
START_MSG_ID = 1  # move to settings file
Camera_Unit_ID = 'KY-DV-D2' # NOT USED
TIMEZONE = 'Europe/Kyiv'


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
        conn.close()
        stop_scheduler.set()

    def __send_keep_alive(conn):
        conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))

    def __process_DetectionRequest(data, conn):
        global msg_id

        # data = data.decode()
        data = data.rstrip('\x00')
        try:
            request_data = {item.split(':')[0]: ''.join(item.split(':')[1:]) for item in data.split('|')}

            # send response to CAMEA
            response_data = dict()
            response_data['msg'] = 'DetectionRequestRepeat'
            response_data['ModuleID'] = request_data['RequestedSensor'] if 'RequestedSensor' in request_data else MODULE_ID
            response_data['RequestID'] = request_data['RequestID'] if 'RequestID' in request_data else 'no_request_ID_in_the_request'

            try:
                dt = datetime.strptime(request_data['ImageTime'], '%Y%m%dT%H%M%S%f%z')
                # generate random response time with tolerance 250
                dt_response = dt + timedelta(milliseconds=random.randomint(-250, 250))
            except Exception:
                logger.error(f"Incorrect datetime in the DetectionRequest: {response_data['RequestID']}")
                dt_response = datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE))

            response_data['ImageID'] = (Camera_Unit_ID + '_' + datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                                                             + datetime.strftime(dt_response, '%z'))
            response_data['TimeDet'] = (datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                                        + datetime.strftime(dt_response, '%z'))
            # response_data['ImageID'] = (Camera_Unit_ID + '_' + datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).strftime('%Y%m%dT%H%M%S%f')[:-3]
            #                                                  + datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).strftime('%z'))
            # response_data['TimeDet'] = (datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).strftime('%Y%m%dT%H%M%S%f')[:-3]
            #                             + datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).strftime('%z'))
            response_data['LP'] = 'AA1234AA'
            response_data['ILPC'] = 'UA'
            response_data['IsDetection'] = 1

            response_data_str = '|'.join([f'{key}:{value}' for key, value in response_data.items()])

            response = (bytearray(b'\x44\x41\x74\x50')
                        + msg_id.to_bytes(2, 'little')
                        + bytearray(b'\x00\x00')
                        + len(response_data_str).to_bytes(4, 'little')
                        + response_data_str.encode('UTF-8'))
            conn.sendall(response)
            logger.info(f"Send response: '{response}'")

            # send picture to CAMEA
            response2_data = dict()
            response2_data['msg'] = 'LargeDetection'
            response2_data['ModuleID'] = response_data['ModuleID']
            response2_data['ImageID'] = response_data['ImageID']
            response2_data['TimeDet'] = (datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).strftime('%Y%m%dT%H%M%S%f')[:-3]
                                         + datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).strftime('%z'))
            response2_data['UT'] = datetime.now(tz=zoneinfo.ZoneInfo(TIMEZONE)).isoformat(timespec="milliseconds")
            response2_data['ExtraCount'] = 0
            response2_data['LPText'] = 'AA1234AA'
            response2_data['ILPC'] = 'UA'
            response2_data['LpJpeg'] = generate_lpr_image_base64('AA 1234 AA')
            response2_data['FullImage64'] = generate_image_base64(f'stub image for {response_data["RequestID"]}, TimeDet: {response2_data["TimeDet"]}')
            response2_data_str = '|'.join([f'{key}:{value}' for key, value in response2_data.items()])

            ip = 'localhost'
            port = 5050
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                s2.connect((ip, port))
                s2.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
                s2_response = str(s2.recv(BUFFER), 'ascii')
                logger.info(f"Received data: '{s2_response}' from {ip}:{port}")
                img_response = (bytearray(b'\x44\x41\x74\x50')
                                + msg_id.to_bytes(2, 'little')
                                + bytearray(b'\x00\x00')
                                + len(response2_data_str).to_bytes(4, 'little')
                                + response2_data_str.encode('UTF-8'))
                s2.sendall(img_response)
                logger.info("Send images to 'localhost':5050")
                s2.close()

        except Exception as e:
            logger.exception(e)

    # Start the background thread
    stop_scheduler = __run_scheduler()
    atexit.register(__atexit)

    msg_id = START_MSG_ID
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
            buffer = str()
            queries = queue.Queue()

            with conn:
                # sending handshake
                conn.sendall(bytearray(b'\x48\x53\x78\x78'))
                logger.info("Connection established with: " + str(addr))

                schedule.every(3).seconds.do(__send_keep_alive, conn)
                logger.debug("Keep alive message send")

                while conn:
                    data = conn.recv(BUFFER)
                    try:
                    #     if not isinstance(data, str):
                    #         data = data.decode('ISO-8859-1')
                        data = data.decode('ISO-8859-1')
                    except Exception as e:
                        logger.error(f"Failed to decode: '{data}' - " + str(e))
                    buffer = buffer + data
                    data = ''

                    splitted_buffer = re.findall(r'.+?(?=DAtP|Hsxx|$)', buffer, flags=re.DOTALL)
                    if len(splitted_buffer) > 1:
                        for i in range(len(splitted_buffer) - 1):
                            queries.put(splitted_buffer[i])
                        buffer = splitted_buffer[-1]

                    while not queries.empty():
                        query = queries.get()
                        logger.info(f"Received data: '{query}' from {str(addr)}")

                        # check if it is request for camera images
                        try:
                            if "msg:DetectionRequest" in query:
                                logger.debug('DetectionRequest catched')
                                __process_DetectionRequest(query, conn)
                            else:
                                logger.debug('not a DetectionRequest')
                        except Exception as e:
                            logger.error(e)

        except KeyboardInterrupt:
            __atexit()