try:
    import usocket as socket
except ImportError:
    import socket

try:
    import ustruct as struct
except ImportError:
    import struct


class MQTTException(Exception):
    pass


def _ensure_bytes(value):
    if isinstance(value, bytes):
        return value
    return str(value).encode()


class MQTTClient:
    def __init__(
        self,
        client_id,
        server,
        port=0,
        user=None,
        password=None,
        keepalive=0,
        ssl=False,
        ssl_params=None,
    ):
        if port == 0:
            port = 8883 if ssl else 1883

        self.client_id = _ensure_bytes(client_id)
        self.server = server
        self.port = port
        self.user = None if user is None else _ensure_bytes(user)
        self.pswd = None if password is None else _ensure_bytes(password)
        self.keepalive = keepalive
        self.ssl = ssl
        self.ssl_params = ssl_params or {}

        self.sock = None
        self.pid = 0
        self.cb = None
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, value):
        value = _ensure_bytes(value)
        self.sock.write(struct.pack("!H", len(value)))
        self.sock.write(value)

    def _recv_len(self):
        n = 0
        sh = 0
        while True:
            b = self.sock.read(1)
            if not b:
                raise OSError("MQTT socket fechado ao ler tamanho")
            res = b[0]
            n |= (res & 0x7F) << sh
            if not res & 0x80:
                return n
            sh += 7

    def set_callback(self, callback):
        self.cb = callback

    def set_last_will(self, topic, msg, retain=False, qos=0):
        self.lw_topic = _ensure_bytes(topic)
        self.lw_msg = _ensure_bytes(msg)
        self.lw_retain = retain
        self.lw_qos = qos

    def connect(self, clean_session=True):
        self.sock = socket.socket()
        try:
            self.sock.settimeout(10)
        except Exception:
            pass

        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(addr)

        if self.ssl:
            try:
                import ssl
            except ImportError:
                import ussl as ssl
            self.sock = ssl.wrap_socket(self.sock, **self.ssl_params)

        premsg = bytearray(b"\x10\0\0\0\0\0")
        msg = bytearray(b"\x04MQTT\x04\x02\0\0")

        size = 10 + 2 + len(self.client_id)
        msg[6] = int(clean_session) << 1

        if self.user is not None:
            size += 2 + len(self.user) + 2 + len(self.pswd)
            msg[6] |= 0xC0

        if self.keepalive:
            msg[7] |= self.keepalive >> 8
            msg[8] |= self.keepalive & 0x00FF

        if self.lw_topic:
            size += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
            msg[6] |= 0x04 | ((self.lw_qos & 0x01) << 3) | ((self.lw_qos & 0x02) << 3)
            msg[6] |= int(self.lw_retain) << 5

        i = 1
        while size > 0x7F:
            premsg[i] = (size & 0x7F) | 0x80
            size >>= 7
            i += 1
        premsg[i] = size

        self.sock.write(premsg, i + 1)
        self.sock.write(msg)
        self._send_str(self.client_id)

        if self.lw_topic:
            self._send_str(self.lw_topic)
            self._send_str(self.lw_msg)

        if self.user is not None:
            self._send_str(self.user)
            self._send_str(self.pswd)

        response = self.sock.read(4)
        if not response or len(response) < 4:
            raise MQTTException("Sem resposta CONNACK do broker")
        if response[0] != 0x20 or response[1] != 0x02:
            raise MQTTException("CONNACK invalido: {}".format(response))
        if response[3] != 0:
            raise MQTTException(response[3])

        try:
            self.sock.settimeout(None)
        except Exception:
            pass

        return response[2] & 1

    def disconnect(self):
        if self.sock is not None:
            self.sock.write(b"\xe0\0")
            self.sock.close()
            self.sock = None

    def ping(self):
        self.sock.write(b"\xc0\0")

    def publish(self, topic, msg, retain=False, qos=0):
        topic = _ensure_bytes(topic)
        msg = _ensure_bytes(msg)

        pkt = bytearray(b"\x30\0\0\0")
        pkt[0] |= qos << 1 | int(retain)

        size = 2 + len(topic) + len(msg)
        if qos > 0:
            size += 2

        if size >= 2097152:
            raise MQTTException("Payload muito grande")

        i = 1
        while size > 0x7F:
            pkt[i] = (size & 0x7F) | 0x80
            size >>= 7
            i += 1
        pkt[i] = size

        self.sock.write(pkt, i + 1)
        self._send_str(topic)

        if qos > 0:
            self.pid += 1
            struct.pack_into("!H", pkt, 0, self.pid)
            self.sock.write(pkt, 2)

        self.sock.write(msg)

        if qos == 1:
            while True:
                op = self.wait_msg()
                if op == 0x40:
                    size = self._recv_len()
                    if size != 2:
                        raise MQTTException("PUBACK invalido")
                    rcv_pid = struct.unpack("!H", self.sock.read(2))[0]
                    if rcv_pid == self.pid:
                        return

    def subscribe(self, topic, qos=0):
        if self.cb is None:
            raise MQTTException("Callback MQTT nao definido")

        topic = _ensure_bytes(topic)
        pkt = bytearray(b"\x82\0\0\0")
        self.pid += 1
        struct.pack_into("!H", pkt, 1, self.pid)

        size = 2 + 2 + len(topic) + 1
        i = 3
        while size > 0x7F:
            pkt[i] = (size & 0x7F) | 0x80
            size >>= 7
            i += 1
        pkt[i] = size

        self.sock.write(pkt, i + 1)
        self.sock.write(struct.pack("!H", self.pid))
        self._send_str(topic)
        self.sock.write(struct.pack("B", qos))

    def wait_msg(self):
        response = self.sock.read(1)
        try:
            self.sock.setblocking(True)
        except Exception:
            pass

        if response is None:
            return None
        if response == b"":
            raise OSError(-1)

        if response == b"\xd0":
            size = self._recv_len()
            if size != 0:
                raise MQTTException("PINGRESP invalido")
            return None

        op = response[0]
        if op & 0xF0 != 0x30:
            return op

        size = self._recv_len()
        topic_len = struct.unpack("!H", self.sock.read(2))[0]
        topic = self.sock.read(topic_len)
        size -= topic_len + 2

        if op & 0x06:
            pid = struct.unpack("!H", self.sock.read(2))[0]
            size -= 2
        else:
            pid = None

        msg = self.sock.read(size)
        self.cb(topic, msg)

        if op & 0x06 == 0x02:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        elif op & 0x06 == 0x04:
            raise MQTTException("QoS 2 nao suportado")

        return op

    def check_msg(self):
        try:
            self.sock.setblocking(False)
        except Exception:
            pass
        return self.wait_msg()
