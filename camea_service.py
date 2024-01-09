import atexit
import logging
import schedule
import socket
import sys
import time
import threading
from datetime import datetime
from image_generator import ImageGenerator

# set logger
logger = logging.getLogger(__name__)


class CameaService:
    """
    Class represented service for sending responses to
    CAMEA Database Management Software

    Constants:
    -----------

    Parameters:
    db_ip
        Camea Database for image storing IP address
    db_port
        Camea Database for image storing PORT

    Methods:
    send_image_found_response(conn, id, img, request, config, lp, country) --> None
        Sends the response to the CAMEA DB Management Software query
        with the found image credentials
    send_image_not_found_response(conn, id, img, request, config, lp, country) --> None
        Sends the response to the CAMEA DB Management Software query
        that image was not found
    send_stab_image_data(id, dt_response, request, config) --> None
        Sends the autogenerated stab images to the Camea Database
    send_image_data(id, dt_response, request, config, img) --> None
        Sends the received from the Vidar DB image to the Camea Database
    """

    def __init__(self, db_ip: str, db_port: int, buffer: int):
        self.DB_IP = db_ip
        self.DB_PORT = db_port
        self.buffer = buffer

        # initiate Camea DB connection
        self.conn = self.__create_connection()

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

        # def __atexit():
        #     stop_scheduler.set()

        # def __shutdown(s):
        #     self.conn.close()
        #     stop_scheduler.set()

        def __send_keep_alive_2():
            try:
                self.conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
                ### DDD
                logger.info(f"Keep alive was sent to {self.conn.getpeername()}")
            except ConnectionResetError as e:
                logger.error(f'Connection to Camea DB was reset by the peer: {e}')
                self.conn = self.__create_connection()
            except socket.error as e:
                logger.error('An error occurred while sending keep alive to : '
                             + f'Camea DB: {e}')

        # Start the background thread
        self.stop_scheduler = __run_scheduler()
        atexit.register(self.__atexit)
        # sending keep alive messages every 3 seconds
        schedule.every(3).seconds.do(__send_keep_alive_2)

    def __atexit(self):
        schedule.clear()
        self.stop_scheduler.set()
        logger.info('Connection to Camea DB was closed')

    def __shutdown(self):
        schedule.clear()
        self.stop_scheduler.set()
        self.conn.close()

    def __create_connection(self):
        conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.info(f'Connecting to Camea DB at {self.DB_IP}: {self.DB_PORT}')
        conn.connect((self.DB_IP, self.DB_PORT))
        # handshake
        conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
        ### DDD
        logger.info(f"Handshake was sent to {conn.getpeername()}")
        s2_response = str(conn.recv(self.buffer), 'ascii')
        logger.info((f"Received data: '{s2_response}'"
                    + f"from {self.DB_IP}:{self.DB_PORT}"))
        return conn

    def send_image_found_response(self, conn: socket, id: int, dt_response: datetime,
                                  request: dict, config: dict,
                                  lp: str = 'AA1234AA', country: str = 'UA') -> None:
        """
        Sends the response to the CAMEA DB Management Software query
        with the found image credentials

        Parameters:
        -----------
        conn: socket object
            Established connection with CAMEA DB Management Software
        id: int
            message id
        dt_response: datetime
            response timestamp
        request_data: dict
            original DetectionRequest data from the CAMEA DB Management Software
        config: config
            Query Processor settings
        lp: str
            Licence plate text
        country: str
            Licence plate country code

        Output:
        -----------
        """
        response = dict()
        response['msg'] = 'DetectionRequestRepeat'
        response['ModuleID'] = config['service']['module_id']
        response['RequestID'] = request['RequestID']
        response['ImageID'] = (response['ModuleID'] + '_'
                               + datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                               + datetime.strftime(dt_response, '%z'))
        response['TimeDet'] = (datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                               + datetime.strftime(dt_response, '%z'))
        response['LP'] = lp
        response['ILPC'] = country
        response['IsDetection'] = 1 if lp else 0

        response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])

        response_bytes = (bytearray(b'\x44\x41\x74\x50')
                          + id.to_bytes(2, 'little')
                          + bytearray(b'\x00\x00')
                          + len(response_str).to_bytes(4, 'little')
                          + response_str.encode('UTF-8'))
        try:
            conn.sendall(response_bytes)
            logger.info(f"Response to CAMEA DB Management Software at {conn.getpeername()}"
                        + f"has been sent: {response_bytes}")
        except ConnectionResetError as e:
            logger.error(f'Connection to Camea DB Management Software was reset by the peer: {e}')

    def send_image_not_found_response(self, conn: socket, id: int,
                                      request: dict, config: dict) -> None:
        """
        Sends the response to the CAMEA DB Management Software query
        with the found image credentials

        Parameters:
        -----------
        conn: socket object
            Established connection with CAMEA DB Management Software
        id: int
            message id
        dt_response: datetime
            response timestamp
        request_data: dict
            original DetectionRequest data from the CAMEA DB Management Software
        config: config
            Query Processor settings
        lp: str
            Licence plate text
        country: str
            Licence plate country code

        Output:
        -----------
        """
        response = dict()
        response['msg'] = 'DetectionRequestRepeat'
        response['ModuleID'] = config['service']['module_id']
        response['RequestID'] = request['RequestID']
        response['ImageID'] = 'NULL'

        response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])

        response_bytes = (bytearray(b'\x44\x41\x74\x50')
                          + id.to_bytes(2, 'little')
                          + bytearray(b'\x00\x00')
                          + len(response_str).to_bytes(4, 'little')
                          + response_str.encode('UTF-8'))
        try:
            conn.sendall(response_bytes)
            logger.info("Response to CAMEA DB Management Software has been sent: "
                        + f"{response_bytes}")
        except ConnectionResetError as e:
            logger.error(f'Connection to Camea DB Management Software was reset by the peer: {e}')

    def send_stab_image_data(self, id: int, dt_response: datetime,
                             request: dict, config: dict) -> None:
        """
        Sends the autogenerated stab images to the Camea Database

        vParameters:
        -----------
        id: int
            Message id
        dt_response: datetime
            Response timestamp
        request_data: dict
            Original DetectionRequest data from the CAMEA DB Management Software
        config: config
            Query Processor settings

        Output:
        -----------
        """
        image_generator = ImageGenerator('AA 1234 AA')
        response = dict()
        response['msg'] = 'LargeDetection'
        response['ModuleID'] = config['service']['module_id']
        response['ImageID'] = (response['ModuleID'] + '_'
                               + datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                               + datetime.strftime(dt_response, '%z'))
        response['TimeDet'] = (datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                               + datetime.strftime(dt_response, '%z'))
        response['UT'] = dt_response.isoformat(timespec="milliseconds")
        response['ExtraCount'] = 0
        response['LPText'] = 'AA1234AA'
        response['ILPC'] = 'UA'
        response['LpJpeg'] = image_generator.generate_lpr_image_base64()
        response['FullImage64'] = image_generator.generate_image_base64()

        response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])

        img_response = (bytearray(b'\x44\x41\x74\x50')
                        + id.to_bytes(2, 'little')
                        + bytearray(b'\x00\x00')
                        + len(response_str).to_bytes(4, 'little')
                        + response_str.encode('UTF-8'))
        try:
            self.conn.sendall(img_response)

            # log cut message
            s2_response = str(self.conn.recv(config.getint('settings', 'buffer')), 'ascii')
            logger.info(("Send images to CAMEA BD at "
                         + f"{config['camea_db']['ip']}:{config['camea_db']['port']}"))
            logger.debug((f"Camea DB response: '{s2_response}'"
                          + f"from {config['camea_db']['ip']}:{config['camea_db']['port']}"))

            response['LpJpeg'] = response['LpJpeg'][:10]
            response['FullImage64'] = response['FullImage64'][:10]
            response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])
            img_response = (bytearray(b'\x44\x41\x74\x50')
                            + id.to_bytes(2, 'little')
                            + bytearray(b'\x00\x00')
                            + len(response_str).to_bytes(4, 'little')
                            + response_str.encode('UTF-8'))
            logger.debug(f"Images to Camea DB have been sent: '{img_response}'")
        except ConnectionResetError as e:
            logger.error(f'Connection to Camea DB was reset by the peer: {e}')
            self.conn = self.__create_connection()

    def send_image_data(self, id: int, dt_response: datetime,
                        request: dict, config: dict, img: dict) -> None:
        """
        Sends the received from the Vidar DB image to the Camea Database

        vParameters:
        -----------
        id: int
            Message id
        dt_response: datetime
            Response timestamp
        request_data: dict
            Original DetectionRequest data from the CAMEA DB Management Software
        config: config
            Query Processor settings
        img: dict
            Image received from the Vidar database

        Output:
        -----------
        """
        response = dict()
        response['msg'] = 'LargeDetection'
        response['ModuleID'] = config['service']['module_id']
        response['ImageID'] = (response['ModuleID'] + '_'
                               + datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                               + datetime.strftime(dt_response, '%z'))
        response['TimeDet'] = (datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
                               + datetime.strftime(dt_response, '%z'))
        response['UT'] = dt_response.isoformat(timespec="milliseconds")
        response['ExtraCount'] = 0
        response['LPText'] = img['LP']
        response['ILPC'] = img['ILPC']
        response['LpJpeg'] = img['LpJpeg']
        response['FullImage64'] = img['FullImage64']

        response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])

        img_response = (bytearray(b'\x44\x41\x74\x50')
                        + id.to_bytes(2, 'little')
                        + bytearray(b'\x00\x00')
                        + len(response_str).to_bytes(4, 'little')
                        + response_str.encode('UTF-8'))
        try:
            self.conn.sendall(img_response)
            s2_response = str(self.conn.recv(config.getint('settings', 'buffer')), 'ascii')
            logger.info(("Send images to CAMEA BD at "
                         + f"{config['camea_db']['ip']}:{config['camea_db']['port']}"))
            logger.debug((f"Camea DB response: '{s2_response}'"
                         + f"from {config['camea_db']['ip']}:{config['camea_db']['port']}"))

            response['LpJpeg'] = response['LpJpeg'][:10]
            response['FullImage64'] = response['FullImage64'][:10]
            response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])
            img_response = (bytearray(b'\x44\x41\x74\x50')
                            + id.to_bytes(2, 'little')
                            + bytearray(b'\x00\x00')
                            + len(response_str).to_bytes(4, 'little')
                            + response_str.encode('UTF-8'))
            logger.debug(f"Images to Camea DB have been sent: '{img_response}'")
        except ConnectionResetError as e:
            logger.error(f'Connection to Camea DB was reset by the peer: {e}')
            self.conn = self.__create_connection()

    def close_camea_db_connection(self):
        ### TODO: ADD DESCRIPTION
        self.__shutdown()
