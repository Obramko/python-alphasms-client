python-alphasms-client
======================

Client API implementation for [AlphaSMS](http://alphasms.ua/) Ukrainian SMS service provider. [XML API v1.5](http://alphasms.ua/storage/files/AlphaSMS_XML_v1.5.pdf) was used.

Installing is as simple as:

    pip install alphasms-client

Usage example:

```python
import alphasms

a = alphasms.Client(api_key="some_key")  # login and password are fine, too
print('Your balance: %s' % a.check_balance())
sms_result = a.send_sms('0681234567', 'MyCompany', 'API TEST')
print(a.get_status(sms_id=sms_result.sms_id))
```

Messages may be queued for delivery (this will make things faster):

```python
with a.message_queue() as q:
    q.add_message('0681234567', 'UAinet', 'Queued messaging TEST')
    q.add_message('0667654321', 'UAinet', 'Queued messaging TEST 2')
```

