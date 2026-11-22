# Abre Packet Tracer (o el .pkt que le pases) con la escala de NetLab, sin ventana de consola.
# Lo usa el doble clic en archivos .pkt/.pka después de correr asociar_pkt.ps1.
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import packet_tracer  # noqa: E402

packet_tracer.abrir(sys.argv[1] if len(sys.argv) > 1 else None)
