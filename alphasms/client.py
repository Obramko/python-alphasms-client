import requests
import xml.etree.ElementTree as ETree
import io
from collections import namedtuple

MESSAGE_TYPE_NORMAL = 0
MESSAGE_TYPE_FLASH = 1
MESSAGE_TYPE_WAP_PUSH = 2
MESSAGE_TYPE_VOICE = 3

OutgoingMessage = namedtuple('OutgoingMessage', 'recipient sender text message_type message_id wap_url')


class Client(object):
    def __init__(self, login=None, password=None, api_key=None):
        if api_key or (login and password):
            self.login = login
            self.password = password
            self.api_key = api_key
        else:
            raise ValueError("AlphaSMS API client needs either API key or login/password pair")
        self.__message_queue = MessageQueue(self)

    def __create_request(self, action, action_elements=None):
        """
        Constructs the XML request and returns it as a ready-to-send string
        :param action:
        :param action_elements:
        :rtype : str
        """
        stream = io.BytesIO()
        package_node = ETree.Element("package")
        if self.api_key:
            package_node.set("key", self.api_key)
        elif self.login and self.password:
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

    def bulk_send_sms(self, messages):
        """
        Internal function used to
        :param messages: list of messages to send
        :type messages: list[OutgoingMessage]
        :return: Dict
                {
                    'id': message id (supplied by user),
                    'sms_count': count of messages sent (for multipart messages),
                    'sms_id': message id (supplied by service)
                    'error': error code (1 for success)
                }
        :raise ValueError: For WAP Push-related errors
        """
        message_nodes = []
        for message in messages:
            our_new_message_node = ETree.Element('msg', {
                'recipient': message.recipient,
                'sender': message.sender,
                'type': str(message.message_type)
            })
            if int(message.message_type) == MESSAGE_TYPE_WAP_PUSH:
                if message.wap_url is None:
                    raise ValueError('Valid WAP Push URL is required')
                our_new_message_node.set('url', message.wap_url)
            if message.message_id is not None:
                our_new_message_node.set('id', message.message_id)
            our_new_message_node.text = message.text
            message_nodes.append(our_new_message_node)
        xml_tree = self.__create_request('message', message_nodes)
        reply = self.__run_request(xml_tree)
        reply_msg_nodes = reply.findall('message/msg')
        return [{
            'id': reply_msg_node.get('id'),
            'sms_count': reply_msg_node.get('sms_count'),
            'sms_id': reply_msg_node.get('sms_id'),
            'error': reply_msg_node.text
        } for reply_msg_node in reply_msg_nodes]

    def send_sms(self, recipient, sender, text, message_id=None, message_type=MESSAGE_TYPE_NORMAL, wap_url=None):
        """
        Sends SMS

        :param recipient: Recipient phone number. May be in Ukrainian or international format
        :param sender: Sender name, e.g. your phone number or registered alphanumeric name
        :param text: Message text
        :param message_id: User-defined message ID. MUST be unique if defined
        :param message_type: Message type.
                             May be one of MESSAGE_TYPE_NORMAL, MESSAGE_TYPE_FLASH, MESSAGE_MESSAGE_TYPE_WAP_PUSH or
                             MESSAGE_TYPE_VOICE.
                             Note that MESSAGE_TYPE_WAP_PUSH needs a proper wap_url.
                             Voice messages (type MESSAGE_TYPE_VOICE) can be only sent to domestic (non-mobile) numbers.
        :param wap_url: WAP Push URL
        :return: Message ID
        """
        reply = self.bulk_send_sms([OutgoingMessage(
            recipient=recipient,
            sender=sender,
            text=text,
            message_type=message_type,
            message_id=message_id,
            wap_url=wap_url
        )])
        our_reply = reply.pop()
        if our_reply is None:
            raise AlphaSmsException('No server reply')
        if int(our_reply['error']) != 1:
            raise AlphaSmsServerError(our_reply['error'])
        return our_reply

    def message_queue(self):
        """
        Returns message queue for bulk sending. Use it like this:

        with client.message_queue() as q:
            q.add_message(...)

        :return: Message queue object
        :rtype: MessageQueue
        """
        return self.__message_queue


class AlphaSmsException(Exception):
    pass


class AlphaSmsServerError(Exception):
    pass


class MessageQueue(object):
    queue = []
    """:type: list[OutgoingMessage]"""

    def __init__(self, client):
        """
        :param client: Client
        :type client: Client
        """
        self.client = client

    def __enter__(self):
        self.flush()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()
        return self

    def flush(self):
        if len(self.queue) > 0:
            self.client.bulk_send_sms(self.queue)
            self.queue.clear()

    def add_message(self, recipient, sender, text, message_id=None, message_type=MESSAGE_TYPE_NORMAL, wap_url=None):
        self.queue.append(OutgoingMessage(
            recipient=recipient,
            sender=sender,
            text=text,
            message_type=message_type,
            message_id=message_id,
            wap_url=wap_url
        ))
        if len(self.queue) >= 50:
            self.flush()