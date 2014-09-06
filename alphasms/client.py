import requests
import xml.etree.ElementTree as ETree
import io
from collections import namedtuple

MESSAGE_TYPE_NORMAL = 0
MESSAGE_TYPE_FLASH = 1
MESSAGE_TYPE_WAP_PUSH = 2
MESSAGE_TYPE_VOICE = 3


class MessageRequest(namedtuple('MessageRequest', 'recipient sender text message_type user_sms_id wap_url')):
    def as_xml_element(self):
        element = ETree.Element('msg', {
            'recipient': self.recipient,
            'sender': self.sender,
            'type': str(self.message_type)
        })
        if int(self.message_type) == MESSAGE_TYPE_WAP_PUSH:
            if self.wap_url is None:
                raise ValueError('Valid WAP Push URL is required')
            element.set('url', self.wap_url)
        if self.user_sms_id is not None:
            element.set('id', str(self.user_sms_id))
        element.text = self.text
        return element


MessageResult = namedtuple('MessageResult', 'user_sms_id sms_count sms_id error')


class StatusRequest(namedtuple('StatusRequest', 'user_sms_id sms_id')):
    def as_xml_element(self):
        element = ETree.Element('msg')
        if self.user_sms_id:
            element.set('id', str(self.user_sms_id))
        elif self.sms_id:
            element.set('sms_id', str(self.sms_id))
        else:
            raise ValueError('Either user_sms_id or sms_id is required')
        return element


class StatusResult(namedtuple('StatusResult', 'user_sms_id sms_count sms_id date_completed status')):
    result_codes = {
        1: 'received',
        100: 'scheduled for delivery',
        101: 'enroute state',  # I'd want to know what this actually means
        102: 'delivered',
        103: 'expired',
        104: 'deleted',
        105: 'undeliverable',
        106: 'accepted',
        107: 'unknown',
        108: 'rejected',
        109: 'discarded',
        110: 'sending',
        111: 'receiver\'s operator is not supported',
        112: 'wrong alphaname (only for Life:) Ukraine)',
        113: 'wrong alphaname, money returned (only for Life:) Ukraine)'
    }

    def __repr__(self):
        return 'StatusResult(user_sms_id=%r, sms_count=%r, sms_id=%r, date_completed=%r, status=%r, status_string=%r)' \
               % (self.user_sms_id, self.sms_count, self.sms_id, self.date_completed, self.status, self.status_string())

    def status_string(self):
        return self.result_codes.get(int(self.status), 'Unknown error %s' % self.status)


class Client(object):
    __message_queue = None

    def __init__(self, login=None, password=None, api_key=None):
        if api_key or (login and password):
            self.login = login
            self.password = password
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
        xml_tree.write(stream, encoding='utf-8', xml_declaration=True)
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
        :type messages: list[MessageRequest]
        :return: List of sending results
        :rtype: list[SendingResult]
        :raise ValueError: For WAP Push-related errors
        """
        message_nodes = [message.as_xml_element() for message in messages]
        xml_tree = self.__create_request('message', message_nodes)
        reply = self.__run_request(xml_tree)
        reply_msg_nodes = reply.findall('message/msg')
        """:type: list[ETree.Element]"""
        return [MessageResult(
            user_sms_id=reply_msg_node.get('id'),
            sms_count=reply_msg_node.get('sms_count'),
            sms_id=reply_msg_node.get('sms_id'),
            error=reply_msg_node.text
        ) for reply_msg_node in reply_msg_nodes]

    def send_sms(self, recipient, sender, text, user_sms_id=None, message_type=MESSAGE_TYPE_NORMAL, wap_url=None):
        """
        Sends SMS

        :param recipient: Recipient phone number. May be in Ukrainian or international format
        :param sender: Sender name, e.g. your phone number or registered alphanumeric name
        :param text: Message text
        :param user_sms_id: User-defined message ID. MUST be unique if defined
        :param message_type: Message type.
                             May be one of MESSAGE_TYPE_NORMAL, MESSAGE_TYPE_FLASH, MESSAGE_MESSAGE_TYPE_WAP_PUSH or
                             MESSAGE_TYPE_VOICE.
                             Note that MESSAGE_TYPE_WAP_PUSH needs a proper wap_url.
                             Voice messages (type MESSAGE_TYPE_VOICE) can be only sent to domestic (non-mobile) numbers.
        :param wap_url: WAP Push URL
        :return: Message ID
        """
        reply = self.bulk_send_sms([MessageRequest(
            recipient=recipient,
            sender=sender,
            text=text,
            message_type=message_type,
            user_sms_id=user_sms_id,
            wap_url=wap_url
        )])
        our_reply = reply.pop()
        if our_reply is None:
            raise AlphaSmsException('No server reply')
        if int(our_reply.error) != 1:
            raise AlphaSmsServerError(our_reply.error)
        return our_reply

    def bulk_get_status(self, status_requests):
        """
        Get statuses for list of messages
        :param status_requests: list of messages
        :type status_requests: list[StatusRequest]
        :return:
        """
        status_nodes = [req.as_xml_element() for req in status_requests]
        xml_tree = self.__create_request('status', status_nodes)
        reply = self.__run_request(xml_tree)
        reply_msg_nodes = reply.findall('status/msg')
        """:type: list[ETree.Element]"""
        return [StatusResult(
            user_sms_id=reply_msg_node.get('id'),
            sms_count=reply_msg_node.get('sms_count'),
            sms_id=reply_msg_node.get('sms_id'),
            date_completed=reply_msg_node.get('date_completed'),
            status=reply_msg_node.text
        ) for reply_msg_node in reply_msg_nodes]

    def get_status(self, user_sms_id=None, sms_id=None):
        reply = self.bulk_get_status([StatusRequest(
            user_sms_id=user_sms_id,
            sms_id=sms_id
        )])
        our_reply = reply.pop()
        if our_reply is None:
            raise AlphaSmsException('No server reply')
        return our_reply

    def bulk_delete(self, delete_requests):
        """
        Delete list of messages
        :param delete_requests: list of messages
        :type delete_requests: list[StatusRequest]
        :return:
        """
        delete_nodes = [req.as_xml_element() for req in delete_requests]
        xml_tree = self.__create_request('delete', delete_nodes)
        reply = self.__run_request(xml_tree)
        reply_msg_nodes = reply.findall('status/msg')
        """:type: list[ETree.Element]"""
        return [StatusResult(
            user_sms_id=reply_msg_node.get('id'),
            sms_count=reply_msg_node.get('sms_count'),
            sms_id=reply_msg_node.get('sms_id'),
            date_completed=reply_msg_node.get('date_completed'),
            status=reply_msg_node.text
        ) for reply_msg_node in reply_msg_nodes]

    def delete(self, user_sms_id=None, sms_id=None):
        reply = self.bulk_delete([StatusRequest(
            user_sms_id=user_sms_id,
            sms_id=sms_id
        )])
        our_reply = reply.pop()
        if our_reply is None:
            raise AlphaSmsException('No server reply')
        return our_reply

    def message_queue(self):
        """
        Returns message queue for bulk sending. Use it like this:

        with client.message_queue() as q:
            q.add_message(...)

        :return: Message queue object
        :rtype: MessageQueue
        """
        if self.__message_queue is None:
            self.__message_queue = MessageQueue(self)
        return self.__message_queue


class AlphaSmsException(Exception):
    pass


class AlphaSmsServerError(Exception):
    error_codes = {
        200: 'Unknown error',
        201: 'Wrong document format',
        202: 'Authorization error',
        208: 'Duplicate id (user_sms_id)',
        209: 'Wrong API key or API disabled by user',
        210: 'Denied IP address'
    }

    def __str__(self):
        return '%s: %s' % (self.args[0], self.error_codes.get(int(self.args[0]), 'Unknown error'))


class MessageQueue(object):
    queue = []
    """:type: list[MessageRequest]"""
    sent_messages = []
    """:type list[MessageResult]"""

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
            self.sent_messages += self.client.bulk_send_sms(self.queue)
            self.queue = []

    def add_message(self, recipient, sender, text, user_sms_id=None, message_type=MESSAGE_TYPE_NORMAL, wap_url=None):
        self.queue.append(MessageRequest(
            recipient=recipient,
            sender=sender,
            text=text,
            message_type=message_type,
            user_sms_id=user_sms_id,
            wap_url=wap_url
        ))
        if len(self.queue) >= 50:
            self.flush()