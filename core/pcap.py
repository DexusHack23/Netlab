"""Escritor de capturas .pcap en Python puro (sin scapy).

Arma tramas Ethernet con IPv4/TCP/UDP/ICMP/ARP y cargas DNS, DHCP, HTTP y FTP, con
checksums correctos para que Wireshark no marque errores donde no los hay.
"""
from __future__ import annotations

import ipaddress
import random
import struct

# ---------------------------------------------------------------- utilidades


def mac(s: str) -> bytes:
    return bytes(int(x, 16) for x in s.split(":"))


def ip(s: str) -> bytes:
    return ipaddress.IPv4Address(s).packed


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    s = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def mac_azar(rnd: random.Random, oui: str = "00:1a:2b") -> str:
    return oui + ":" + ":".join(f"{rnd.randint(0, 255):02x}" for _ in range(3))


# ---------------------------------------------------------------- capas


def ethernet(src: str, dst: str, tipo: int, payload: bytes) -> bytes:
    trama = mac(dst) + mac(src) + struct.pack("!H", tipo) + payload
    return trama + b"\0" * max(0, 60 - len(trama))  # relleno mínimo de Ethernet


def ipv4(src: str, dst: str, proto: int, payload: bytes, ttl: int = 64, ident: int = 0, df: bool = True) -> bytes:
    flags = 0x4000 if df else 0
    cab = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), ident & 0xFFFF, flags, ttl, proto, 0,
                      ip(src), ip(dst))
    cab = cab[:10] + struct.pack("!H", _checksum(cab)) + cab[12:]
    return cab + payload


def _pseudo(src: str, dst: str, proto: int, largo: int) -> bytes:
    return ip(src) + ip(dst) + struct.pack("!BBH", 0, proto, largo)


FIN, SYN, RST, PSH, ACK = 0x01, 0x02, 0x04, 0x08, 0x10


def tcp(src: str, dst: str, sport: int, dport: int, seq: int, ack: int, flags: int, payload: bytes = b"",
        ventana: int = 64240, mss: bool = False) -> bytes:
    opciones = struct.pack("!BBH", 2, 4, 1460) if mss else b""
    off = (20 + len(opciones)) // 4
    cab = struct.pack("!HHIIBBHHH", sport, dport, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF, off << 4, flags,
                      ventana, 0, 0) + opciones
    seg = cab + payload
    cs = _checksum(_pseudo(src, dst, 6, len(seg)) + seg)
    return seg[:16] + struct.pack("!H", cs) + seg[18:]


def udp(src: str, dst: str, sport: int, dport: int, payload: bytes) -> bytes:
    seg = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0) + payload
    cs = _checksum(_pseudo(src, dst, 17, len(seg)) + seg) or 0xFFFF
    return seg[:6] + struct.pack("!H", cs) + seg[8:]


def icmp_eco(tipo: int, ident: int, seq: int, datos: bytes = b"abcdefghijklmnopqrstuvwabcdefghi") -> bytes:
    msg = struct.pack("!BBHHH", tipo, 0, 0, ident, seq) + datos
    return msg[:2] + struct.pack("!H", _checksum(msg)) + msg[4:]


def arp(op: int, sha: str, spa: str, tha: str, tpa: str) -> bytes:
    return struct.pack("!HHBBH6s4s6s4s", 1, 0x0800, 6, 4, op, mac(sha), ip(spa), mac(tha), ip(tpa))


# ---------------------------------------------------------------- DNS


def _qname(nombre: str) -> bytes:
    return b"".join(bytes([len(p)]) + p.encode() for p in nombre.strip(".").split(".")) + b"\0"


def dns_consulta(ident: int, nombre: str, qtype: int = 1) -> bytes:
    return struct.pack("!HHHHHH", ident, 0x0100, 1, 0, 0, 0) + _qname(nombre) + struct.pack("!HH", qtype, 1)


def dns_respuesta(ident: int, nombre: str, ips: list[str], rcode: int = 0, ttl: int = 300) -> bytes:
    flags = 0x8180 | (rcode & 0xF)
    cuerpo = _qname(nombre) + struct.pack("!HH", 1, 1)
    for a in ips:
        cuerpo += struct.pack("!HHHIH", 0xC00C, 1, 1, ttl, 4) + ip(a)
    return struct.pack("!HHHHHH", ident, flags, 1, len(ips), 0, 0) + cuerpo


# ---------------------------------------------------------------- DHCP


def dhcp(op: int, xid: int, chaddr: str, tipo: int, ciaddr: str = "0.0.0.0", yiaddr: str = "0.0.0.0",
         siaddr: str = "0.0.0.0", opciones: dict[int, bytes] | None = None) -> bytes:
    cab = struct.pack("!BBBBIHH4s4s4s4s16s64s128s", op, 1, 6, 0, xid, 0, 0x8000, ip(ciaddr), ip(yiaddr),
                      ip(siaddr), ip("0.0.0.0"), mac(chaddr) + b"\0" * 10, b"\0" * 64, b"\0" * 128)
    opts = b"\x63\x82\x53\x63" + bytes([53, 1, tipo])
    for k, v in (opciones or {}).items():
        opts += bytes([k, len(v)]) + v
    return cab + opts + b"\xff"


# ---------------------------------------------------------------- archivo


class Captura:
    """Junta paquetes con su tiempo y los escribe como .pcap (Ethernet)."""

    def __init__(self, inicio: float = 1_794_000_000.0):
        self.t = inicio
        self.paquetes: list[tuple[float, bytes]] = []

    def avanza(self, seg: float):
        self.t += seg

    def agrega(self, trama: bytes, dt: float = 0.0):
        self.t += dt
        self.paquetes.append((self.t, trama))
        return len(self.paquetes)  # número de frame (1-based), como en Wireshark

    def bytes(self) -> bytes:
        out = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        for t, d in self.paquetes:
            seg = int(t)
            us = int(round((t - seg) * 1_000_000))
            out += struct.pack("<IIII", seg, us, len(d), len(d)) + d
        return out


class SesionTCP:
    """Conversación TCP con números de secuencia coherentes en ambos sentidos."""

    def __init__(self, cap: Captura, cli: tuple[str, str, int], srv: tuple[str, str, int], rnd: random.Random,
                 rtt: float = 0.02):
        self.cap, self.rtt = cap, rtt
        (self.cmac, self.cip, self.cport), (self.smac, self.sip, self.sport) = cli, srv
        self.cseq, self.sseq = rnd.randint(1, 2**31), rnd.randint(1, 2**31)
        self.ident = rnd.randint(1, 60000)

    def _env(self, desde_cliente: bool, flags: int, datos: bytes = b"", dt: float = 0.0, mss=False, seq=None):
        self.ident += 1
        if desde_cliente:
            s = self.cseq if seq is None else seq
            seg = tcp(self.cip, self.sip, self.cport, self.sport, s, self.sseq if flags & ACK else 0, flags, datos,
                      mss=mss)
            trama = ethernet(self.cmac, self.smac, 0x0800, ipv4(self.cip, self.sip, 6, seg, ident=self.ident))
        else:
            s = self.sseq if seq is None else seq
            seg = tcp(self.sip, self.cip, self.sport, self.cport, s, self.cseq if flags & ACK else 0, flags, datos,
                      mss=mss)
            trama = ethernet(self.smac, self.cmac, 0x0800, ipv4(self.sip, self.cip, 6, seg, ident=self.ident))
        return self.cap.agrega(trama, dt)

    def handshake(self) -> list[int]:
        f1 = self._env(True, SYN, mss=True, dt=0.001)
        self.cseq += 1
        f2 = self._env(False, SYN | ACK, mss=True, dt=self.rtt / 2)
        self.sseq += 1
        f3 = self._env(True, ACK, dt=self.rtt / 2)
        return [f1, f2, f3]

    def datos(self, desde_cliente: bool, payload: bytes, dt: float = 0.01) -> int:
        f = self._env(desde_cliente, PSH | ACK, payload, dt=dt)
        if desde_cliente:
            self.cseq += len(payload)
        else:
            self.sseq += len(payload)
        return f

    def retransmite(self, desde_cliente: bool, payload: bytes, dt: float = 0.3) -> int:
        """Reenvía el último segmento con datos (misma secuencia): Wireshark lo marca como retransmisión."""
        seq = (self.cseq if desde_cliente else self.sseq) - len(payload)
        return self._env(desde_cliente, PSH | ACK, payload, dt=dt, seq=seq)

    def ack(self, desde_cliente: bool, dt: float = 0.005) -> int:
        return self._env(desde_cliente, ACK, dt=dt)

    def cierre(self) -> list[int]:
        f1 = self._env(True, FIN | ACK, dt=0.01)
        self.cseq += 1
        f2 = self._env(False, FIN | ACK, dt=self.rtt / 2)
        self.sseq += 1
        f3 = self._env(True, ACK, dt=self.rtt / 2)
        return [f1, f2, f3]


def leer(datos: bytes) -> list[tuple[float, bytes]]:
    """Lector mínimo para las pruebas: regresa (tiempo, trama) de un .pcap clásico."""
    magic, = struct.unpack("<I", datos[:4])
    assert magic == 0xA1B2C3D4, "no es un pcap clásico little-endian"
    i, out = 24, []
    while i < len(datos):
        seg, us, incl, _ = struct.unpack("<IIII", datos[i:i + 16])
        out.append((seg + us / 1e6, datos[i + 16:i + 16 + incl]))
        i += 16 + incl
    return out
