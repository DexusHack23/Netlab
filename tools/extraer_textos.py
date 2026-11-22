"""Saca todos los textos en español de la interfaz y del contenido fijo (misiones, academia…) para traducirlos.
Uso: python tools/extraer_textos.py  → escribe web/i18n_textos.json"""
import json, os, re, sys
from html.parser import HTMLParser

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
ES = re.compile(r"[a-záéíóúñ]{3,}", re.I)
ESP = re.compile(r"\b(el|la|los|las|de|que|y|en|con|para|un|una|tu|tus|sin|por|del|al|es|se|más|aquí|qué|cómo)\b|[áéíóúñ¿¡]", re.I)


def norm(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) < 90 and "`" not in t:
        t = re.sub(r"\d+(?:[.,]\d+)?", "{n}", t)
    return t


def util(t: str) -> bool:
    t = t.strip()
    if not t or not ES.search(t) or len(t) > 3000:
        return False
    if re.fullmatch(r"[\w.#\-\[\]=\"' :/()]+", t) and not ESP.search(t):  # selectores, ids, código
        return False
    if re.search(r"(=>|\bconst\b|\bfunction\b|\$\(|querySelector|addEventListener|\bfn\b.*\{)", t):
        return False
    sin_emoji = re.sub(r"^[^\wáéíóúñÁÉÍÓÚÑ¿¡]+", "", t)  # "⏸️ Pausar VM": la mayúscula va después del emoji
    return bool(ESP.search(t)) or (len(t.split()) <= 4 and sin_emoji[:1].isupper())


textos = set()

# ---- index.html
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.skip = 0
    def handle_starttag(s, tag, a):
        s.skip += tag in ("script", "style")
        for k, v in a:
            if k in ("placeholder", "title") and v and util(v):
                textos.add(norm(v))
    def handle_endtag(s, tag):
        s.skip -= tag in ("script", "style")
    def handle_data(s, d):
        if not s.skip and util(d):
            textos.add(norm(d))
P().feed(open(os.path.join(AQUI, "web/index.html"), encoding="utf-8").read())

# ---- JS: literales y trozos de plantillas
def quitar_expr(t: str) -> str:
    out, i, prof = [], 0, 0
    while i < len(t):
        if t.startswith("${", i) and prof == 0:
            prof, i = 1, i + 2
            out.append("\x00")
            continue
        if prof:
            prof += {"{": 1, "}": -1}.get(t[i], 0)
            i += 1
            continue
        out.append(t[i]); i += 1
    return "".join(out)

_REGEX_PREV = set("(,=:[!&|?{};+-*%<>~^")
_KW = ("return", "typeof", "case", "do", "else", "in", "of", "void", "yield", "await")


def js_textos(src: str):
    """Lee JS de verdad: devuelve [('str', texto)] y [('tpl', texto con \\x00 donde iba cada ${...})], ignorando
    comentarios y regex. Antes se emparejaban backticks con una regex y un ` dentro de un string desfasaba todo."""
    out = []
    n = len(src)

    def leer_str(i, q):
        j, buf = i + 1, []
        while j < n and src[j] != q and src[j] != "\n":
            if src[j] == "\\" and j + 1 < n:
                buf.append(src[j:j + 2]); j += 2; continue
            buf.append(src[j]); j += 1
        return j + 1, "".join(buf)

    def leer_regex(i):
        j, clase = i + 1, False
        while j < n and src[j] != "\n":
            c = src[j]
            if c == "\\":
                j += 2; continue
            if c == "[":
                clase = True
            elif c == "]":
                clase = False
            elif c == "/" and not clase:
                j += 1
                while j < n and src[j].isalpha():
                    j += 1
                return j
            j += 1
        return j

    def leer_tpl(i):
        j, buf = i + 1, []
        while j < n and src[j] != "`":
            if src[j] == "\\" and j + 1 < n:
                buf.append(src[j:j + 2]); j += 2; continue
            if src.startswith("${", j):
                buf.append("\x00")
                j = escanear(j + 2, hasta_llave=True)
                continue
            buf.append(src[j]); j += 1
        out.append(("tpl", "".join(buf)))
        return j + 1

    def escanear(i, hasta_llave=False):
        prof, prev, palabra = 0, "(", ""
        while i < n:
            c = src[i]
            if src.startswith("//", i):
                i = src.find("\n", i); i = n if i < 0 else i; continue
            if src.startswith("/*", i):
                i = src.find("*/", i + 2); i = n if i < 0 else i + 2; continue
            if c in "\"'":
                i, t = leer_str(i, c); out.append(("str", t)); prev, palabra = "a", ""; continue
            if c == "`":
                i = leer_tpl(i); prev, palabra = "a", ""; continue
            if c == "/" and (prev in _REGEX_PREV or palabra in _KW):
                i = leer_regex(i); prev, palabra = "a", ""; continue
            if hasta_llave:
                if c == "{":
                    prof += 1
                elif c == "}":
                    if prof == 0:
                        return i + 1
                    prof -= 1
            if c.isalnum() or c in "_$":
                palabra = palabra + c if prev == "w" else c
                prev = "w"
            elif not c.isspace():
                prev, palabra = c, ""
            i += 1
        return i

    escanear(0)
    return out


for f in sorted(os.listdir(os.path.join(AQUI, "web"))):
    if not f.endswith(".js") or f.startswith("i18n"):
        continue
    src = open(os.path.join(AQUI, "web", f), encoding="utf-8").read()
    for tipo, t in js_textos(src):
        if tipo == "tpl":  # frase completa con {n} donde iba ${…}: casa con "Ver una pista (2)" vía buscarEN
            for pieza in re.split(r"<[^>]*>", t):
                pieza = re.sub(r"\s+", " ", pieza.replace("\\n", " ")).strip()
                if "\x00" in pieza and pieza.count("\x00") <= 3 and len(pieza) < 90:
                    k = pieza.replace("\x00", "{n}")
                    if util(k.replace("{n}", "")) and k.replace("{n}", "").strip(" .·:—-()/"):
                        textos.add(norm(k))
        for trozo in re.split(r"<[^>]*>|\x00", t):
            trozo = trozo.replace("\\n", " ")
            if util(trozo) and not trozo.strip().startswith(("/api", "#", ".")):
                textos.add(norm(trozo))

# ---- contenido fijo del servidor (se traduce entero con tr())
contenido = set()
from core import academia, vm_misiones, temario
from core import wireshark as ws
for c in academia.CURSOS.values():
    contenido.update([c["nombre"], c["lema"]])
    for n in c["niveles"]:
        contenido.update([n["nombre"], n["cap"]])
        for m in n["misiones"]:
            contenido.update([m["titulo"], m["teoria"], m["enunciado"], *m["pistas"]])
for m in vm_misiones.MISIONES:
    contenido.update([m["nivel"], m["titulo"], m["historia"], m["objetivo"], *m["pistas"]])
for e in ws.ESCENARIOS.values():
    contenido.update([e["nombre"], e["temas"], e["nivel"]])
for t in temario.TEMAS:
    contenido.update([t["nombre"], t["nivel"]])
for d in temario.DOMINIOS:
    contenido.add(d[0])
# contenido elegido a propósito (niveles, misiones, temas): basta con que tenga letras. util() descartaba "Primeros pasos" o
# "Redes neuronales" por parecer identificadores de código (sin acentos ni artículos).
contenido = {c.strip() for c in contenido if c and ES.search(c) and not re.fullmatch(r"[A-Z0-9_.\-]+", c.strip())}

# ---- textos que arma el SERVIDOR y llegan a la interfaz (chequeo de estado, logros, SIEM, VM, mensajes de trabajos)
import ast


def _cadena(n) -> str | None:
    """Literal o f-string; en las f-strings cada {expr} se vuelve {n} (así casan con los números que pone tr())."""
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value
    if isinstance(n, ast.JoinedStr):
        partes = []
        for v in n.values:
            if isinstance(v, ast.Constant):
                partes.append(str(v.value))
            else:
                partes.append("{n}")
        return "".join(partes)
    return None


def _nombre(f) -> str:
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""


servidor = set()
# archivos cuyo texto se muestra tal cual (sin prompts largos del modelo)
for f in ("core/salud.py", "core/juego.py", "core/siem.py", "core/vm.py", "core/vm_misiones.py", "core/rvb.py"):
    ruta = os.path.join(AQUI, f)
    if not os.path.isfile(ruta):
        continue
    arbol = ast.parse(open(ruta, encoding="utf-8").read())
    ignorar = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.JoinedStr):  # sus trozos sueltos no se muestran solos
            ignorar.update(id(v) for v in n.values)
        if isinstance(n, (ast.Expr, ast.FunctionDef)) and isinstance(getattr(n, "value", None), ast.Constant):  # docstrings
            ignorar.add(id(n.value))
        if isinstance(n, ast.FunctionDef) and n.body and isinstance(n.body[0], ast.Expr):
            ignorar.add(id(n.body[0].value))
    for n in ast.walk(arbol):
        if id(n) in ignorar:
            continue
        t = _cadena(n)
        if t and len(t) < 400 and chr(10) not in t and chr(92) not in t and util(t):
            servidor.add(norm(t))
# en app.py y generador.py solo lo que se muestra: progreso(...), errores, títulos y mensajes
VISIBLES = {"progreso", "p", "RuntimeError", "ValueError", "_fase"}
for f in ("app.py", "core/generador.py", "core/academia.py", "core/rustproj.py", "core/pytorch_lab.py", "core/chisel_lab.py"):
    ruta = os.path.join(AQUI, f)
    if not os.path.isfile(ruta):
        continue
    arbol = ast.parse(open(ruta, encoding="utf-8").read())
    for n in ast.walk(arbol):
        cand = []
        if isinstance(n, ast.Call) and _nombre(n.func) in VISIBLES:
            cand += n.args[:2]
        if isinstance(n, ast.Dict):
            cand += [v for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant) and k.value in ("titulo", "error", "msg", "detalle", "veredicto")]
        for c in cand:
            t = _cadena(c)
            if t and len(t) < 400 and chr(92) not in t and util(t):
                servidor.add(norm(t))
for n in ast.walk(ast.parse(open(os.path.join(AQUI, "app.py"), encoding="utf-8").read())):
    if isinstance(n, ast.FunctionDef) and n.name == "temas_teoria":
        for m in ast.walk(n):
            t = _cadena(m)
            if t and len(t) < 400 and util(t):
                servidor.add(norm(t))
servidor = {t for t in servidor if t.replace("{n}", "").strip(" .·:—-()") and not re.search(r"&&|\|\||/dev/null|\{\{|^(grep|echo|sudo|cat|ls) ", t)}
contenido |= servidor

todo = sorted(textos | contenido)
json.dump(todo, open(os.path.join(AQUI, "web/i18n_textos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(textos), "de interfaz +", len(contenido), "de contenido (", len(servidor), "del servidor) =", len(todo))
