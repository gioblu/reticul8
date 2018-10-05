import itertools
from . import reticul8_pb2 as r8


has_field = lambda o, f: f in o.DESCRIPTOR.fields_by_name
len_fields = lambda o: len(o.DESCRIPTOR.fields)
get_first_field = lambda o: o.DESCRIPTOR.fields[0]

class RPC_Caller(object):

    def __init__(self, name):
        self.name = name

    def __call__(self, *args, **kwargs):

        rpc = r8.RPC()
        call = rpc.__getattribute__(self.name)

        if has_field(call, self.name) and \
                not kwargs and \
                len_fields(call) == 1 \
                and get_first_field(call).type == get_first_field(call).TYPE_BOOL:

            # if there is only one field that is a bool with the same name as the rpc call, enabled it automatically

            call.__setattr__(self.name, True)
        else:

            for k,v in kwargs.items():
                call.__setattr__(k,v)

        return rpc


class RPC_Wrapper(object):

    def __getattribute__(self, item):

        if not has_field(r8.RPC, item):
            raise Exception(item)

        return RPC_Caller(item)


from contextlib import ContextDecorator
import contextvars

rpc = RPC_Wrapper()

node = contextvars.ContextVar('node')

class Node(ContextDecorator):

    def __init__(self, remote_device_id, transport):
        self.device_id = remote_device_id
        self.transport = transport
        self.startup = None
        transport.add_node(self)
        self.futures = []

    def __enter__(self):
        self.token = node.set(self)
        return self

    def __exit__(self, *exc):
        node.reset(self.token)
        return False

    def notify_startup(self):
        raise NotImplementedError()

    async def send_packet(self, packet):
        return await self.transport.send_packet_blocking(self.device_id, packet)
