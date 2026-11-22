"""Ruta de temas de básico a superior (basada en el temario del CCNA 200-301 + extras de CCNP).

Es fija a propósito: así la IA no inventa temas ni se salta niveles. La IA solo genera
exámenes y prácticas DENTRO de cada tema. `lab` indica si el tema se puede practicar
en Packet Tracer (si no, solo hay examen).
"""

NIVELES = ["Básico", "Intermedio", "Avanzado", "Superior"]

TEMAS = [
    # ---------------------------------------------------------------- Básico
    {"id": "fundamentos", "nivel": "Básico", "nombre": "Modelos OSI y TCP/IP, dispositivos y cableado", "lab": False,
     "clave": "capas, encapsulación, PDU, cable directo vs cruzado, consola, dispositivos de red"},
    {"id": "ipv4", "nivel": "Básico", "nombre": "Direccionamiento IPv4 y subneteo", "lab": True,
     "clave": "clases, máscara, CIDR, subneteo, VLSM, hosts por subred, direcciones privadas"},
    {"id": "cli", "nivel": "Básico", "nombre": "CLI de IOS y configuración inicial", "lab": True,
     "clave": "modos, hostname, enable secret, contraseñas de consola y vty, banner motd, "
              "service password-encryption, guardar configuración"},
    {"id": "ip_basica", "nivel": "Básico", "nombre": "Configurar interfaces y conectividad básica", "lab": True,
     "clave": "ip address en router, no shutdown, IP y gateway en PCs, ping, show ip interface brief"},
    {"id": "switching", "nivel": "Básico", "nombre": "Conmutación Ethernet y tabla MAC", "lab": True,
     "clave": "trama Ethernet, aprendizaje y reenvío de MAC, dominio de colisión y difusión, "
              "SVI de administración e ip default-gateway en switch"},
    {"id": "ipv6", "nivel": "Básico", "nombre": "Direccionamiento IPv6", "lab": True,
     "clave": "formato, abreviación, link-local, global unicast, EUI-64, SLAAC, ipv6 unicast-routing"},
    # ------------------------------------------------------------ Intermedio
    {"id": "vlans", "nivel": "Intermedio", "nombre": "VLANs y puertos de acceso", "lab": True,
     "clave": "crear VLANs, nombres, switchport mode access, switchport access vlan, show vlan brief"},
    {"id": "troncales", "nivel": "Intermedio", "nombre": "Troncales 802.1Q y VLAN nativa", "lab": True,
     "clave": "switchport mode trunk, allowed vlan, native vlan, DTP, show interfaces trunk"},
    {"id": "roas", "nivel": "Intermedio", "nombre": "Enrutamiento entre VLANs (router-on-a-stick)", "lab": True,
     "clave": "subinterfaces, encapsulation dot1Q, gateway por VLAN, troncal hacia el router"},
    {"id": "svi_l3", "nivel": "Intermedio", "nombre": "Enrutamiento entre VLANs con switch multicapa (SVI)", "lab": True,
     "clave": "ip routing, interface vlan, no switchport, switch multicapa 3560"},
    {"id": "estaticas", "nivel": "Intermedio", "nombre": "Rutas estáticas y por defecto", "lab": True,
     "clave": "ip route, siguiente salto vs interfaz de salida, ruta por defecto, ruta flotante, distancia administrativa"},
    {"id": "dhcp", "nivel": "Intermedio", "nombre": "DHCP en router y relay", "lab": True,
     "clave": "ip dhcp pool, network, default-router, dns-server, excluded-address, ip helper-address"},
    {"id": "stp", "nivel": "Intermedio", "nombre": "Spanning Tree (STP/RSTP)", "lab": True,
     "clave": "root bridge, prioridad, roles y estados de puerto, PortFast, BPDU Guard, rapid-pvst"},
    {"id": "etherchannel", "nivel": "Intermedio", "nombre": "EtherChannel (LACP/PAgP)", "lab": True,
     "clave": "channel-group, mode active/passive/desirable/auto/on, interface port-channel, troncal en el port-channel"},
    {"id": "cdp_lldp", "nivel": "Intermedio", "nombre": "CDP, LLDP, NTP y Syslog", "lab": True,
     "clave": "show cdp neighbors, lldp run, ntp server, logging host, niveles de severidad"},
    # -------------------------------------------------------------- Avanzado
    {"id": "ospf", "nivel": "Avanzado", "nombre": "OSPFv2 de área única", "lab": True,
     "clave": "router ospf, network con wildcard, area 0, router-id, passive-interface, "
              "default-information originate, DR/BDR, costo"},
    {"id": "acl", "nivel": "Avanzado", "nombre": "ACL estándar y extendidas", "lab": True,
     "clave": "access-list numerada y nombrada, wildcard, ip access-group in/out, ubicación correcta, access-class en vty"},
    {"id": "nat", "nivel": "Avanzado", "nombre": "NAT estático, dinámico y PAT", "lab": True,
     "clave": "ip nat inside/outside, ip nat inside source static, pool, overload, show ip nat translations"},
    {"id": "ssh_seguridad", "nivel": "Avanzado", "nombre": "Acceso seguro: SSH y endurecimiento", "lab": True,
     "clave": "ip domain-name, crypto key generate rsa, username secret, ip ssh version 2, "
              "line vty transport input ssh, login local, exec-timeout"},
    {"id": "port_security", "nivel": "Avanzado", "nombre": "Seguridad de puertos, DHCP Snooping y DAI", "lab": True,
     "clave": "switchport port-security, maximum, sticky, violation, ip dhcp snooping, trust, ip arp inspection"},
    {"id": "fhrp", "nivel": "Avanzado", "nombre": "Redundancia de gateway (HSRP)", "lab": True,
     "clave": "standby ip, priority, preempt, IP virtual, show standby"},
    {"id": "wireless", "nivel": "Avanzado", "nombre": "Redes inalámbricas y WLC", "lab": False,
     "clave": "802.11, SSID, WPA2/WPA3, AP autónomo vs ligero, CAPWAP, WLC"},
    {"id": "automatizacion", "nivel": "Avanzado", "nombre": "Automatización y programabilidad", "lab": False,
     "clave": "SDN, plano de control/datos, REST, JSON, Ansible, Terraform, controladores"},
    # -------------------------------------------------------------- Superior
    {"id": "ospf_multi", "nivel": "Superior", "nombre": "OSPF multiárea y autenticación", "lab": True,
     "clave": "ABR, áreas no cero, LSAs tipo 1-3, autenticación md5, summarización"},
    {"id": "eigrp", "nivel": "Superior", "nombre": "EIGRP", "lab": True,
     "clave": "router eigrp, AS, network con wildcard, no auto-summary, sucesor y sucesor factible"},
    {"id": "bgp", "nivel": "Superior", "nombre": "BGP básico (eBGP)", "lab": True,
     "clave": "router bgp, neighbor remote-as, network mask, show ip bgp summary"},
    {"id": "ipv6_routing", "nivel": "Superior", "nombre": "Enrutamiento IPv6 (estático y OSPFv3)", "lab": True,
     "clave": "ipv6 route, ipv6 router ospf, ipv6 ospf area en interfaz"},
    {"id": "diseno", "nivel": "Superior", "nombre": "Diseño integrador de campus (todo junto)", "lab": True,
     "clave": "VLANs + troncales + enrutamiento entre VLANs + DHCP + OSPF + NAT + ACL + SSH en una sola red"},
]

POR_ID = {t["id"]: t for t in TEMAS}

# Dominios del examen CCNA 200-301 v1.1 y su peso, con los temas de la ruta que caen en cada uno
DOMINIOS = [
    ("Fundamentos de red", 0.20, ["fundamentos", "ipv4", "ipv6", "switching", "ip_basica"]),
    ("Acceso a la red", 0.20, ["vlans", "troncales", "stp", "etherchannel", "cdp_lldp", "wireless"]),
    ("Conectividad IP", 0.25, ["estaticas", "ospf", "roas", "svi_l3", "fhrp"]),
    ("Servicios IP", 0.10, ["dhcp", "nat", "cdp_lldp"]),
    ("Seguridad", 0.15, ["acl", "ssh_seguridad", "port_security", "cli"]),
    ("Automatización y programabilidad", 0.10, ["automatizacion"]),
]


def tema(tema_id: str) -> dict | None:
    return POR_ID.get(tema_id)


def recomendado(progreso: dict[str, dict]) -> dict:
    """Siguiente tema: el primero de la ruta sin dominar (mejor calificación < 8)."""
    for t in TEMAS:
        p = progreso.get(t["id"])
        if not p or (p.get("mejor") or 0) < 8:
            return t
    return TEMAS[-1]
