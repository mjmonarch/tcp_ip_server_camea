import requests
import sys
import xml.etree.ElementTree as ET
from datetime import datetime


class VidarService:
    """
    Class represented service for quering the vidar database

    Constants:
    -----------

    Parameters:
    -----------

    Methods:
    get_ids(transit_timestamp: datetime string, tolerance: ms) --> dict
        Returns dict of image timestamps in int format (since 1970) along
        with IDs from the range
        (transit_timestamp - tolerance; transit_timestamp + tolerance)
    get_data(id: str) --> dict
        Returns dictionary with vehicle image in base64 format,
        license plate image in base64 format and license plate text
    """

    def __init__(self, IP):
        self.IP = IP

    def get_ids(self, transit_timestamp, tolerance: int) -> list:
        """
        Returns list of IDs along with image time in int format (since 1970)
        from the range (transit_timestamp - tolerance; timestamp + tolerance)

        Parameters:
        -----------
        transit_timestamp: str
            Datetime object
            Tolerance in ms to define the search range

        Output:
        -----------
        Dict of timestamp along with IDs that fit the interval
        transit_timestamp ± tolerance
        """
        result = list()
        t1 = int(transit_timestamp.timestamp()*1_000) - tolerance
        t2 = int(transit_timestamp.timestamp()*1_000) + tolerance
        url = 'https://' + self.IP + f'/lpr/cff?cmd=querydb&sql=select%20*%20from%20cffresult%20where%20frametimems%20%3E%{t1}%20and%20frametimems%20%3C%{t2}'
        r = requests.get(url, params={})
        root = ET.fromstring(r.content)
        for row in root.findall('row'):
            result[row.find('FRAMETIMEMS').get('value')] = result[row.find('ID').get('value')]
        return result

    def get_data(id: int) -> dict:
        """
        Returns dictionary with vehicle image in base64 format,
        license plate image in base64 format and license plate text

        Parameters:
        -----------
        ID: int
            Image ID

        Output:
        -----------
        Dictionary with vehicle image in base64 format,
        license plate image in base64 format and license plate text
        """
        pass


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Invalid arguments quantity - provide IP, timestamp in format '2023-11-18 09:54:45.000' and tolerance in ms")
        exit(1)

    # set up query parameters
    IP = sys.argv[1]
    transit_timestamp = datetime.strptime(sys.argv[2], '%Y-%m-%d %H:%M:%S.%f')
    tolerance = sys.argv[3]

    vidar_service = VidarService(IP)
    result = vidar_service.get_ids(transit_timestamp, tolerance)
    print(*result.items(), sep='\n')
