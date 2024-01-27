import configparser
import socket
import logging
import logging.config
import os
import sys
from vidar_service import VidarService


LOG_FILE = "logs/sw_trigger.log"
LOGGING_SETTINGS = {
    "handlers": [],
    "format": "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
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


class SoftwareTrigger:
    """
    Class represented Processor that sends the software trigger to Vidar
    camera when receives push message from the CAMEA Push Software
    that is connected via TCP/IP.
    Sends an immediate sofrware trigger for event that is equal to
    configured.

    Constants:
    -----------

    Parameters:
    -----------
    Parameters are stored in the 'config.ini' file

    Methods:
    -----------
    send_immediate_trigger() --> None
        Sends an immediate software trigger to the vidar camera
    main() --> None
        Main program loop.
    """

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.initiated = SoftwareTrigger.__check_config(self.config)
        if self.initiated:
            self.vidar_service = VidarService(ip=self.config['vidar']['ip'])

    @classmethod
    def __check_config(cls, config):
        # check config structure
        if not {'vidar', 'software_trigger'}.issubset(config.sections()):
            logger.critical('Configuration file does not have appropriate structure')
            return False

        # check vidar section
        if not {'ip', }.issubset(config['vidar']):
            logger.critical('Configuration file vidar section: missing values')
            return False

        # check software_trigger section
        if not {'ip', 'port', 'loop_state_changed'}.issubset(config['software_trigger']):
            logger.critical('Configuration file software__trigger section: missing values')
            return False
        try:
            config.getint('camea_push', 'port')
        except Exception as e:
            logger.critical('Invalid datatype for data in software_trigger section: ' + str(e))
            return False

        return True

    def __create_connection(self):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ip = self.config['software_trigger']['ip']
            port = self.config.getint('software_trigger', 'port')
            logger.info(f'Connecting to Camea Push System at {ip}: {port}')
            conn.connect((ip, port))
        except socket.error as e:
            logger.error("Failed to connect to Camea Push  System  at: "
                         + f"{self.config['software_trigger']['ip']}:"
                         + f"{self.config.getint('software_trigger', 'port')} - {e}")
            sys.exit(1)
        return conn

    def main(self):
        """
        Runs the programs main loop

        Parameters:
        -----------

        Output:
        -----------
        """
        # get connection to the Camea Push System
        client = self.__create_connection()

        # start the main loop
        while client:
            try:
                try:
                    data = client.recv(1024)
                except AttributeError:
                    logger.error("Failed to read from socket")
                try:
                    data = data.decode('ISO-8859-1')
                    logger.info(f"Data received: {data}")
                except Exception as e:
                    logger.error(f"Failed to decode: '{data}' - " + str(e))

                request_data = {item.split(':')[0]: ''.join(item.split(':')[1:])
                                for item in data.split('|')}

                if 'msg' not in request_data or 'ChangedTo' not in request_data:
                    logger.error('Incorrect format of input message')
                else:
                    if (request_data['msg'] == 'LoopStateChanged' and
                        request_data['ChangedTo'] == self.config['software_trigger']['loop_state_changed']):
                        self.vidar_service.send_software_trigger()

            except ConnectionResetError as e:
                logger.error('Connection with Camea Push System was closed by Camea: '
                             + str(e))
                client = self.__create_connection()
            except TimeoutError:
                logger.error('Connection to Camea Push System was closed due to timeout')
                client = self.__create_connection()
            except KeyboardInterrupt:
                logger.error('Connection to Camea Push System was closed due to timeout')
                sys.exit(1)
            except Exception as e:
                logger.error('An error occured during runtime: ' + str(e))
                continue


if __name__ == "__main__":
    sw_trigger = SoftwareTrigger()
    if sw_trigger.initiated:
        sw_trigger.main()
