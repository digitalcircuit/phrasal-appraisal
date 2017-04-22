import logging
log = logging.getLogger(__name__)

# Python 3.4 and above; remove if needed
from enum import Enum

def parse_messages(operation_msgs):
    messages = []
    for msg in operation_msgs:
        messages.append(msg.convert_to_dict())
    return messages

class MessageType(Enum):
    Primary = 0
    Success = 1
    Info = 2
    Warn = 3
    Danger = 4

# Handle messages
class OpMessage(object):
    def __init__(self, msg_type, message, title = '', details = ''):
        if not msg_type in MessageType:
            raise TypeError("msg_type must be from MessageType")
        self.op_msg_type = msg_type
        self.op_title = title
        self.op_message = message
        if isinstance(details, list):
            self.op_details = details
        else:
            # Encapulsate the value in a list
            self.op_details = [ details ]
        log.debug(
            "OpMessage: Created new message: {0}"
            .format(self)
        )

    @property
    def msg_type(self):
        return self.op_msg_type

    @property
    def title(self):
        return self.op_title

    @property
    def message(self):
        return self.op_message

    @property
    def details(self):
        return self.op_details

    def convert_to_dict(self):
        # Create a dictionary representation of this message
        if self.op_msg_type is MessageType.Primary:
            msg_class = 'primary'
        elif self.op_msg_type is MessageType.Success:
            msg_class = 'success'
        elif self.op_msg_type is MessageType.Info:
            msg_class = 'info'
        elif self.op_msg_type is MessageType.Warn:
            msg_class = 'warning'
        elif self.op_msg_type is MessageType.Danger:
            msg_class = 'danger'
        else:
            msg_class = 'unknown'
        return {
            'msg_class': msg_class,
            'title': self.op_title,
            'message': self.op_message,
            'details': self.op_details
        }
