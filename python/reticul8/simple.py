import time
import asyncio
import logging
import datetime


R8_SERIAL_MAX_PACKET = 254
R8_SERIAL_OVERHEAD   = 1+2+4
R8_SERIAL_BUF_SZ     = (R8_SERIAL_MAX_PACKET + R8_SERIAL_OVERHEAD)
R8_SERIAL_START      = 149
R8_SERIAL_END        = 234
R8_SERIAL_ESC        = 187

def crc32_compute(data):

    crc = 0xFFFFFFFF

    for b in data:

        if b < 0:
            b += 256

        crc ^= b
        for i in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                 crc =  crc >> 1
    return ~crc



def crc32_to_bytes(crc):

    d = []

    for x in range(4):
        i = 4-x

        c_x = (crc >> (8 * (i - 1))) & 0xFF
        if c_x < 0:
            c_x += 256

        d.append(c_x)
    return bytes(d)


def crc32_compare(computed, received):
    return crc32_to_bytes(computed) == received

    # for x in range(4):
    #     i = 4-x
    #
    #     c_x = (computed >> (8 * (i - 1))) & 0xFF
    #     if c_x < 0:
    #         c_x += 256
    #
    #     r_x = (received[3 - (i - 1)])
    #
    #     if c_x != r_x:
    #         return False
    #
    # return True




class Reticul8Packet(object):

    def __init__(self, incoming_packet_queue):
        self.incoming_packet_queue = incoming_packet_queue
        self.clear()

    def clear(self):
        self.buf = []
        self.esc = False
        self.packet_in_progress = False

    def data_recv(self, data):

        failures = sum(map(self.byte_recv,data))
        if failures:
            logging.warning(data)

    def byte_recv(self, b):

        if self.packet_in_progress:

            if self.esc:
                self.buf.append(b ^ R8_SERIAL_ESC)
                self.esc = False
                return 0
            elif b == R8_SERIAL_ESC:
                self.esc = True
                return 0
            elif b == R8_SERIAL_END:

                try:
                    self.check_packet()
                    self.clear()
                    return 0
                except:
                    logging.warning(bytes(self.buf))
                    self.clear()
                    return 1

            else:
                self.buf.append(b)
                return 0

        elif b == R8_SERIAL_START:
            self.clear()
            self.packet_in_progress = True
            return 0
        else:
            return 1



    def check_packet(self):

        assert self.buf[2] == (len(self.buf) - R8_SERIAL_OVERHEAD)

        pkt = bytes(self.buf[:-4])
        crc = bytes(self.buf[-4:])

        assert len(crc) == 4, len(crc)

        assert len(pkt) -3 == self.buf[2], 'pkt len {} != {}'.format(len(pkt), self.buf[2])

        crc_computed = crc32_compute(pkt)

        assert crc32_compare(crc_computed, crc) is True

        self.incoming_packet_queue.put_nowait((datetime.datetime.utcnow(), pkt))


class Reticul8Serial(asyncio.Protocol):

    def __init__(self, incoming_packet_queue):
        super().__init__()
        self._transport = None
        self.r8packet = Reticul8Packet(incoming_packet_queue)
        self.msg_id = 0

    def connection_made(self, transport):
        self._transport = transport

        # Reset device
        self._transport.serial.setDTR(True)
        self._transport.serial.setRTS(True)
        time.sleep(0.01)
        self._transport.serial.setDTR(False)
        self._transport.serial.setRTS(False)

    def data_received(self, data):
        self.r8packet.data_recv(data)

        # print(data)

        # s = data.decode('utf-8')
        # print(s)
        # for _ in s.split('\n'):
        #     print(_)

    def connection_lost(self, exc):
        self._transport.loop.stop()

    def pause_writing(self):
        print(self._transport.get_write_buffer_size())

    def resume_writing(self):
        print(self._transport.get_write_buffer_size())


    def send_packet(self, source, dest, packet):

        if packet.HasField('msg_id') is not True:
            msg_id = self.msg_id
            self.msg_id += 1
            packet.msg_id = msg_id
        pbytes = packet.SerializeToString()
        plen = len(pbytes)
        assert plen< R8_SERIAL_MAX_PACKET

        b = bytes([dest, source, plen]) + pbytes
        crc = crc32_compute(b)

        b += crc32_to_bytes(crc)

        outbuf = [R8_SERIAL_START]

        for _ in b:
            if _ == R8_SERIAL_ESC or _ == R8_SERIAL_START or _ == R8_SERIAL_END:
                outbuf.append(R8_SERIAL_ESC)
                outbuf.append(_ ^ R8_SERIAL_ESC)
            else:
                outbuf.append(_)
        outbuf.append(R8_SERIAL_END)

        self._transport.write(bytes(outbuf))
        return packet.msg_id




# class SimpleIO(pjon_cython.ThroughSerialAsync):
#     """Create a serial connection for """
#
#     def __init__(self, device_id, *args, **kwargs):
#         self.device_id = device_id
#         self.waiting_ack_packets = {}
#         self.received_ack_packets = {}
#
#         self.port = serial.serial_for_url(*args, **kwargs)
#         logging.info('Serial port opened {}'.format(self.port))
#
#         pjon_cython.ThroughSerialAsync.__init__(self, self.device_id, self.port.fd, int(self.port._baudrate))
#         self.set_asynchronous_acknowledge(False)
#         self.set_synchronous_acknowledge(False)
#         self.set_crc_32(True)
#         self.set_packet_id(True)
#         logging.error('Packet overhead {}'.format(self.packet_overhead()))
#
        # Tune this to your serial interface
        # A value of 0 seems to work well for USB serial interfaces,
        # where as the RPi hardware serial requires a minimum of 10
        # self.set_flush_offset(0)
        #
        # self.msg_id = 0
        # self.recv_q = asyncio.Queue()
        #
        # Reset device
        # self.port.setDTR(True)
        # self.port.setRTS(True)
        # time.sleep(0.01)
        # self.port.setDTR(False)
        # self.port.setRTS(False)
        #
        # asyncio.ensure_future(self.loop_task())
        # asyncio.ensure_future(self.process_task())
    #
    # def receive(self, data, length, packet_info):
    #     self.recv_q.put_nowait((data, packet_info['sender_id']))
    #
    # async def recv_task(self):
    #

    # async def loop_task(self):
    #
    #     while True:
    #         pts, status = self.loop()
    #         if pts >0:
    #             logging.info('PTS {} STATUS {}'.format(pts, status))
    #         await asyncio.sleep(LOOP_SLEEP)
    #
    # def send_packet(self, destination, packet):
    #
    #     packet.msg_id = self.msg_id
    #     self.msg_id += 1
    #
    #     self.waiting_ack_packets[packet.msg_id] = datetime.datetime.now()
    #     self.send(destination, packet.SerializeToString())
    #     logging.info('sent to {}'.format(destination))
    #

