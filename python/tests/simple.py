import uvloop
import datetime
import asyncio
import serial
import serial_asyncio
import logging
import math
import os
from collections import deque, Counter

from reticul8 import simple, rpc
from reticul8.arduino import *

class Reticul8(object):

    def __init__(self, port, baudrate=115200):
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        self.loop = asyncio.get_event_loop()
        self.baudrate = baudrate
        self.port = port
        self.serial_transport = None
        self.incoming_packet_queue = asyncio.Queue()
        self.received_packet_queue = asyncio.Queue()
        self.outgoing_packet_queue = asyncio.Queue()
        self.loop.set_debug(True)
        self.loop.slow_callback_duration = 0.01

        self.packet_log = {}
        self.packet_data = {}
        self.packet_rtt = deque([10000],maxlen=10)
        self.timeout_bytes = Counter()


    def run(self):
        try:
            self.loop.run_until_complete(self.start_loops())
            self.loop.run_forever()
        finally:
            for b,c in self.timeout_bytes.items():
                print('{}\t{}'.format(b,c))
            self.loop.close()

    async def start_loops(self):

        ser = serial.Serial(port=self.port, baudrate=self.baudrate)
        self.r8serial = protocol = simple.Reticul8Serial(self.incoming_packet_queue)
        serial_asyncio.SerialTransport(self.loop, protocol, ser)
        asyncio.create_task(self.pkt_decode_loop())
        asyncio.create_task(self.process_loop())
        asyncio.create_task(self.packet_send_loop())
        asyncio.create_task(self.packet_check_timeout_loop())


    async def pkt_decode_loop(self):

        while True:
            ts, pkt = await self.incoming_packet_queue.get()

            dest = pkt[0]
            source = pkt[1]
            pkt = bytes(pkt[3:])

            packet = r8.FROM_MICRO()

            try:
                packet.ParseFromString(pkt)
                assert packet.IsInitialized()
            except (DecodeError, AssertionError):
                packet = None

            # logging.warning('{} Packet received from {} to {}\n{}'.format(ts, source, dest, packet))

            msg_id = int(packet.result.msg_id)

            try:
                self.packet_data.pop(msg_id)
            except KeyError:
                pass

            try:
                sent = self.packet_log.pop(msg_id)
                rtt = (datetime.datetime.utcnow()  - sent).microseconds

                self.packet_rtt.append(rtt)

                logging.warning('{} - RTT:{:<5,} ms (max {:<5,} ms) waiting: {}'.format(
                    source,
                    self.rtt_mean()/1000,
                    self.rtt_stdev()/1000,
                    str(packet).replace('\n',' ')
                ))
            except KeyError:
                logging.warning('Received duplicate packet {}'.format(msg_id))

            self.received_packet_queue.put_nowait({
                'ts':ts,
                'source':source,
                'dest':dest,
                'packet':packet
            })


    def rtt_mean(self):
        return int(sum(self.packet_rtt)/(1.0*len(self.packet_rtt)))

    def rtt_stdev(self):
        mean = self.rtt_mean()
        return int(math.sqrt(sum(map(lambda _:pow((_ -  mean),2), self.packet_rtt))/(1.0 * len(self.packet_rtt))))

    def rtt_max(self):
        return int(max(self.packet_rtt)/(1000.0))

    def timedout(self):
        return self.rtt_mean() *2#+ 2*self.rtt_stdev()

    async def process_loop(self):

        while True:
            packet = await self.received_packet_queue.get()
            pkt = rpc.RPC_Wrapper().ping()
            self.outgoing_packet_queue.put_nowait((0,10,pkt))

    async def packet_send_loop(self):

        while True:

            source, dest, packet = await self.outgoing_packet_queue.get()

            # while len(self.packet_log):
            #     await asyncio.sleep(self.timedout())
            msg_id = self.r8serial.send_packet(source, dest, packet)
            packet.msg_id = msg_id
            self.packet_log[msg_id] = datetime.datetime.utcnow()
            self.packet_data[msg_id] = (source, dest, packet)


    async def packet_check_timeout_loop(self):

        while True:

            timeout = self.timedout()

            for msg_id, ts in self.packet_log.copy().items():

                if (datetime.datetime.utcnow()  - ts).microseconds > timeout:
                    logging.error('{} has timed out, resending'.format(msg_id))
                    self.packet_log.pop(msg_id)
                    source,dest, pkt = self.packet_data.pop(msg_id)
                    for b in bytes(pkt.SerializeToString()):
                        self.timeout_bytes[int(b)]+=1
                    pkt.ClearField('msg_id')

                    self.outgoing_packet_queue.put_nowait((source,dest,pkt))
                    break

            await asyncio.sleep(timeout/1000000.0)






UART_PORT = [
    # '/dev/ttyUSB0',
    # '/dev/ttyAMA0',
    '/dev/tty.wchusbserial1410',
    '/dev/tty.usbserial-FTVY43AL',
    '/dev/tty.wchusbserial14120',
    '/dev/tty.SLAB_USBtoUART'
]

for port in UART_PORT:
    if os.path.exists(port):
        r = Reticul8(port=port, baudrate=115200)
        r.run()
        break







