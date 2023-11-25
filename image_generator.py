from PIL import Image, ImageDraw
import base64
from io import BytesIO


class ImageGenerator:
    """
    Class represented service for generating stab images

    Constants:
    -----------

    Parameters:
    -----------
    plate_number: str
        plate number to put into the picture

    Methods:
    def generate_image_base64() --> base64 str
        Returns generated 1920x1080 stab image with plate number
        in the center in the base64 string format
    def generate_lpr_image_base64() --> base64 str
        Returns generated 400x100 stab plate image with plate number
        in the center in the base64 string format
    """

    def __init__(self, text=''):
        self.text = text

    def __generate_image(self):
        img = Image.new('RGB', (1920, 1080), color=(0, 0, 0))
        d = ImageDraw.Draw(img)
        d.text((960, 540), self.text, anchor="mm", fill=(255, 255, 255), font_size=30)
        return img

    def __generate_lpr_image(self):
        img = Image.new('RGB', (400, 100), color=(240, 240, 240))
        d = ImageDraw.Draw(img)
        d.text((200, 50), self.text, anchor="mm", fill=(0, 0, 0), font_size=30)
        return img

    def generate_image_base64(self):
        """
        Returns generated 1920x1080 stab image with plate number
        in the center in the base64 string format

        Parameters:
        -----------

        Output:
        -----------
        Stab image in base64 format
        """
        img = self.__generate_image()
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue())
        return img_str.decode()

    def generate_lpr_image_base64(self):
        """
        Returns generated 400x100 stab plate image with plate number
        in the center in the base64 string format

        Parameters:
        -----------

        Output:
        -----------
        Stab plate image in base64 format
        """
        img = self.__generate_lpr_image()
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue())
        return img_str.decode()


if __name__ == '__main__':
    image_generator = ImageGenerator('AA 1234 AA')

    img_str = image_generator.generate_image_base64()
    img = Image.open(BytesIO(base64.b64decode(img_str)))
    img.save('test_img.png', 'PNG')

    img_plate_str = image_generator.generate_lpr_image_base64()
    img_plate = Image.open(BytesIO(base64.b64decode(img_plate_str)))
    img_plate.save('test_img_LPR.png', 'PNG')
