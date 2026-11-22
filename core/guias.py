"""Tus guías como material de consulta (RAG local con Ollama).

Echas PDFs, .txt o .md en la carpeta `guias` y la app los parte en trozos, los convierte en vectores con
un modelo de embeddings de Ollama y los guarda en datos/guias.db. Cuando genera una práctica, un examen o
explica una captura, busca los trozos más parecidos al tema y se los pasa al modelo como referencia.

Archivo especial: `wireshark-campos-filtros.txt` (salida de `tshark -G fields`) no se vectoriza: se usa
como lista de campos válidos para sugerirte el nombre correcto cuando un filtro trae un campo inexistente.
"""
from __future__ import annotations

import array
import difflib
import math
import operator
import os
import re
import sqlite3
import threading

from . import ollama

EXTENSIONES = (".pdf", ".txt", ".md")
CAMPOS_ARCHIVO = "wireshark-campos-filtros.txt"
PREFERIDOS = ["qwen3-embedding:0.6b", "qwen3-embedding:4b", "qwen3-embedding", "bge-m3", "nomic-embed-text"]
TROZO = 1100      # caracteres por trozo
TRASLAPE = 150

_lock = threading.Lock()
_cache: dict = {"modelo": None, "trozos": None}
_campos: set[str] | None = None


# ---------------------------------------------------------------- utilidades
def modelo_embed(preferido: str = "") -> str | None:
    disponibles = ollama.list_models()
    def esta(m):
        return m in disponibles or f"{m}:latest" in disponibles
    for m in ([preferido] if preferido else []) + PREFERIDOS:
        if m and esta(m):
            return m if m in disponibles else f"{m}:latest"
    return next((m for m in disponibles if "embed" in m), None)


def _prefijo(modelo: str, consulta: bool) -> str:
    if "nomic" in modelo:
        return "search_query: " if consulta else "search_document: "
    if "qwen3-embedding" in modelo and consulta:
        return "Instruct: Dada una pregunta sobre redes Cisco o Wireshark, encuentra el texto que la responde\nQuery: "
    return ""


def _embed(modelo: str, textos: list[str], consulta: bool = False, keep: str | int = "2m") -> list[array.array]:
    pre = _prefijo(modelo, consulta)
    r = ollama._post("/api/embed", {"model": modelo, "input": [pre + t for t in textos], "keep_alive": keep,
                                    "truncate": True}, timeout=600)
    out = []
    for v in r.get("embeddings", []):
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append(array.array("f", (x / n for x in v)))
    return out


def _conn(ruta_db: str) -> sqlite3.Connection:
    c = sqlite3.connect(ruta_db)
    c.executescript("""
    PRAGMA journal_mode=DELETE;
    CREATE TABLE IF NOT EXISTS archivos(nombre TEXT PRIMARY KEY, mtime REAL, tam INTEGER, modelo TEXT, trozos INTEGER);
    CREATE TABLE IF NOT EXISTS trozos(id INTEGER PRIMARY KEY, archivo TEXT, pagina INTEGER, texto TEXT, vec BLOB);
    """)
    return c


# ---------------------------------------------------------------- lectura de archivos
def _leer(ruta: str) -> list[tuple[int, str]]:
    """[(página, texto)]. Los .txt/.md cuentan como página 0."""
    if ruta.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("Falta pypdf para leer PDFs (py -m pip install pypdf en el Python de NetLab).")
        lector = PdfReader(ruta)
        return [(i + 1, pag.extract_text() or "") for i, pag in enumerate(lector.pages)]
    with open(ruta, encoding="utf-8", errors="replace") as f:
        return [(0, f.read())]


def _trozos(paginas: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out = []
    for pag, texto in paginas:
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
        i = 0
        while i < len(texto):
            fin = min(len(texto), i + TROZO)
            if fin < len(texto):  # corta en un salto de línea o punto cercano
                corte = max(texto.rfind("\n", i + TROZO // 2, fin), texto.rfind(". ", i + TROZO // 2, fin))
                fin = corte + 1 if corte > 0 else fin
            t = texto[i:fin].strip()
            if len(re.sub(r"\W", "", t)) > 80:  # descarta índices vacíos y pies de página
                out.append((pag, t))
            if fin >= len(texto):
                break
            i = max(fin - TRASLAPE, i + 1)
    return out


# ---------------------------------------------------------------- índice
def estado(carpeta: str, ruta_db: str, modelo_actual: str | None = None) -> dict:
    archivos = []
    with _lock:
        c = _conn(ruta_db)
        hechos = {r[0]: r for r in c.execute("SELECT nombre, mtime, tam, modelo, trozos FROM archivos")}
        c.close()
    if os.path.isdir(carpeta):
        for n in sorted(os.listdir(carpeta)):
            ruta = os.path.join(carpeta, n)
            if not os.path.isfile(ruta) or not n.lower().endswith(EXTENSIONES):
                continue
            st = os.stat(ruta)
            h = hechos.get(n)
            especial = n.lower() == CAMPOS_ARCHIVO
            archivos.append({"nombre": n, "mb": round(st.st_size / 1e6, 1), "especial": especial,
                             "indexado": bool(h and h[1] == st.st_mtime and h[2] == st.st_size
                                              and (not modelo_actual or h[3] == modelo_actual)),
                             "trozos": h[4] if h else 0, "modelo": h[3] if h else ""})
    return {"carpeta": carpeta, "existe": os.path.isdir(carpeta), "archivos": archivos,
            "pendientes": sum(1 for a in archivos if not a["indexado"] and not a["especial"])}


def indexar(carpeta: str, ruta_db: str, preferido: str = "", progreso=lambda m: None) -> dict:
    modelo = modelo_embed(preferido)
    if not modelo:
        raise RuntimeError("No tienes un modelo de embeddings. En PowerShell: ollama pull qwen3-embedding:0.6b")
    est = estado(carpeta, ruta_db, modelo)
    presentes = {a["nombre"] for a in est["archivos"]}
    with _lock:
        c = _conn(ruta_db)
        # si cambió el modelo, todo se rehace (los vectores de modelos distintos no se pueden mezclar)
        viejos = {r[0] for r in c.execute("SELECT DISTINCT modelo FROM archivos")}
        if viejos and viejos != {modelo}:
            c.execute("DELETE FROM archivos")
            c.execute("DELETE FROM trozos")
            est = estado(carpeta, ruta_db, modelo)
        for (n,) in c.execute("SELECT nombre FROM archivos").fetchall():
            if n not in presentes:
                c.execute("DELETE FROM archivos WHERE nombre=?", (n,))
                c.execute("DELETE FROM trozos WHERE archivo=?", (n,))
        c.commit()
        c.close()
    hechos, errores = 0, []
    for a in est["archivos"]:
        if a["indexado"] or a["especial"]:
            continue
        ruta = os.path.join(carpeta, a["nombre"])
        try:
            progreso(f"Leyendo {a['nombre']}…")
            trozos = _trozos(_leer(ruta))
            vecs = []
            for i in range(0, len(trozos), 32):
                progreso(f"{a['nombre']}: vectorizando {min(i + 32, len(trozos))}/{len(trozos)} con {modelo}…")
                vecs += _embed(modelo, [t for _, t in trozos[i:i + 32]])
            st = os.stat(ruta)
            with _lock:
                c = _conn(ruta_db)
                c.execute("DELETE FROM trozos WHERE archivo=?", (a["nombre"],))
                c.executemany("INSERT INTO trozos(archivo,pagina,texto,vec) VALUES(?,?,?,?)",
                              [(a["nombre"], p, t, v.tobytes()) for (p, t), v in zip(trozos, vecs)])
                c.execute("INSERT OR REPLACE INTO archivos VALUES(?,?,?,?,?)",
                          (a["nombre"], st.st_mtime, st.st_size, modelo, len(trozos)))
                c.commit()
                c.close()
            hechos += 1
        except Exception as e:  # noqa: BLE001  un PDF dañado no debe tirar a los demás
            errores.append(f"{a['nombre']}: {e}")
    _cache["trozos"] = None
    return {"modelo": modelo, "indexados": hechos, "errores": errores, **estado(carpeta, ruta_db, modelo)}


def _cargar(ruta_db: str):
    if _cache["trozos"] is None:
        with _lock:
            c = _conn(ruta_db)
            filas = c.execute("SELECT t.archivo, t.pagina, t.texto, t.vec, a.modelo FROM trozos t "
                              "JOIN archivos a ON a.nombre = t.archivo").fetchall()
            c.close()
        _cache["modelo"] = filas[0][4] if filas else None
        _cache["trozos"] = [(f[0], f[1], f[2], array.array("f", f[3])) for f in filas]
    return _cache["modelo"], _cache["trozos"]


# Qué guías le tocan a cada mundo (por el nombre del archivo). Antes TODAS se mezclaban: una lección de Rust o un examen
# de Linux recibían pedazos de las guías de Cisco (que son casi la mitad) y el modelo mezclaba temas.
FUENTES = {
    "wireshark": ("wireshark", "wca-", "rfc-"),
    "linux": ("linux-", "nist-", "mitre-", "kernel-", "arch-"),
    "soc": ("mitre-", "nist-", "linux-", "cisa-", "enisa-", "ransomware-", "owasp-cs", "owasp-top10", "owasp-api", "owasp-asvs"),
    "purple": ("mitre-", "nist-", "linux-", "cisa-", "enisa-", "ransomware-", "owasp-", "blackarch-"),
    "rust": ("rust-",),
    "rustproj": ("rust-", "rfc-"),
    "ia": ("ia-",),
    "torch": ("ia-",),
    "cpu": ("risc-v", "cpu-", "sv-"),
    "chisel": ("cpu-", "risc-v", "sv-"),
    "sv": ("sv-", "cpu-"),
}
_CCNA = ("ccna", "cisco", "0guia", "day 1", "redes", "rfc-")


def de_mundo(archivo: str, mundo: str | None) -> bool:
    """¿Esta guía sirve para este mundo? CCNA se queda con lo suyo y con cualquier guía que no sea de otro mundo."""
    if not mundo:
        return True
    a = archivo.lower()
    if mundo in FUENTES:
        return a.startswith(FUENTES[mundo])
    ajenas = {x for m, xs in FUENTES.items() for x in xs if x != "rfc-"}
    return a.startswith(_CCNA) or not any(a.startswith(x) for x in ajenas)


def buscar(ruta_db: str, consulta: str, k: int = 4, keep: str | int = "2m", mundo: str | None = None) -> list[dict]:
    modelo, trozos = _cargar(ruta_db)
    if not trozos or not consulta.strip():
        return []
    q = _embed(modelo, [consulta[:2000]], consulta=True, keep=keep)[0]
    mul = operator.mul
    punt = sorted(((sum(map(mul, q, v)), i) for i, (_, _, _, v) in enumerate(trozos)), reverse=True)
    out, vistos = [], set()
    for s, i in punt:
        if len(out) >= k or s < 0.3:
            break
        archivo, pagina, texto, _ = trozos[i]
        if not de_mundo(archivo, mundo):
            continue
        clave = (archivo, pagina)
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append({"archivo": archivo, "pagina": pagina, "texto": texto, "similitud": round(s, 3)})
    return out


def contexto(ruta_db: str, consulta: str, k: int = 3, max_chars: int = 3200, min_sim: float = 0.55,
             mundo: str | None = None) -> str:
    """Texto listo para meter en el prompt (o "" si no hay guías o algo falla: nunca rompe la generación)."""
    try:
        # solo lo que de verdad se parece: un fragmento flojo confunde más al modelo de lo que ayuda
        # keep=0: se descarga en cuanto contesta para dejarle la VRAM al modelo que genera
        res = [r for r in buscar(ruta_db, consulta, k, keep=0, mundo=mundo) if r["similitud"] >= min_sim]
    except Exception:  # noqa: BLE001
        return ""
    partes, total = [], 0
    for r in res:
        fuente = f"[{r['archivo']}" + (f", p. {r['pagina']}]" if r["pagina"] else "]")
        t = r["texto"][: max_chars - total]
        if len(t) < 200:
            break
        partes.append(f"{fuente}\n{t}")
        total += len(t)
    return "\n\n".join(partes)


# ---------------------------------------------------------------- campos de Wireshark
def campos(carpeta: str) -> set[str]:
    global _campos
    if _campos is None:
        _campos = set()
        ruta = os.path.join(carpeta, CAMPOS_ARCHIVO)
        if os.path.isfile(ruta):
            with open(ruta, encoding="utf-8-sig", errors="replace") as f:
                for linea in f:
                    p = linea.rstrip("\r\n").split("\t")
                    if len(p) > 2 and p[0] in ("F", "P"):
                        _campos.add(p[2])
    return _campos


def sugerir_campo(carpeta: str, error_tshark: str) -> str:
    """Si tshark dice que un campo no existe, sugiere los nombres válidos más parecidos."""
    m = re.search(r'"([\w.\-]+)" is neither a field', error_tshark) or re.search(r"\"([\w.\-]+)\"", error_tshark)
    if not m:
        return ""
    malo = m.group(1)
    parecidos = difflib.get_close_matches(malo, campos(carpeta), n=3, cutoff=0.6)
    return f"¿Quisiste decir {', '.join(parecidos)}?" if parecidos else ""
