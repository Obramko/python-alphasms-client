__author__ = 'abram'

import requests
import xml.etree.ElementTree as ETree
import io

AUTH_METHOD_API = 0
AUTH_METHOD_LOGIN_PASSWORD = 1

MESSAGE_TYPE_NORMAL = 0
MESSAGE_TYPE_FLASH = 1
MESSAGE_TYPE_WAP_PUSH = 2
MESSAGE_TYPE_VOICE = 3


class Client(object):
    def __init__(self, login=None, password=None, api_key=None):
        if login is not None and password is not None:
            self.auth_method = AUTH_METHOD_LOGIN_PASSWORD
            self.login = login
            self.password = password
        elif api_key is not None:
            self.auth_method = AUTH_METHOD_API
            self.api_key = api_key
        else:
            raise ValueError("AlphaSMS API client needs either API key or login/password pair")

    def __create_request(self, action, action_elements=None):
        """
        Constructs the XML request and returns it as a ready-to-send string
        :param action:
        :param action_elements:
        :rtype : str
        """
        stream = io.BytesIO()
        package_node = ETree.Element("package")
        if self.auth_method == AUTH_METHOD_API:
            package_node.set("key", self.api_key)
        elif self.auth_method == AUTH_METHOD_LOGIN_PASSWORD:
            package_node.set("login", self.login)
            package_node.set("password", self.password)
        action_node = ETree.SubElement(package_node, action)
        """:type : ETree.Element """
        if action_elements is not None:
            for element in action_elements:
                action_node.append(element)
        xml_tree = ETree.ElementTree(package_node)
        xml_tree.write(stream, encoding='utf-8', xml_declaration=True, short_empty_elements=False)
        return stream.getvalue()

    @staticmethod
    def __run_request(request_string):
        """
        Runs the actual request
        :return : Parsed XML tree of reply
        :rtype  : ETree.ElementTree
        :raises : AlphaSmsException if something gone wrong
        :raises : AlphaSmsServerError if server returned an error
        """
        r = requests.post("http://alphasms.com.ua/api/xml.php", data=request_string)
        if r.status_code != 200:
            raise AlphaSmsException("HTTP Error")
        try:
            xml_tree = ETree.fromstring(r.text)
            error_node = xml_tree.find('error')
            if error_node is not None:
                raise AlphaSmsServerError(error_node.text)
            else:
                return xml_tree
        except ETree.ParseError:
            raise AlphaSmsException("Error parsing XML reply")

    def check_balance(self):
        """
        :return : Balance
        :rtype  : float
        :raise AlphaSmsException:
        """
        xml_tree = self.__run_request(self.__create_request('balance'))
        amount_node = xml_tree.find('balance/amount')
        if amount_node is None:
            raise AlphaSmsException("Could not find balance XML node")
        return float(amount_node.text)

    def send_sms(self, recipient, sender, text, id=None, message_type=MESSAGE_TYPE_NORMAL, wap_url=None):
        """
        Sends SMS

        :param recipient: Recipient phone number. May be in Ukrainian or international format
        :param sender: Sender name, e.g. your phone number or registered alphanumeric name
        :param text: Message text
        :param id: User-defined message ID. MUST be unique if defined
        :param message_type: Message type.
                             May be one of MESSAGE_TYPE_NORMAL, MESSAGE_TYPE_FLASH, MESSAGE_MESSAGE_TYPE_WAP_PUSH or
                             MESSAGE_TYPE_VOICE.
                             Note that MESSAGE_TYPE_WAP_PUSH needs a proper wap_url.
                             Voice messages (type MESSAGE_TYPE_VOICE) can be only sent to domestic (non-mobile) numbers.
        :param wap_url: WAP Push URL
        :return: Message ID
        """
        message_node = ETree.Element('msg', {
            'recipient': recipient,
            'sender': sender,
            'type': str(message_type)
        })
        if message_type == MESSAGE_TYPE_WAP_PUSH:
            if wap_url is None:
                raise ValueError('Valid WAP Push URL is required')
            message_node.set('url', wap_url)
        if id is not None:
            message_node.set('id', id)
        message_node.text = text
        xml_tree = self.__create_request('message', [message_node])

        reply = self.__run_request(xml_tree)
        reply_msg_node = reply.find('message/msg')
        """:type : ETree.Element"""
        if reply_msg_node is None:
            raise AlphaSmsException('Could not find msg node')
        if int(reply_msg_node.text) == 1:
            return {
                'id': reply_msg_node.get('id'),
                'sms_count': reply_msg_node.get('sms_count'),
                'sms_id': reply_msg_node.get('sms_id')
            }
        else:
            raise AlphaSmsServerError(reply_msg_node.text)


class AlphaSmsException(Exception):
    pass


class AlphaSmsServerError(Exception):
    pass