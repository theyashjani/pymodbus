"""Framer implementations.

The implementation is responsible for encoding/decoding requests/responses.

According to the selected type of modbus frame a prefix/suffix is added/removed
"""
from __future__ import annotations

from abc import abstractmethod

from pymodbus.exceptions import ModbusIOException
from pymodbus.factory import ClientDecoder, ServerDecoder
from pymodbus.logging import Log
from pymodbus.pdu import ModbusRequest, ModbusResponse


class FramerBase:
    """Intern base."""

    EMPTY = b''
    MIN_SIZE = 0

    def __init__(
        self,
        decoder: ClientDecoder | ServerDecoder,
        dev_ids: list[int],
    ) -> None:
        """Initialize a ADU (framer) instance."""
        self.decoder = decoder
        self.dev_ids = dev_ids
        self.incoming_dev_id = 0
        self.incoming_tid = 0
        self.databuffer = b""

    def decode(self, data: bytes) -> tuple[int, bytes]:
        """Decode ADU.

        returns:
            used_len (int) or 0 to read more
            modbus request/response (bytes)
        """
        if (data_len := len(data)) < self.MIN_SIZE:
          Log.debug("Very short frame (NO MBAP): {} wait for more data", data, ":hex")
          return 0, self.EMPTY
        used_len, res_data = self.specific_decode(data, data_len)
        if not res_data:
            self.incoming_dev_id = 0
            self.incoming_tid = 0
        return used_len, res_data

    @abstractmethod
    def specific_decode(self, data: bytes, data_len: int) -> tuple[int, bytes]:
        """Decode ADU.

        returns:
            used_len (int) or 0 to read more
            modbus request/response (bytes)
        """


    @abstractmethod
    def encode(self, pdu: bytes, dev_id: int, tid: int) -> bytes:
        """Encode ADU.

        returns:
            modbus ADU (bytes)
        """

    def buildPacket(self, message: ModbusRequest | ModbusResponse) -> bytes:
        """Create a ready to send modbus packet.

        :param message: The populated request/response to send
        """
        data = message.function_code.to_bytes(1,'big') + message.encode()
        packet = self.encode(data, message.slave_id, message.transaction_id)
        return packet

    def processIncomingPacket(self, data: bytes, callback, slave, tid=None):
        """Process new packet pattern.

        This takes in a new request packet, adds it to the current
        packet stream, and performs framing on it. That is, checks
        for complete messages, and once found, will process all that
        exist.  This handles the case when we read N + 1 or 1 // N
        messages at a time instead of 1.

        The processed and decoded messages are pushed to the callback
        function to process and send.
        """
        Log.debug("Processing: {}", data, ":hex")
        self.databuffer += data
        if self.databuffer == b'':
            return
        if not isinstance(slave, (list, tuple)):
            slave = [slave]
        while True:
            if self.databuffer == b'':
                return
            used_len, data = self.decode(self.databuffer)
            if used_len:
                self.databuffer = self.databuffer[used_len:]
            if not data:
                return
            if slave and 0 not in slave and self.incoming_dev_id not in slave:
                Log.debug("Not a valid slave id - {}, ignoring!!", self.incoming_dev_id)
                self.databuffer = b''
                continue
            if (result := self.decoder.decode(data)) is None:
                self.databuffer = b''
                raise ModbusIOException("Unable to decode request")
            result.slave_id = self.incoming_dev_id
            result.transaction_id = self.incoming_tid
            Log.debug("Frame advanced, resetting header!!")
            self.databuffer = self.databuffer[used_len:]
            if tid and result.transaction_id and tid != result.transaction_id:
                self.databuffer = b''
            else:
                callback(result)  # defer or push to a thread?
