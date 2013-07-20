from PIL import Image
from lib.pytesser import image_to_string
from StringIO import StringIO


class CaptchaBoss(object):

    def process_str(self, image_str, **kwargs):
        image = Image.open(StringIO(image_str))
        return self.process(image, **kwargs)

    def process_path(self, path, **kwargs):
        image = Image.open(path)
        return self.process(image, **kwargs)

    def process(self, image, debug=False):
        """ Analyse the image and return the captcha value. """
        image = self._resize(image)
        debug and image.show()

        image = self._crop(image)
        debug and image.show()

        image = self._threshold(image)
        debug and image.show()
        return self._text(image)

    def _resize(self, img, factor=5):
        nx, ny = img.size
        return img.resize((int(nx*factor), int(ny*factor)), Image.BICUBIC)

    def _crop(self, img):
        nx, ny = img.size
        box = map(int, (nx * 0.15, ny * 0.25, nx * 0.85, ny * 0.75))
        return img.crop(box)

    def _threshold(self, img, threshold=160):
        lut = [255 if v > threshold else 0 for v in range(256)]
        return img.convert("L").point(lut)

    def _text(self, image):
        return image_to_string(image).strip()


import requests
import time
from bs4 import BeautifulSoup


class TenMinuteEmailBoss():

    def __init__(self):
        self.s = requests.Session()
        self.temp_email_site = 'http://10minutemail.com/'
        self.temp_email_address = self._get_temp_email_address()

    def _get_temp_email_address(self):
        resp = self.s.get(self.temp_email_site)
        soup = BeautifulSoup(resp.content)
        temp_email_address = self._get_temp_email_address_from_soup(soup)

        return temp_email_address

    def _get_confirmation_email_link(self):
        found_link = False
        num_attempts = 10

        while not found_link:
            resp = self.s.get(self.temp_email_site)
            soup = BeautifulSoup(resp.content)

            current_temp_email_address = self._get_temp_email_address_from_soup(soup)
            assert current_temp_email_address == self.temp_email_address

            email_table = soup.find('table', {'id': 'emailTable'})
            columns = email_table.findAll('td')

            if len(email_table.findAll('tr')) <= 1:
                num_attempts -= 1
                if not num_attempts > 0:
                    return ''
                else:
                    time.sleep(1)
            else:
                found_link = True

        sender = columns[1].get_text().strip()
        assert sender == 'noreply@coinad.com'

        message_link = columns[2].find('a').get('href')

        return message_link

    def _get_confirmation_code(self, msg_link):
        msg_resp = self.s.get(self.temp_email_site + msg_link)
        msg_soup = BeautifulSoup(msg_resp.content)

        text = msg_soup.find('div', {'class': 'article'}).get_text()
        idx = text.find('Login to your account')
        confirmation_code = text[idx-7:idx-2]
        return confirmation_code

    def get_confirmation_code(self):
        msg_link = self._get_confirmation_email_link()

        if not msg_link:
            print "Couldnt get the code!"
            return None

        confirmation_code = self._get_confirmation_code(msg_link)

        return confirmation_code

    def _get_temp_email_address_from_soup(self, soup):
        email_input_id = 'addyForm:addressSelect'
        temp_email_address = soup.find('input', {'id': email_input_id}).get('value')
        return temp_email_address


import requests
from bs4 import BeautifulSoup
import re


class FakeUser(object):
    """ FakeUser offers the automatization of user proceses """

    HEADERS = {
        "Host": "coinad.com",
        "Origin": 'https://coinad.com',
        'Referer': 'https://coinad.com/?a=New_Account',
        'User-Agent': 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/28.0.1500.71 Safari/537.36'
    }

    def signup(self, username, referal):
        """ The signup process counts with the following steps: Register, Login, Verify Email, Set Address. """

        s = requests.session()
        t = TenMinuteEmailBoss()

        password = "123456"

        # Set referal code to session
        res = s.get('https://coinad.com/?r={}'.format(referal), verify=False, headers=self.HEADERS)
        assert res.status_code == 200

        # Go to register page
        res = s.get('https://coinad.com/?a=New_Account', verify=False, headers=self.HEADERS)
        captcha_code = self._get_captcha(s, res)

        email = t.temp_email_address
        print 'Using Email {}'.format(email)

        # Post Register Form
        data = self._data_register(username, email, password, captcha_code)
        res = s.post('https://coinad.com/?a=New_Account', data=data, verify=False, headers=self.HEADERS)
        self.dump_file(res, 'register_res.html')
        assert res.content.find('now need to use the code sent to') != -1

        # Get Login Form
        res = s.get('https://coinad.com/?a=Account', verify=False, headers=self.HEADERS)
        captcha_code = self._get_captcha(s, res)

        # Post Login Data
        data = self._data_login(username, password, captcha_code)
        res = s.post('https://coinad.com/?a=Account', data=data, verify=False, headers=self.HEADERS)
        self.dump_file(res, 'login_res.html')
        assert res.content.find('your email using the code sent to') != -1

        verification = t.get_confirmation_code()
        print 'Using Verification Code {}'.format(verification)

        # Post Verification Code
        data = {'code': verification}
        res = s.post('https://coinad.com/?a=Account', data=data, verify=False, headers=self.HEADERS)
        self.dump_file(res, 'verification_res.html')
        assert res.content.find('Complete account registration with your') != -1

        # TODO: Create Bitcoin Address
        address = raw_input('Bitcoin Address: ')

        # Post Bitcoin Address
        data = {'address': address}
        res = s.post('https://coinad.com/?a=Account', data=data, verify=False, headers=self.HEADERS)
        self.dump_file(res, 'address_res.html')
        assert res.content.find('Account Details') != -1

        soup = BeautifulSoup(res.content)
        referal_code = soup.findAll('td', {'style': "width:300px;"})[1].get_text()
        referal_code = re.match('.*?r=(.*)', referal_code).groups()[0]

        return username, password, referal_code, address, email

    def _get_captcha(self, s, res):
        soup = BeautifulSoup(res.content)
        captcha_path = soup.find('img', {'id': 'siimage'})['src']

        res = s.get('https://coinad.com/'+captcha_path, verify=False, headers=self.HEADERS)
        return CaptchaBoss().process_str(res.content)

    def _data_register(self, username, email, password, captcha):
        return {
            'username': username,
            'email': email,
            'password': password,
            'confirmation': password,
            'birth': "1978",
            'captcha-code': captcha,
        }

    def _data_login(self, username, password, captcha):
        return {
            'username': username,
            'password': password,
            'captcha-code': captcha,
        }

    def dump_file(self, res, name='tmp.html'):
        f = open(name, 'wb')
        f.write(res.content)
        f.close()
