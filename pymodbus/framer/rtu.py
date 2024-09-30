"""Modbus RTU frame implementation."""
from __future__ import annotations

from pymodbus.framer.base import FramerBase
from pymodbus.logging import Log


class FramerRTU(FramerBase):
    """Modbus RTU frame type.

    [ Start Wait ] [Address ][ Function Code] [ Data ][ CRC ]
      3.5 chars     1b         1b               Nb      2b

    * Note: due to the USB converter and the OS drivers, timing cannot be quaranteed
    neither when receiving nor when sending.

    Decoding is a complicated process because the RTU frame does not have a fixed prefix
    only suffix, therefore it is necessary to decode the content (PDU) to get length etc.

    There are some protocol restrictions that help with the detection.

    For client:
       - a request causes 1 response !
       - Multiple requests are NOT allowed (master-slave protocol)
       - the server will not retransmit responses
    this means decoding is always exactly 1 frame (response)

    For server (Single device)
       - only 1 request allowed (master-slave) protocol
       - the client (master) may retransmit but in larger time intervals
    this means decoding is always exactly 1 frame (request)

    For server (Multidrop line --> devices in parallel)
       - only 1 request allowed (master-slave) protocol
       - other devices will send responses
       - the client (master) may retransmit but in larger time intervals
    this means decoding is always exactly 1 frame request, however some requests
    will be for unknown slaves, which must be ignored together with the
    response from the unknown slave.
    >>>>> NOT IMPLEMENTED <<<<<

    Recovery from bad cabling and unstable USB etc is important,
    the following scenarios is possible:
       - garble data before frame
       - garble data in frame
       - garble data after frame
       - data in frame garbled (wrong CRC)
    decoding assumes the frame is sound, and if not enters a hunting mode.

    The 3.5 byte transmission time at the slowest speed 1.200Bps is 31ms.
    Device drivers will typically flush buffer after 10ms of silence.
    If no data is received for 50ms the transmission / frame can be considered
    complete.
    >>>>> NOT IMPLEMENTED <<<<<
    """

    MIN_SIZE = 5

    @classmethod
    def generate_crc16_table(cls) -> list[int]:
        """Generate a crc16 lookup table.

        .. note:: This will only be generated once
        """
        result = []
        for byte in range(256):
            crc = 0x0000
            for _ in range(8):
                if (byte ^ crc) & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
                byte >>= 1
            result.append(crc)
        return result
    crc16_table: list[int] = [0]



    def decode(self, data: bytes) -> tuple[int, int, int, bytes]:
        """Decode ADU."""
        if len(data) < self.MIN_SIZE:
            Log.debug("Short frame: {} wait for more data", data, ":hex")
            return 0, 0, 0, b''

        return 0, 0, 0, b''


    def encode(self, pdu: bytes, device_id: int, _tid: int) -> bytes:
        """Encode ADU."""
        packet = device_id.to_bytes(1,'big') + pdu
        return packet + FramerRTU.compute_CRC(packet).to_bytes(2,'big')

    @classmethod
    def check_CRC(cls, data: bytes, check: int) -> bool:
        """Check if the data matches the passed in CRC.

        :param data: The data to create a crc16 of
        :param check: The CRC to validate
        :returns: True if matched, False otherwise
        """
        return cls.compute_CRC(data) == check

    @classmethod
    def compute_CRC(cls, data: bytes) -> int:
        """Compute a crc16 on the passed in bytes.

        The difference between modbus's crc16 and a normal crc16
        is that modbus starts the crc value out at 0xffff.

        :param data: The data to create a crc16 of
        :returns: The calculated CRC
        """
        crc = 0xFFFF
        for data_byte in data:
            idx = cls.crc16_table[(crc ^ int(data_byte)) & 0xFF]
            crc = ((crc >> 8) & 0xFF) ^ idx
        swapped = ((crc << 8) & 0xFF00) | ((crc >> 8) & 0x00FF)
        return swapped

FramerRTU.crc16_table = FramerRTU.generate_crc16_table()
