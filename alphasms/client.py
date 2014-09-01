__author__ = 'abram'

import requests
import xml.etree.ElementTree as ETree
import io

AUTH_METHOD_API = 0
AUTH_METHOD_LOGIN_PASSWORD = 1


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
            Constructs the XML request and returns it as a string
            @rtype : str
            @param action: action to perform
            @param action_elements: list of ETree.Elements with corresponding actions 
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


    def __run_request(self, request_string):
        r = requests.post("http://alphasms.com.ua/api/xml.php", data=request_string)
        if r.status_code != 200:
            raise AlphaSmsException("HTTP Error")
        return r.text

    def check_balance(self):
        xml_string = self.__run_request(self.__create_request('balance'))
        xml_tree = ETree.fromstring(xml_string)
        """:type : ETree.ElementTree """
        amount_node = xml_tree.find('balance/amount')
        if amount_node is None:
            raise AlphaSmsException("Something weird happened")
        else:
            return amount_node.text


class AlphaSmsException(Exception):
    pass