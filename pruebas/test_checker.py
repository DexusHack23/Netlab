"""Pruebas del parser y del verificador. Ejecuta: python -m pruebas.test_checker"""
import sys

sys.dont_write_bytecode = True

from core.checker import Evidence, grade
from core.ios_parser import expand_iface_range, norm_iface, parse_config

R1_RUNNING = """
Building configuration...

Current configuration : 1234 bytes
!
version 15.1
hostname R1
!
ip dhcp excluded-address 192.168.10.1 192.168.10.10
!
ip dhcp pool VENTAS
 network 192.168.10.0 255.255.255.0
 default-router 192.168.10.1
!
interface GigabitEthernet0/0
 no ip address
 duplex auto
!
interface GigabitEthernet0/0.10
 encapsulation dot1Q 10
 ip address 192.168.10.1 255.255.255.0
!
interface GigabitEthernet0/0.20
 encapsulation dot1Q 20
 ip address 192.168.20.1 255.255.255.0
!
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.252
 shutdown
!
router ospf 1
 router-id 1.1.1.1
 network 192.168.10.0 0.0.0.255 area 0
 network 10.0.0.0 0.0.0.3 area 0
!
ip route 0.0.0.0 0.0.0.0 10.0.0.2
!
line vty 0 4
 login
!
end
"""

SW1_TYPED = """
SW1>enable
SW1#conf t
Enter configuration commands, one per line.  End with CNTL/Z.
Switch(config)#hostname SW1
SW1(config)#vlan 10
SW1(config-vlan)#name VENTAS
SW1(config-vlan)#exit
SW1(config)#interface range fa0/1 - 5
SW1(config-if-range)#switchport mode access
SW1(config-if-range)#switchport access vlan 10
SW1(config-if-range)#exit
SW1(config)#int g0/1
SW1(config-if)#switchport mode trunk
SW1(config-if)#switchport trunk allowed vlan 10,20
SW1(config-if)#end
"""

SW1_SHOW = """
SW1#show vlan brief

VLAN Name                             Status    Ports
---- -------------------------------- --------- -------------------------------
1    default                          active    Fa0/6, Fa0/7, Fa0/8, Fa0/9
                                                Fa0/10, Gig0/2
10   VENTAS                           active    Fa0/1, Fa0/2, Fa0/3, Fa0/4
                                                Fa0/5
20   RRHH                             active
"""

PC1 = """
C:\\>ipconfig

FastEthernet0 Connection:(default port)

   Connection-specific DNS Suffix..:
   Link-local IPv6 Address.........: FE80::1
   IPv6 Address....................: ::
   IPv4 Address....................: 192.168.10.11
   Subnet Mask.....................: 255.255.255.0
   Default Gateway.................: ::
                                     192.168.10.1

C:\\>ping 192.168.20.11

Pinging 192.168.20.11 with 32 bytes of data:

Request timed out.
Reply from 192.168.20.11: bytes=32 time<1ms TTL=127
Reply from 192.168.20.11: bytes=32 time<1ms TTL=127

Ping statistics for 192.168.20.11:
    Packets: Sent = 4, Received = 2, Lost = 2 (50% loss),

C:\\>ping 8.8.8.8

Pinging 8.8.8.8 with 32 bytes of data:

Request timed out.
Request timed out.

Ping statistics for 8.8.8.8:
    Packets: Sent = 4, Received = 0, Lost = 4 (100% loss),
"""

PRACTICA = {"verificaciones": [
    {"id": "1", "dispositivo": "R1", "tipo": "hostname", "nombre": "R1"},
    {"id": "2", "dispositivo": "R1", "tipo": "subinterfaz", "interfaz": "g0/0.10", "vlan": "10", "ip": "192.168.10.1", "mascara": "255.255.255.0"},
    {"id": "3", "dispositivo": "R1", "tipo": "ip_interfaz", "interfaz": "Gi0/1", "ip": "10.0.0.1", "mascara": "255.255.255.252"},
    {"id": "4", "dispositivo": "R1", "tipo": "ospf_red", "red": "192.168.20.0", "wildcard": "0.0.0.255", "area": "0", "proceso": "1"},
    {"id": "5", "dispositivo": "R1", "tipo": "ospf_red", "red": "192.168.10.0", "wildcard": "0.0.0.255", "area": "0"},
    {"id": "6", "dispositivo": "R1", "tipo": "dhcp_pool", "red": "192.168.10.0", "mascara": "255.255.255.0", "gateway": "192.168.10.1"},
    {"id": "7", "dispositivo": "R1", "tipo": "dhcp_excluido", "ip": "192.168.10.1", "ip_fin": "192.168.10.5"},
    {"id": "8", "dispositivo": "R1", "tipo": "ruta_default", "siguiente_salto": "10.0.0.2"},
    {"id": "9", "dispositivo": "R1", "tipo": "ssh"},
    {"id": "10", "dispositivo": "SW1", "tipo": "vlan", "vlan": "20", "nombre": "RRHH"},
    {"id": "11", "dispositivo": "SW1", "tipo": "puerto_acceso", "interfaz": "Fa0/3", "vlan": "10"},
    {"id": "12", "dispositivo": "SW1", "tipo": "puerto_troncal", "interfaz": "G0/1", "vlan": "10,20,30"},
    {"id": "13", "dispositivo": "PC1", "tipo": "ip_pc", "ip": "192.168.10.11", "mascara": "255.255.255.0", "gateway": "192.168.10.1"},
    {"id": "14", "dispositivo": "PC1", "tipo": "ping", "ip": "192.168.20.11"},
    {"id": "15", "dispositivo": "PC1", "tipo": "ping", "ip": "8.8.8.8"},
    {"id": "16", "dispositivo": "PC1", "tipo": "ping", "ip": "192.168.30.1"},
    {"id": "17", "dispositivo": "SW2", "tipo": "hostname", "nombre": "SW2"},
]}

ESPERADO = {
    "1": "ok", "2": "ok", "3": "falla", "4": "falla", "5": "ok", "6": "ok", "7": "ok",
    "8": "ok", "9": "falla", "10": "ok", "11": "ok", "12": "falla", "13": "ok",
    "14": "ok", "15": "falla", "16": "sin_datos", "17": "sin_datos",
}


def main():
    assert norm_iface("g0/0.10") == "GigabitEthernet0/0.10"
    assert norm_iface("Fa0/1") == "FastEthernet0/1"
    assert norm_iface("se0/0/0") == "Serial0/0/0"
    assert norm_iface("vlan 10".replace(" ", "")) == "Vlan10"
    assert expand_iface_range("fa0/1 - 3, g0/1") == [
        "FastEthernet0/1", "FastEthernet0/2", "FastEthernet0/3", "GigabitEthernet0/1"]
    sw = parse_config(SW1_TYPED)
    assert sw.hostname == "SW1", sw.hostname
    assert "switchport access vlan 10" in sw.iface("fa0/4"), sw.iface("fa0/4")

    ev = {"R1": Evidence(R1_RUNNING), "SW1": Evidence(SW1_TYPED, SW1_SHOW), "PC1": Evidence("", PC1)}
    r = grade(PRACTICA, ev)
    bad = []
    for res in r["resultados"]:
        if res["estado"] != ESPERADO[res["id"]]:
            bad.append((res["id"], res["tipo"], res["estado"], ESPERADO[res["id"]], res["detalle"]))
    for res in r["resultados"]:
        print(f"  [{res['estado']:9}] #{res['id']:>2} {res['tipo']:15} {res['detalle']}")
    if bad:
        print("\nNO COINCIDEN:")
        for b in bad:
            print("  ", b)
        raise SystemExit(1)
    print(f"\nTodo bien. Calificación de prueba: {r['calificacion']}/10")


if __name__ == "__main__":
    main()
