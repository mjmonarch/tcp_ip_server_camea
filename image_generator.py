from PIL import Image, ImageDraw
import base64
from io import BytesIO


def generate_image(text=''):
    img = Image.new('RGB', (1920, 1080), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((960, 540), text, anchor="mm", fill=(255, 255, 255), font_size=30)
    return img


def generate_lpr_image(text=''):
    img = Image.new('RGB', (400, 100), color=(240, 240, 240))
    d = ImageDraw.Draw(img)
    d.text((200, 50), text, anchor="mm", fill=(0, 0, 0), font_size=30)
    return img


def generate_image_base64(text=''):
    img = generate_image(text)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode()


def generate_lpr_image_base64(text=''):
    img = generate_lpr_image(text)
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue())
    return img_str.decode()


if __name__ == '__main__':
    generate_image("test image").save('test_img_1.png')
    img_str = generate_image_base64('AAA')

    img = Image.open(BytesIO(base64.b64decode(img_str)))
    img.save('test_img_2.png', 'PNG')

    generate_lpr_image("AA 1234 AA").save('test_img_LPR.png')
    img_str = generate_lpr_image_base64('AA 1234 AA')
    # print(img_str)
    # a = img_str.decode()
    # print(a)
    # print(type(a))

    img = Image.open(BytesIO(base64.b64decode(img_str)))
    img.save('test_img_LPR_2.png', 'PNG')

