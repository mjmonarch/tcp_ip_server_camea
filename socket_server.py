import atexit
import logging
import logging.config
import os
import queue
import re
import schedule
import socket
import sys
import time
import threading
import zoneinfo
from datetime import datetime
from camea_service import CameaService
from vidar_service import VidarService
from errors import IncorrectCameaQuery


###  DDD TEMP
TOTAL = 0
S0 = 0
S1 = 0
S2 = 0


# Logger settings
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


class QUERY_PROCESSOR:
    """
    Class represented Processor to operate with CAMEA DB Management Software
    that is connected via TCP/IP.
    Received and parsed queries form the CAMEA DB Management Software,
    afterwars queries the Vidar database for appropriate photos.
    Program's entry point.

    Constants:
    -----------
    AVAILABLE_COMMANDS - dict with available commands to receive via TCP/IP.
    Now only "DetectionRequest" command is supported

    Parameters:
    -----------
    # TODO: add descripton of the parameters and where they are stored

    Methods:
    -----------
    process_DetectionRequest(data, conn) --> None
        Tries to process Detection request: get the appropriate photos
        from Vidar database and send it to the CAMEA DB Management Software
    main() --> None
        Main program loop.
    """

    def __init__(self):
        # TODO: move to file
        # Socket server settings
        self.SETTINGS = dict()
        self.SETTINGS['SERVER_TIMEOUT'] = 11
        self.SETTINGS['BUFFER'] = 1024
        self.SETTINGS['HOST'] = '127.0.0.1'
        self.SETTINGS['PORT'] = 7_777  # Port 0 means to select an arbitrary unused port
        self.SETTINGS['INITIAL_MSG_ID'] = 1  # move to settings file # get start_message_id from the temp file, save to temp file after
        self.SETTINGS['Camera_Unit_ID'] = 'CAMERA_1'  # NOT USED
        self.SETTINGS['MODULE_ID'] = 'KY-DV-D2'  # move to settings file
        self.SETTINGS['TIMEZONE'] = 'Europe/Kyiv'
        self.SETTINGS['MODE'] = 'VIDAR'  # also 'TEST' mode is available when the stub pictures are generated automatically
        # check for appropriate values
        self.SETTINGS['WORKING_TIME'] = 60  # set service working time in minutes, 0 means working infinite time
        self.SETTINGS['VIDAR_IP'] = '192.168.6.161'
        self.SETTINGS['TOLERANCE'] = 300  # tolerance (in ms) for querying the vidar database
        self.SETTINGS['CAMEA_DB_IP'] = '127.0.0.1'
        self.SETTINGS['CAMEA_DB_PORT'] = 5_050

        self.msg_id = self.SETTINGS['INITIAL_MSG_ID'] # TODO: change!!!
        self.vidar_service = VidarService(ip=self.SETTINGS['VIDAR_IP'])
        self.camea_service = CameaService(db_ip=self.SETTINGS['CAMEA_DB_IP'],
                                          db_port=self.SETTINGS['CAMEA_DB_PORT'])

    def __send_keep_alive(self, conn):
        conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))

    def __send_handshake(self, conn):
        conn.sendall(bytearray(b'\x48\x53\x78\x78'))

    def process_DetectionRequest(self, data, conn):
        """
        Tries to process Detection request:
        1: VIDAR mode - gets the appropriate photos from Vidar database
        and send it to the CAMEA DB Management Software
        2: TEST mode - autogenerates images stubs
        and send it to the CAMEA DB Management Software

        Parameters:
        -----------
        data: string
            TCP/IP CAMEA DetectionRequest query decoded in ISO-8859-1 format
        conn: socket object
            Established connection with CAMEA DB Management Software

        Output:
        -----------
        """

        data = data.rstrip('\x00')
        try:
            request_data = {item.split(':')[0]: ''.join(item.split(':')[1:])
                            for item in data.split('|')}
            try:
                dt = datetime.strptime(request_data['ImageTime'], '%Y%m%dT%H%M%S%f%z')
            except Exception:
                msg = f"Incorrect datetime in the DetectionRequest: {request_data['ImageTime']}"
                raise IncorrectCameaQuery(msg)

            if 'RequestID' not in request_data:
                msg = "Missing ID in the DetectionRequest"
                raise IncorrectCameaQuery(msg)

            # get transit images
            if self.SETTINGS['MODE'] == 'VIDAR':
                # search for IDs in vidar database with given datetime ± tolerance
                vidar_ids = self.vidar_service.get_ids(transit_timestamp=dt,
                                                       tolerance=self.SETTINGS['TOLERANCE'])
                
                #### DDDDDDDDDD
                global TOTAL, S0, S1, S2
                TOTAL += 1
                if vidar_ids:
                    S0 += 1
                else:
                    time.sleep(1)
                    vidar_ids = self.vidar_service.get_ids(transit_timestamp=dt,
                                                       tolerance=self.SETTINGS['TOLERANCE'])
                    if vidar_ids:
                        S1 += 1
                    else:
                        time.sleep(1)
                        vidar_ids = self.vidar_service.get_ids(transit_timestamp=dt,
                                                       tolerance=self.SETTINGS['TOLERANCE'])
                        if vidar_ids:
                            S2 += 1
                  
                if vidar_ids:
                    logger.debug(f"DDD: Received vidar ids keys: {vidar_ids.keys()} from {vidar_ids}")
                    # search for the image that is the closest to requested timestamp
                    dt_ts = int(dt.timestamp()*1_000)
                    vidar_ids_deviation = [abs(dt_ts - int(ts)) for ts in vidar_ids.keys()]
                    logger.debug(f"DDD: Vidar ids deviation: {vidar_ids_deviation}")
                    best_fit = vidar_ids_deviation.index(min(vidar_ids_deviation))
                    logger.debug(f"DDD: Vidar ids best fit index: {best_fit}")
                    id = list(vidar_ids.values())[best_fit]
                    # get the image with given ID from the Vidar database
                    img = self.vidar_service.get_data(id)
                    # transfer best_fit from timestamp into datetime
                    timezone = zoneinfo.ZoneInfo(self.SETTINGS['TIMEZONE'])
                    dt_vidar = datetime.fromtimestamp(best_fit, tz=timezone)
                    # send response to the CAMEA DB Management Software
                    self.camea_service.send_image_found_response(conn=conn,
                                                                 id=self.msg_id,
                                                                 dt_response=dt_vidar,
                                                                 request=request_data,
                                                                 settings=self.SETTINGS,
                                                                 lp=img['LP'],
                                                                 country=img['ILPC'])
                    self.camea_service.send_image_data(id=self.msg_id,
                                                       dt_response=dt_vidar,
                                                       request=request_data,
                                                       settings=self.SETTINGS,
                                                       img=img)
                else:
                    # send response to the CAMEA DB Management Software
                    # self.camea_service.send_no_image_found_response(conn, request_data, self.SETTINGS)
                    # TODO: figure out is it needed to send answer to CAMEA DB Management Software
                    # if no image found
                    pass
                self.msg_id += 1
            elif self.SETTINGS['MODE'] == 'TEST':
                # send response to the CAMEA DB Management Software
                self.camea_service.send_image_found_response(conn,
                                                             id=self.msg_id,
                                                             dt_response=dt,
                                                             request=request_data,
                                                             settings=self.SETTINGS)
                self.camea_service.send_stab_image_data(id=self.msg_id,
                                                        dt_response=dt,
                                                        request=request_data,
                                                        settings=self.SETTINGS)
                self.msg_id += 1

        # detalize exceptions!!!
        except Exception as e:
            logger.exception(e)

    def main(self):
        """
        Runs the programs main loop

        Parameters:
        -----------

        Output:
        -----------
        """

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

            #### DDDDDDDDDD
            global TOTAL, S0, S1, S2

            logger.info(f"total: {TOTAL}")
            logger.info(f"got without delay: {S0}")
            logger.info(f"got with delay 1s: {S1}")
            logger.info(f"got with delay 2s: {S2}")

            with open("logs/statistic.log", "a") as writer:
                writer.write("total: ".ljust(20), TOTAL, "\n")
                writer.write("got without delay: ".ljust(20), S0, "\n")
                writer.write("got with delay 1s: ".ljust(20), S1, "\n")
                writer.write("got with delay 2s: ".ljust(20), S2, "\n")

        # Start the background thread
        stop_scheduler = __run_scheduler()
        atexit.register(__atexit)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.SETTINGS['HOST'], self.SETTINGS['PORT']))
            s.listen()
            s.settimeout(self.SETTINGS['SERVER_TIMEOUT'])

            socket_thread = threading.current_thread()
            logger.info(f"Service started at {self.SETTINGS['HOST']}:{self.SETTINGS['PORT']}")
            logger.info("Start socket listening in thread:" + socket_thread.name)

            if self.SETTINGS['WORKING_TIME'] > 0:
                schedule.every(self.SETTINGS['WORKING_TIME']).minutes.do(__shutdown, s)
                logger.info((f"Terminate scheduler set for {self.SETTINGS['WORKING_TIME']} "
                            + f"minutes: {socket_thread.name}"))
            try:
                conn, addr = s.accept()
                buffer = str()
                queries = queue.Queue()

                with conn:
                    # sending handshake
                    self.__send_handshake(conn)
                    logger.info("Connection established with: " + str(addr))

                    # sending keep alive messages every 3 seconds
                    schedule.every(3).seconds.do(self.__send_keep_alive, conn)
                    logger.debug("Keep alive message send")

                    while conn:
                        data = conn.recv(self.SETTINGS['BUFFER'])
                        try:
                            data = data.decode('ISO-8859-1')
                        except Exception as e:
                            logger.error(f"Failed to decode: '{data}' - " + str(e))
                        buffer = buffer + data
                        data = ''

                        splitted_buffer = re.findall(r'.+?(?=DAtP|Hsxx|KAxx|$)',
                                                     buffer, flags=re.DOTALL)
                        if len(splitted_buffer) > 1:
                            for i in range(len(splitted_buffer) - 1):
                                queries.put(splitted_buffer[i])
                            buffer = splitted_buffer[-1]

                        while not queries.empty():
                            query = queries.get()
                            logger.debug(f"Received data: '{query}' from {str(addr)}")

                            # check if it is request for camera images
                            try:
                                if "msg:DetectionRequest" in query:
                                    logger.info(f"Received data: '{query}' from {str(addr)}")
                                    logger.debug('DetectionRequest catched')
                                    self.process_DetectionRequest(data=query, conn=conn)
                                else:
                                    logger.debug('not a DetectionRequest')
                            except Exception as e:
                                logger.error(e)

            except KeyboardInterrupt:
                __atexit()


if __name__ == "__main__":
    query_processor = QUERY_PROCESSOR()
    query_processor.main()
