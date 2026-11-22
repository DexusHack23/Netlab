"""Abrir Packet Tracer (y archivos .pkt/.pka) con la escala que elegiste.

Packet Tracer 9.0.1 no guarda el tamaño de letra de Preferences, así que se agranda toda
la interfaz con la variable QT_SCALE_FACTOR al abrirlo. La escala se lee de
datos/config.json ("escala_pt"); por defecto 1.25.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_RUTA = os.path.join(AQUI, "datos", "config.json")
ESCALA_DEFECTO = "1.25"

EXE_CANDIDATOS = [
    r"C:\Program Files\Cisco Packet Tracer 9.0.1\bin\PacketTracer.exe",
    r"C:\Program Files\Cisco Packet Tracer 9.0.0\bin\PacketTracer.exe",
    r"C:\Program Files\Cisco Packet Tracer 8.2.2\bin\PacketTracer.exe",
]


def exe() -> str | None:
    return next((p for p in EXE_CANDIDATOS if os.path.isfile(p)), None) or shutil.which("PacketTracer")


def escala() -> str:
    try:
        with open(CONFIG_RUTA, encoding="utf-8") as f:
            valor = str(json.load(f).get("escala_pt") or ESCALA_DEFECTO)
    except (OSError, ValueError):
        valor = ESCALA_DEFECTO
    try:
        return str(min(max(float(valor), 0.8), 2.5))
    except ValueError:
        return ESCALA_DEFECTO


def abrir(archivo: str | None = None) -> dict:
    ruta_exe = exe()
    if not ruta_exe:
        return {"ok": False, "error": "No encontré PacketTracer.exe en Archivos de programa."}
    args = [ruta_exe]
    if archivo:
        if not os.path.isfile(archivo) or os.path.splitext(archivo)[1].lower() not in (".pkt", ".pka", ".pkz"):
            return {"ok": False, "error": "Ese archivo no es una práctica de Packet Tracer."}
        args.append(archivo)
    entorno = dict(os.environ, QT_SCALE_FACTOR=escala())
    subprocess.Popen(args, close_fds=True, env=entorno, cwd=os.path.dirname(ruta_exe))
    return {"ok": True, "escala": entorno["QT_SCALE_FACTOR"]}
