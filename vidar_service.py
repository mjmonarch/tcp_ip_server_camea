import logging
import requests
import sys
import xml.etree.ElementTree as ET
from datetime import datetime


# set logger
logger = logging.getLogger(__name__)


class VidarService:
    """
    Class represented service for quering the vidar database

    Constants:
    -----------

    Parameters:
    -----------

    Methods:
    send_software_trigger() --> None
        Sends software trigger to vidar
        Software trigger needs to be configured at vidar
    get_ids(transit_timestamp: datetime string, tolerance: ms) --> dict
        Returns dict of image timestamps in int format (since 1970) along
        with IDs from the range with appropriate zone
        (transit_timestamp - tolerance; transit_timestamp + tolerance)
    get_data(id: str) --> dict
        Returns dictionary with vehicle image in base64 format,
        license plate image in base64 format and license plate text
    """

    def __init__(self, ip):
        self.IP = ip

    def send_software_trigger(self) -> None:
        """
        Sends software trigger to vidar
        Software trigger needs to be configured at vidar

        Parameters:
        -----------

        Output:
        -----------
        """
        url = 'http://' + self.IP + '/trigger/swtrigger?wfilter=1&sendtrigger=1'
        r = requests.get(url)
        if r.status_code == 200:
            logger.info("Software trigger sending was successfull")
        else:
            logger.info("Software trigger sending was unsuccessfull")

    def get_ids(self, transit_timestamp, tolerance: int, zone: str) -> list:
        """
        Returns list of IDs along with image time in int format (since 1970)
        from the range (transit_timestamp - tolerance; timestamp + tolerance)
        with appropriate zone

        Parameters:
        -----------
        transit_timestamp: str
            Datetime object
        tolerance: int
            Tolerance in ms to define the search range
        zone: list
            List of appropriate zones to compare to
        Output:
        -----------
        Dictionary:
            'timestamp': image ID
        """
        result = dict()
        t1 = int(transit_timestamp.timestamp()*1_000) - tolerance
        t2 = int(transit_timestamp.timestamp()*1_000) + tolerance
        url = ('http://' + self.IP + '/lpr/cff?cmd=querydb&sql=select%20*%20from%20cffresult%20'
                         + f'where%20frametimems%20%3E%20{t1}%20and%20frametimems%20%3C%20{t2}')
        r = requests.get(url)
        root = ET.fromstring(r.content)
        for row in root.findall('row'):
            # check if it is appropriate zone
            if zone != '0' and row.find('ZONE_NAME').get('value') not in zone:
                continue
            result[row.find('FRAMETIMEMS').get('value')] = row.find('ID').get('value')
        return result

    def get_data(self, id: int) -> dict:
        """
        Returns dictionary with vehicle image in base64 format,
        license plate image in base64 format and license plate text

        Parameters:
        -----------
        ID: int
            Image ID

        Output:
        -----------
        Dictionary:
            'timestamp': image timestamp
            'LP': vehicle license plate number
            'ILPC': vehile country code
            'LpJpeg':  license plate image in base64 format
            'FullImage64': vehicle image in base64 format
        """
        result = dict()
        url = 'http://' + self.IP + f'/lpr/cff?cmd=getdata&id={id}'
        r = requests.get(url)
        root = ET.fromstring(r.content)
        if root.find('ID').get('value'):
            result['timestamp'] = root.find('capture').find('frametimems').get('value')
            result['LP'] = root.find('anpr').find('text').get('value')
            result['ILPC'] = root.find('anpr').find('country').get('value')
            result['LpJpeg'] = root.find('images').find('lp_img').get('value')
            result['FullImage64'] = root.find('images').find('normal_img').get('value')
        return result


if __name__ == '__main__':
    # in test purposes
    #  python vidar_service.py 192.168.6.161 "2023-12-06 13:00:00.000" 60000
    if len(sys.argv) != 4:
        msg = ("Invalid arguments quantity - provide IP, "
               + "timestamp in format '2023-11-18 09:54:45.000' and tolerance in ms")
        print(msg)
        exit(1)

    # set up query parameters
    IP = sys.argv[1]
    transit_timestamp = datetime.strptime(sys.argv[2], '%Y-%m-%d %H:%M:%S.%f')
    tolerance = int(sys.argv[3])

    vidar_service = VidarService(IP)
    ids = vidar_service.get_ids(transit_timestamp, tolerance)
    for id in ids.values():
        result = vidar_service.get_data(id)
        if result:
            result['LpJpeg'] = result['LpJpeg'][:20] + '...'
            result['FullImage64'] = result['FullImage64'][:20] + '...'
            print(*result.items(), sep='\n')
            print()
