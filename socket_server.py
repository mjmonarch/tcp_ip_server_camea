import atexit
import configparser
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
    Parameters are stored in the 'config.ini' file

    Methods:
    -----------
    process_DetectionRequest(data, conn) --> None
        Tries to process Detection request: get the appropriate photos
        from Vidar database and send it to the CAMEA DB Management Software
    main() --> None
        Main program loop.
    """

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.initiated = QUERY_PROCESSOR.__check_config(self.config)
        if self.initiated:
            self.msg_id = 0
            self.vidar_service = VidarService(ip=self.config['vidar']['ip'])
            self.camea_service = CameaService(db_ip=self.config['camea_db']['ip'],
                                              db_port=self.config.getint('camea_db', 'port'),
                                              buffer=self.config.getint('settings', 'buffer'))

    @classmethod
    def __check_config(cls, config):
        # check config structure
        if not {'service', 'settings', 'vidar', 'camea_db'}.issubset(config.sections()):
            logger.critical('Configuration file does not have appropriate structure')
            return False

        # check service section
        if not {'host', 'port', 'module_id', 'mode', 'operating_time'}.issubset(config['service']):
            logger.critical('Configuration file service section: missing values')
            return False
        try:
            config.getint('service', 'port')
            config.getint('service', 'operating_time')
        except Exception as e:
            logger.critical('Invalid datatype for data in service section: ' + str(e))
            return False

        # check settings section
        if not {'buffer', 'timezone', 'timeout', 'camera_unit_id'}.issubset(config['settings']):
            logger.critical('Configuration file settings section: missing values')
            return False
        try:
            config.getint('settings', 'buffer')
            config.getint('settings', 'timeout')
        except Exception as e:
            logger.critical('Invalid datatype for data in settings section: ' + str(e))
            return False

        # check vidar section
        if not {'ip', 'tolerance'}.issubset(config['vidar']):
            logger.critical('Configuration file vidar section: missing values')
            return False
        try:
            config.getint('vidar', 'tolerance')
        except Exception as e:
            logger.critical('Invalid datatype for data in vidar section: ' + str(e))
            return False

        # check camea_db section
        if not {'ip', 'port'}.issubset(config['camea_db']):
            logger.critical('Configuration file camea_db section: missing values')
            return False
        try:
            config.getint('camea_db', 'port')
        except Exception as e:
            logger.critical('Invalid datatype for data in camea_db section: ' + str(e))
            return False

        return True

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

            # use tolerance from the configfile (if set) or from query (if 0)
            tolerance = (self.config.getint('vidar', 'tolerance') 
                         if self.config.getint('vidar', 'tolerance') > 0
                         else request_data['ToleranceMS'])

            # get transit images
            if self.config['service']['mode'] == 'VIDAR':
                # search for IDs in vidar database with given datetime ± tolerance
                vidar_ids = self.vidar_service.get_ids(transit_timestamp=dt,
                                                       tolerance=tolerance)

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
                    timezone = zoneinfo.ZoneInfo(self.config['settings']['timezone'])
                    dt_vidar = datetime.fromtimestamp(best_fit, tz=timezone)
                    # send response to the CAMEA Management Software
                    self.camea_service.send_image_found_response(conn=conn,
                                                                 id=self.msg_id,
                                                                 dt_response=dt_vidar,
                                                                 request=request_data,
                                                                 config=self.config,
                                                                 lp=img['LP'],
                                                                 country=img['ILPC'])
                    self.camea_service.send_image_data(id=self.msg_id,
                                                       dt_response=dt_vidar,
                                                       request=request_data,
                                                       config=self.config,
                                                       img=img)
                else:
                    # send response to the CAMEA DB
                    # that required image was not found
                    self.camea_service.send_image_not_found_response(conn=conn,
                                                                     id=self.msg_id,
                                                                     request=request_data,
                                                                     config=self.config)

            elif self.config['service']['mode'] == 'TEST':
                # send response to the CAMEA Management Software
                self.camea_service.send_image_found_response(conn,
                                                             id=self.msg_id,
                                                             dt_response=dt,
                                                             request=request_data,
                                                             config=self.config)
                # send response to the CAMEA DB
                self.camea_service.send_stab_image_data(id=self.msg_id,
                                                        dt_response=dt,
                                                        request=request_data,
                                                        config=self.config)
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

        # Start the background thread
        stop_scheduler = __run_scheduler()
        atexit.register(__atexit)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.config['service']['host'], self.config.getint('service', 'port')))
            s.listen()
            s.settimeout(self.config.getint('settings', 'timeout'))

            socket_thread = threading.current_thread()
            logger.info(f"Service started at {self.config['service']['host']}:"
                        + f"{self.config['service']['port']}")
            logger.info("Start socket listening in thread:" + socket_thread.name)

            operating_time = self.config.getint('service', 'operating_time')
            if operating_time > 0:
                schedule.every(operating_time).minutes.do(__shutdown, s)
                logger.info((f"Terminate scheduler set for {operating_time} "
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
                        data = conn.recv(self.config.getint('settings', 'buffer'))
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
    if query_processor.initiated:
        query_processor.main()
