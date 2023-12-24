# import requests
# import sys
# import xml.etree.ElementTree as ET
# from datetime import datetime
import logging
import socket
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
    send_stab_image_data(id, dt_response, request, config) --> None
        Sends the autogenerated stab images to the Camea Database
    send_image_data(id, dt_response, request, config, img) --> None
        Sends the received from the Vidar DB image to the Camea Database
    """

    def __init__(self, db_ip: str, db_port: int, buffer: int):
        self.DB_IP = db_ip
        self.DB_PORT = db_port
        self.buffer = int(buffer)

        ### KKK
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((self.DB_IP, self.DB_PORT))

        # handshake
        self.conn.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
        s2_response = str(self.conn.recv(int(self.buffer), 'ascii'))
        logger.info((f"Received data: '{s2_response}'"
                    + f"from {self.DB_IP}:{self.DB_PORT}"))

    def send_image_found_response(self, conn: socket, id: int, dt_response: datetime,
                                  request: dict, config: dict,
                                  lp: str = 'AA1234AA', country: str = 'UA') -> None:
        """
        Sends the response to the CAMEA DB Management Software query

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
        response['ModuleID'] = (request['RequestedSensor']
                                if 'RequestedSensor' in request
                                else config['service']['module_id'])
        response['RequestID'] = request['RequestID']
        # response['ImageID'] = (settings['Camera_Unit_ID'] + '_'
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
        conn.sendall(response_bytes)
        logger.info(f"Response to CAMEA DB Management Software has been sent: '{response_bytes}'")

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
        response['ModuleID'] = (request['RequestedSensor']
                                if 'RequestedSensor' in request
                                else config['service']['module_id'])
        # response['ImageID'] = (settings['Camera_Unit_ID'] + '_'
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

        ### KKK
        img_response = (bytearray(b'\x44\x41\x74\x50')
                        + id.to_bytes(2, 'little')
                        + bytearray(b'\x00\x00')
                        + len(response_str).to_bytes(4, 'little')
                        + response_str.encode('UTF-8'))
        self.conn.sendall(img_response)

        s2_response = str(self.conn.recv(config.getint('settings', 'buffer')), 'ascii')
        logger.info((f"XXXXX: '{s2_response}'"
                     + f"from {config['camea_db']['ip']}:{config['camea_db']['port']}"))

        logger.info(("Send images to CAMEA BD at "
                     + f"{config['camea_db']['ip']}:{config['camea_db']['port']}"))

        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
        #     s2.connect((config['camea_db']['ip'], config.getint('camea_db', 'port')))

        #     # handshake
        #     s2.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
        #     s2_response = str(s2.recv(config.getint('settings', 'buffer')), 'ascii')
        #     logger.info((f"Received data: '{s2_response}'"
        #                  + f"from {config['camea_db']['ip']}:{config['camea_db']['port']}"))

        #     img_response = (bytearray(b'\x44\x41\x74\x50')
        #                     + id.to_bytes(2, 'little')
        #                     + bytearray(b'\x00\x00')
        #                     + len(response_str).to_bytes(4, 'little')
        #                     + response_str.encode('UTF-8'))
        #     s2.sendall(img_response)

        #     #### DDD
            # s2_response = str(s2.recv(config.getint('settings', 'buffer')), 'ascii')
            # logger.info((f"XXXXX: '{s2_response}'"
            #              + f"from {config['camea_db']['ip']}:{config['camea_db']['port']}"))


            # logger.info(("Send images to CAMEA BD at "
            #              + f"{config['camea_db']['ip']}:{config['camea_db']['port']}"))
            # s2.close()

        #     ### DDD
        response['LpJpeg'] = response['LpJpeg'][:10]
        response['FullImage64'] = response['FullImage64'][:10]
        response_str = '|'.join([f'{key}:{value}' for key, value in response.items()])
        img_response = (bytearray(b'\x44\x41\x74\x50')
                        + id.to_bytes(2, 'little')
                        + bytearray(b'\x00\x00')
                        + len(response_str).to_bytes(4, 'little')
                        + response_str.encode('UTF-8'))
        logger.info(f"Images to Camea DB have been sent: '{img_response}'")

            ### DDD
            # with open("logs/test_img.txt", "a") as writer:
            #     response = dict()
            #     response['msg'] = 'LargeDetection'
            #     response['ModuleID'] = (request['RequestedSensor']
            #                             if 'RequestedSensor' in request
            #                             else config['service']['module_id'])
            #     response['ImageID'] = (config['settings']['camera_unit_id'] + '_'
            #                            + datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
            #                            + datetime.strftime(dt_response, '%z'))
            #     response['TimeDet'] = (datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
            #                            + datetime.strftime(dt_response, '%z'))
            #     response['UT'] = dt_response.isoformat(timespec="milliseconds")
            #     response['ExtraCount'] = 0
            #     response['LPText'] = 'AA1234AA'
            #     response['ILPC'] = 'UA'
            #     response['LpJpeg'] = 'xxx'
            #     response['FullImage64'] = 'yyy'

            #     response_str = '|'.join([f'{key}:{value}' for key, value in response.items()]) + '\n\n\n'

            #     writer.write(response_str)

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
        response['ModuleID'] = (request['RequestedSensor']
                                if 'RequestedSensor' in request
                                else config['service']['module_id'])
        response['ImageID'] = (config['settings']['camera_unit_id'] + '_'
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

        # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
        #     s2.connect((config['camea_db']['ip'], config.getint('camea_db', 'port')))

        #     # handshake
        #     s2.sendall(bytearray(b'\x4b\x41\x78\x78\x00\x00\x00\x00\x00\x00\x00\x00'))
        #     s2_response = str(s2.recv(config.getint('settings', 'buffer')), 'ascii')
        #     logger.info((f"Received data: '{s2_response}'"
        #                  + f"from {config['camea_db']['ip']}:{config['camea_db']['port']}"))

        #     img_response = (bytearray(b'\x44\x41\x74\x50')
        #                     + id.to_bytes(2, 'little')
        #                     + bytearray(b'\x00\x00')
        #                     + len(response_str).to_bytes(4, 'little')
        #                     + response_str.encode('UTF-8'))
        #     s2.sendall(img_response)
        #     logger.info(("Send images to CAMEA BD at "
        #                  + f"{config['camea_db']['ip']}:{config['camea_db']['port']}"))
        #     s2.close()

        img_response = (bytearray(b'\x44\x41\x74\x50')
                        + id.to_bytes(2, 'little')
                        + bytearray(b'\x00\x00')
                        + len(response_str).to_bytes(4, 'little')
                        + response_str.encode('UTF-8'))
        self.conn.sendall(img_response)
        logger.info(("Send images to CAMEA BD at "
                    + f"{config['camea_db']['ip']}:{config['camea_db']['port']}"))


            # ### DDD
            # with open("logs/test_img.txt", "a") as writer:
            #     response = dict()
            #     response['msg'] = 'LargeDetection'
            #     response['ModuleID'] = (request['RequestedSensor']
            #                             if 'RequestedSensor' in request
            #                             else settings['MODULE_ID'])
            #     response['ImageID'] = (settings['Camera_Unit_ID'] + '_'
            #                         + datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
            #                         + datetime.strftime(dt_response, '%z'))
            #     response['TimeDet'] = (datetime.strftime(dt_response, '%Y%m%dT%H%M%S%f')[:-3]
            #                         + datetime.strftime(dt_response, '%z'))
            #     response['UT'] = dt_response.isoformat(timespec="milliseconds")
            #     response['ExtraCount'] = 0
            #     response['LPText'] = img['LP']
            #     response['ILPC'] = img['ILPC']
            #     response['LpJpeg'] = img['LpJpeg'][:20] + '...'
            #     response['FullImage64'] = img['FullImage64'][:20] + '...'

            #     response_str = '|'.join([f'{key}:{value}' for key, value in response.items()]) + '\n\n\n'

            #     writer.write(response_str)
