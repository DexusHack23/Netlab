"""SIEM real para NetLab: Elasticsearch + Kibana corriendo DENTRO de la VM de Ubuntu.

- `SCRIPT_INSTALAR` instala el stack (una sola vez, queda en la instantánea 'limpio').
- Los escenarios (brute-force, escaneo, beacon, exfil…) los GENERA NetLab en el host con verdad de fondo,
  los sube a Elastic por el puerto reenviado 9200, y el alumno los caza en Kibana (127.0.0.1:5601).
- NetLab califica la respuesta contra la verdad que él mismo sembró: ejercicios de detección infinitos.
"""
from __future__ import annotations

import datetime as dt
import ipaddress
import json
import random
import urllib.request

ES = "http://127.0.0.1:9200"  # puerto reenviado del host a la VM
KIBANA = "http://127.0.0.1:5601"
INDICE = "lab-logs"

# ---------------------------------------------------------------- instalación (corre en la VM, como root)
VERSION = "8.15.3"
SCRIPT_INSTALAR = r"""
set -e
export DEBIAN_FRONTEND=noninteractive
VER="__VER__"

marca=/opt/netlab/siem_listo

# la descarga/instalación apt solo si aún no está (el resto SIEMPRE se reescribe: así un arreglo de config se aplica al re-ejecutar)
if ! dpkg -s elasticsearch >/dev/null 2>&1 || ! dpkg -s kibana >/dev/null 2>&1; then
  echo "::: repositorio de Elastic"
  apt-get install -y apt-transport-https wget gpg curl >/dev/null 2>&1 || true
  rm -f /usr/share/keyrings/elastic.gpg
  wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --batch --yes --dearmor -o /usr/share/keyrings/elastic.gpg
  echo "deb [signed-by=/usr/share/keyrings/elastic.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" > /etc/apt/sources.list.d/elastic-8.x.list
  apt-get update >/dev/null 2>&1
  echo "::: descargando Elasticsearch + Kibana (puede tardar varios minutos)"
  apt-get install -y elasticsearch=$VER kibana=$VER >/dev/null 2>&1
else
  echo "::: Elasticsearch y Kibana ya instalados; solo reconfiguro"
fi

echo "::: configurando Elasticsearch (nodo único, sin seguridad: laboratorio local)"
cat > /etc/elasticsearch/elasticsearch.yml <<'YML'
cluster.name: netlab-siem
node.name: netlab
# rutas del paquete (propiedad del usuario elasticsearch): sin esto ES usa /usr/share/... y no puede escribir sus logs
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
network.host: 0.0.0.0
http.port: 9200
discovery.type: single-node
xpack.security.enabled: false
xpack.security.http.ssl.enabled: false
xpack.security.transport.ssl.enabled: false
xpack.ml.enabled: false
ingest.geoip.downloader.enabled: false
YML
mkdir -p /etc/elasticsearch/jvm.options.d
printf -- "-Xms1g\n-Xmx1g\n" > /etc/elasticsearch/jvm.options.d/heap.options

echo "::: configurando Kibana"
cat > /etc/kibana/kibana.yml <<'YML'
server.host: "0.0.0.0"
server.port: 5601
server.publicBaseUrl: "http://127.0.0.1:5601"
elasticsearch.hosts: ["http://localhost:9200"]
telemetry.enabled: false
YML

echo "::: requisitos del kernel para Elasticsearch (mmap)"
sysctl -w vm.max_map_count=262144 >/dev/null 2>&1 || true
echo "vm.max_map_count=262144" > /etc/sysctl.d/99-elastic.conf

echo "::: dejando los servicios listos para arrancar en el próximo reinicio"
systemctl daemon-reload
# los HABILITAMOS pero NO los arrancamos aquí: arrancar Elastic ahoga la VM y tira esta sesión SSH.
# En el reinicio limpio systemd los levanta solos y NetLab lo verifica desde el host por el puerto 9200.
systemctl enable elasticsearch kibana >/dev/null 2>&1

touch "$marca"
echo "INSTALADO_OK"
"""


def script_instalar() -> str:
    return SCRIPT_INSTALAR.replace("__VER__", VERSION)


# ---------------------------------------------------------------- Elastic desde el host (NetLab, Windows)
def _pedir(ruta: str, datos: bytes | None = None, metodo: str = "GET", base: str = ES, timeout: int = 20) -> tuple[int, str]:
    req = urllib.request.Request(base + ruta, data=datos, method=metodo,
                                 headers={"Content-Type": "application/json", "kbn-xsrf": "netlab"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def es_vivo() -> bool:
    code, _ = _pedir("/", timeout=8)
    return code == 200


def kibana_vivo() -> bool:
    code, out = _pedir("/api/status", base=KIBANA, timeout=8)
    return code == 200 and '"level":"available"' in out or code == 200


def estado_siem() -> dict:
    return {"es": es_vivo(), "kibana": kibana_vivo()}


def _bulk(docs: list[dict]) -> tuple[int, str]:
    lineas = []
    for d in docs:
        lineas.append(json.dumps({"index": {"_index": INDICE}}))
        lineas.append(json.dumps(d))
    cuerpo = ("\n".join(lineas) + "\n").encode("utf-8")
    return _pedir("/_bulk?refresh=wait_for", cuerpo, "POST", timeout=60)


def reiniciar_indice() -> None:
    """Borra el índice de laboratorio y crea el mapping + la data view de Kibana si falta."""
    _pedir("/" + INDICE, metodo="DELETE")
    mapping = json.dumps({
        "mappings": {"properties": {
            "@timestamp": {"type": "date"},
            "src_ip": {"type": "ip"}, "dst_ip": {"type": "ip"},
            "dst_port": {"type": "integer"}, "src_port": {"type": "integer"},
            "user": {"type": "keyword"}, "accion": {"type": "keyword"}, "resultado": {"type": "keyword"},
            "proto": {"type": "keyword"}, "bytes": {"type": "long"}, "host": {"type": "keyword"},
            "event_id": {"type": "integer"}, "url": {"type": "keyword"}, "status": {"type": "integer"},
            "mensaje": {"type": "text"},
        }}
    }).encode("utf-8")
    _pedir("/" + INDICE, mapping, "PUT")
    # data view en Kibana (idempotente: si ya existe, Kibana responde 409 y no pasa nada)
    dv = json.dumps({"data_view": {"title": INDICE, "name": "lab-logs", "timeFieldName": "@timestamp"}}).encode("utf-8")
    _pedir("/api/data_views/data_view", dv, "POST", base=KIBANA, timeout=20)


# ---------------------------------------------------------------- utilidades de generación
def _ip_interna(rng: random.Random) -> str:
    return f"10.0.{rng.randint(0, 20)}.{rng.randint(2, 254)}"


def _ip_externa(rng: random.Random) -> str:
    while True:
        ip = ipaddress.ip_address(rng.randint(0x01000000, 0xDF000000))
        if not (ip.is_private or ip.is_loopback or ip.is_multicast or ip.is_reserved):
            return str(ip)


USUARIOS = ["jdiaz", "mlopez", "arojas", "svargas", "root", "admin", "soporte", "ktorres", "lgomez", "administrador"]
HOSTS = ["PC-VENTAS01", "SRV-DC01", "PC-RH04", "SRV-WEB01", "PC-FIN02", "SRV-FILE01", "PC-TI07"]
URLS = ["/", "/login", "/inicio", "/perfil", "/reportes", "/api/datos", "/admin", "/salir", "/productos"]


def _t(base: dt.datetime, seg: float) -> str:
    return (base + dt.timedelta(seconds=seg)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---------------------------------------------------------------- escenarios (devuelven docs + verdad + preguntas)
def esc_fuerza_bruta(rng: random.Random) -> dict:
    """Muchos 4625 (login fallido) desde una IP y al final un 4624 (éxito): cuenta comprometida."""
    base = dt.datetime.utcnow() - dt.timedelta(hours=rng.randint(2, 20))
    atacante = _ip_externa(rng)
    victima = rng.choice(USUARIOS)
    host = rng.choice([h for h in HOSTS if h.startswith("SRV")])
    docs = []
    # ruido: logins normales exitosos de varios usuarios
    for _ in range(rng.randint(40, 70)):
        docs.append({"@timestamp": _t(base, rng.uniform(0, 7200)), "event_id": 4624, "accion": "logon",
                     "resultado": "exito", "user": rng.choice(USUARIOS), "src_ip": _ip_interna(rng),
                     "host": rng.choice(HOSTS), "mensaje": "An account was successfully logged on"})
    # el ataque: ráfaga de fallos contra 'victima' y luego un éxito
    intentos = rng.randint(60, 140)
    t0 = rng.uniform(1800, 5000)
    for i in range(intentos):
        docs.append({"@timestamp": _t(base, t0 + i * rng.uniform(0.5, 2.5)), "event_id": 4625, "accion": "logon",
                     "resultado": "fallo", "user": victima, "src_ip": atacante, "host": host,
                     "mensaje": "An account failed to log on"})
    t_exito = t0 + intentos * 1.6 + 3
    docs.append({"@timestamp": _t(base, t_exito), "event_id": 4624, "accion": "logon", "resultado": "exito",
                 "user": victima, "src_ip": atacante, "host": host, "mensaje": "An account was successfully logged on"})
    return {
        "id": "fuerza_bruta",
        "titulo": "Logins sospechosos en un servidor",
        "info": f"El SIEM recibió una avalancha de eventos de autenticación de Windows del host **{host}**. "
                "Algo no cuadra con una cuenta. Investiga en Kibana (índice lab-logs) y responde.",
        "pistas": ["Filtra por event_id: 4625 (login fallido) y agrupa por src_ip.",
                   "La IP con cientos de fallos es el atacante. ¿Logró entrar? Busca un 4624 con esa misma IP.",
                   "El usuario de ese 4624 exitoso desde la IP atacante es la cuenta comprometida."],
        "verdad": {"ip_atacante": atacante, "usuario": victima},
        "preguntas": [
            {"k": "ip_atacante", "q": "¿IP del atacante (la de los cientos de fallos)?", "tipo": "ip"},
            {"k": "usuario", "q": "¿Qué cuenta comprometió (el 4624 exitoso desde esa IP)?", "tipo": "texto"},
        ],
        "docs": docs,
    }


def esc_escaneo(rng: random.Random) -> dict:
    """Una IP toca muchísimos puertos distintos de un mismo host: port scan."""
    base = dt.datetime.utcnow() - dt.timedelta(hours=rng.randint(1, 15))
    atacante = _ip_externa(rng)
    objetivo = _ip_interna(rng)
    docs = []
    for _ in range(rng.randint(60, 100)):  # tráfico normal
        docs.append({"@timestamp": _t(base, rng.uniform(0, 3600)), "proto": "tcp", "accion": "conexion",
                     "src_ip": _ip_interna(rng), "dst_ip": _ip_interna(rng),
                     "dst_port": rng.choice([80, 443, 445, 3389, 22, 53]), "resultado": "permitido"})
    puertos = rng.sample(range(1, 10000), rng.randint(300, 600))  # el escaneo
    t0 = rng.uniform(600, 2500)
    for i, p in enumerate(puertos):
        docs.append({"@timestamp": _t(base, t0 + i * rng.uniform(0.02, 0.2)), "proto": "tcp", "accion": "conexion",
                     "src_ip": atacante, "dst_ip": objetivo, "dst_port": p,
                     "resultado": "rechazado" if rng.random() < 0.9 else "permitido"})
    return {
        "id": "escaneo",
        "titulo": "Barrido de puertos",
        "info": "El firewall registró un pico de conexiones rechazadas. Parece que alguien está mapeando un equipo. "
                "Encuentra quién escanea y a quién, en Kibana (índice lab-logs).",
        "pistas": ["Agrupa por src_ip y mira quién genera cientos de dst_port distintos en poco tiempo.",
                   "El dst_ip repetido de esas conexiones es el objetivo.",
                   "Un escaneo toca cientos de puertos; el tráfico normal solo unos pocos conocidos."],
        "verdad": {"ip_atacante": atacante, "ip_objetivo": objetivo},
        "preguntas": [
            {"k": "ip_atacante", "q": "¿IP que realiza el escaneo?", "tipo": "ip"},
            {"k": "ip_objetivo", "q": "¿IP del equipo escaneado?", "tipo": "ip"},
        ],
        "docs": docs,
    }


def esc_beacon(rng: random.Random) -> dict:
    """Un equipo interno se conecta a una IP externa en intervalos regulares: beacon C2."""
    base = dt.datetime.utcnow() - dt.timedelta(hours=rng.randint(3, 18))
    infectado = _ip_interna(rng)
    c2 = _ip_externa(rng)
    intervalo = rng.choice([30, 45, 60, 90, 120])
    docs = []
    for _ in range(rng.randint(80, 140)):  # navegación normal del equipo infectado y otros
        docs.append({"@timestamp": _t(base, rng.uniform(0, 14400)), "proto": "tcp", "accion": "conexion",
                     "src_ip": rng.choice([infectado, _ip_interna(rng)]), "dst_ip": _ip_externa(rng),
                     "dst_port": rng.choice([80, 443]), "bytes": rng.randint(800, 90000), "resultado": "permitido"})
    n = rng.randint(60, 110)  # el beacon: mismo destino, intervalo fijo, bytes pequeños y constantes
    t0 = rng.uniform(0, 1200)
    for i in range(n):
        docs.append({"@timestamp": _t(base, t0 + i * intervalo + rng.uniform(-1.5, 1.5)), "proto": "tcp",
                     "accion": "conexion", "src_ip": infectado, "dst_ip": c2, "dst_port": 443,
                     "bytes": rng.randint(180, 260), "resultado": "permitido"})
    return {
        "id": "beacon",
        "titulo": "Latido hacia afuera (C2)",
        "info": "Sospechamos que un equipo está infectado y 'llama a casa' a su servidor de control. "
                "Un beacon se delata por conectarse al MISMO destino una y otra vez en intervalos regulares. Cázalo en Kibana.",
        "pistas": ["Agrupa conexiones salientes por pareja src_ip + dst_ip y busca la que se repite decenas de veces.",
                   "El beacon manda muy pocos bytes (200 aprox) siempre, muy regular. La navegación normal varía mucho.",
                   "El src_ip es el equipo infectado; el dst_ip es el C2."],
        "verdad": {"ip_infectado": infectado, "ip_c2": c2},
        "preguntas": [
            {"k": "ip_infectado", "q": "¿IP del equipo interno infectado?", "tipo": "ip"},
            {"k": "ip_c2", "q": "¿IP del servidor C2 (destino del beacon)?", "tipo": "ip"},
        ],
        "docs": docs,
    }


def esc_exfil(rng: random.Random) -> dict:
    """Subida enorme de datos a una IP externa."""
    base = dt.datetime.utcnow() - dt.timedelta(hours=rng.randint(2, 12))
    interno = _ip_interna(rng)
    destino = _ip_externa(rng)
    total = 0
    docs = []
    for _ in range(rng.randint(80, 130)):  # tráfico normal (bytes modestos)
        docs.append({"@timestamp": _t(base, rng.uniform(0, 10800)), "proto": "tcp", "accion": "subida",
                     "src_ip": _ip_interna(rng), "dst_ip": _ip_externa(rng), "dst_port": 443,
                     "bytes": rng.randint(500, 120000), "resultado": "permitido"})
    n = rng.randint(15, 30)  # exfil: muchos MB al mismo destino
    t0 = rng.uniform(1000, 6000)
    for i in range(n):
        b = rng.randint(8_000_000, 30_000_000)
        total += b
        docs.append({"@timestamp": _t(base, t0 + i * rng.uniform(2, 10)), "proto": "tcp", "accion": "subida",
                     "src_ip": interno, "dst_ip": destino, "dst_port": 443, "bytes": b, "resultado": "permitido"})
    return {
        "id": "exfil",
        "titulo": "Fuga de datos",
        "info": "Alertaron por un volumen anormal de datos SALIENDO de la red. Encuentra qué equipo mandó cuánto y a dónde, en Kibana.",
        "pistas": ["Suma bytes por dst_ip de las subidas (accion: subida). Un destino concentra cientos de MB.",
                   "El src_ip de esas subidas gigantes es el equipo que filtró.",
                   "La navegación normal son KB o pocos MB; la exfil son decenas de MB por conexión."],
        "verdad": {"ip_interno": interno, "ip_destino": destino, "mb": round(total / 1_000_000)},
        "preguntas": [
            {"k": "ip_interno", "q": "¿IP del equipo interno que filtró los datos?", "tipo": "ip"},
            {"k": "ip_destino", "q": "¿IP externa que recibió los datos?", "tipo": "ip"},
            {"k": "mb", "q": "¿Aprox. cuántos MB se enviaron en total? (±15%)", "tipo": "num", "tol": 0.15},
        ],
        "docs": docs,
    }


def esc_web(rng: random.Random) -> dict:
    """Credential stuffing contra /login: muchos 401 y al final un 200."""
    base = dt.datetime.utcnow() - dt.timedelta(hours=rng.randint(1, 10))
    atacante = _ip_externa(rng)
    victima = rng.choice(USUARIOS)
    host = "SRV-WEB01"
    docs = []
    for _ in range(rng.randint(100, 180)):  # tráfico web normal
        docs.append({"@timestamp": _t(base, rng.uniform(0, 7200)), "proto": "http", "accion": "request",
                     "src_ip": _ip_interna(rng), "dst_ip": "10.0.0.10", "host": host,
                     "url": rng.choice(URLS), "status": rng.choice([200, 200, 200, 302, 404]), "user": rng.choice(USUARIOS)})
    intentos = rng.randint(50, 110)  # el ataque a /login
    t0 = rng.uniform(1200, 4000)
    for i in range(intentos):
        docs.append({"@timestamp": _t(base, t0 + i * rng.uniform(0.3, 1.2)), "proto": "http", "accion": "request",
                     "src_ip": atacante, "dst_ip": "10.0.0.10", "host": host, "url": "/login",
                     "status": 401, "user": rng.choice(USUARIOS)})
    docs.append({"@timestamp": _t(base, t0 + intentos * 0.8 + 2), "proto": "http", "accion": "request",
                 "src_ip": atacante, "dst_ip": "10.0.0.10", "host": host, "url": "/login", "status": 200, "user": victima})
    return {
        "id": "web",
        "titulo": "Ataque al login del portal",
        "info": f"El portal web **{host}** recibió un aluvión de intentos de inicio de sesión. "
                "Averigua si alguien logró entrar, desde qué IP y con qué usuario. Índice lab-logs en Kibana.",
        "pistas": ["Filtra url: \"/login\" y status: 401, agrupa por src_ip: una IP concentra decenas de fallos.",
                   "Busca un status: 200 en /login desde esa misma IP: ahí entró.",
                   "El 'user' de ese 200 es la cuenta con la que logró entrar."],
        "verdad": {"ip_atacante": atacante, "usuario": victima},
        "preguntas": [
            {"k": "ip_atacante", "q": "¿IP que atacó el login?", "tipo": "ip"},
            {"k": "usuario", "q": "¿Con qué usuario logró entrar (status 200)?", "tipo": "texto"},
        ],
        "docs": docs,
    }


ESCENARIOS = {
    "fuerza_bruta": esc_fuerza_bruta, "escaneo": esc_escaneo, "beacon": esc_beacon,
    "exfil": esc_exfil, "web": esc_web,
}
CATALOGO = [
    {"id": "fuerza_bruta", "titulo": "Fuerza bruta de credenciales", "nivel": "Básico", "ic": "🔑"},
    {"id": "web", "titulo": "Ataque al login web", "nivel": "Básico", "ic": "🌐"},
    {"id": "escaneo", "titulo": "Barrido de puertos", "nivel": "Intermedio", "ic": "📡"},
    {"id": "beacon", "titulo": "Beacon C2", "nivel": "Avanzado", "ic": "📶"},
    {"id": "exfil", "titulo": "Fuga de datos", "nivel": "Avanzado", "ic": "📤"},
]


def generar(escenario: str, semilla: int | None = None) -> dict:
    rng = random.Random(semilla)
    fn = ESCENARIOS.get(escenario)
    if not fn:
        raise ValueError("escenario desconocido")
    e = fn(rng)
    rng.shuffle(e["docs"])
    return e


def sembrar(escenario: str, semilla: int | None = None) -> dict:
    """Genera el escenario, lo carga en Elastic y devuelve lo que ve el alumno (sin la verdad)."""
    e = generar(escenario, semilla)
    reiniciar_indice()
    code, out = _bulk(e["docs"])
    if code not in (200, 201):
        raise RuntimeError(f"No pude cargar los logs en Elastic ({code}): {out[:200]}")
    return {"id": e["id"], "titulo": e["titulo"], "info": e["info"], "preguntas": e["preguntas"],
            "n": len(e["docs"]), "verdad": e["verdad"], "pistas": e["pistas"]}


def calificar(verdad: dict, preguntas: list[dict], respuestas: dict) -> dict:
    """Compara respuestas del alumno contra la verdad sembrada."""
    detalle = []
    bien = 0
    for p in preguntas:
        k = p["k"]
        esperado = verdad.get(k)
        dado = str(respuestas.get(k, "")).strip()
        ok = False
        if p.get("tipo") == "num":
            try:
                v = float(dado.replace(",", "").replace("MB", "").strip())
                tol = p.get("tol", 0.15)
                ok = abs(v - float(esperado)) <= abs(float(esperado)) * tol
            except ValueError:
                ok = False
        elif p.get("tipo") == "ip":
            ok = dado == str(esperado)
        else:
            ok = dado.lower() == str(esperado).lower()
        bien += ok
        detalle.append({"k": k, "ok": ok, "esperado": esperado})
    return {"ok": bien == len(preguntas), "bien": bien, "total": len(preguntas), "detalle": detalle}


# ---------------------------------------------------------------- importar datos reales (carpeta host → Elastic)
# No usamos carpeta compartida de VirtualBox (la cloud image no trae Guest Additions): NetLab lee la carpeta en Windows
# y manda los eventos a Elasticsearch por el puerto reenviado. Van a su propio índice para que los casos no los borren.
INDICE_IMP = "importados"
EXT_IMP = (".pcap", ".pcapng", ".cap", ".log", ".txt", ".json", ".ndjson", ".jsonl", ".csv")
MAX_DOCS_ARCHIVO = 50000
_RE_IP = None


def _asegurar_indice_imp() -> None:
    code, _ = _pedir("/" + INDICE_IMP)
    if code == 200:
        return
    mapping = json.dumps({
        "settings": {"index.mapping.total_fields.limit": 5000},
        "mappings": {"dynamic": True, "properties": {
            "@timestamp": {"type": "date"}, "src_ip": {"type": "ip"}, "dst_ip": {"type": "ip"},
            "src_port": {"type": "integer"}, "dst_port": {"type": "integer"}, "proto": {"type": "keyword"},
            "bytes": {"type": "long"}, "host": {"type": "keyword"}, "url": {"type": "keyword"},
            "archivo": {"type": "keyword"}, "mensaje": {"type": "text"},
        }}}).encode("utf-8")
    _pedir("/" + INDICE_IMP, mapping, "PUT")
    dv = json.dumps({"data_view": {"title": INDICE_IMP, "name": "importados", "timeFieldName": "@timestamp"}}).encode("utf-8")
    _pedir("/api/data_views/data_view", dv, "POST", base=KIBANA, timeout=20)


def _bulk_imp(docs: list[dict]) -> tuple[int, int]:
    """Manda en lotes; devuelve (cargados, con_error)."""
    ok = mal = 0
    for i in range(0, len(docs), 2000):
        lote = docs[i:i + 2000]
        cuerpo = "".join(json.dumps({"index": {"_index": INDICE_IMP}}) + "\n" + json.dumps(d, ensure_ascii=False) + "\n"
                         for d in lote).encode("utf-8")
        code, out = _pedir("/_bulk", cuerpo, "POST", timeout=120)
        if code not in (200, 201):
            mal += len(lote)
            continue
        try:
            items = json.loads(out).get("items", [])
            e = sum(1 for it in items if (it.get("index") or {}).get("error"))
        except ValueError:
            e = 0
        ok += len(lote) - e
        mal += e
    _pedir("/" + INDICE_IMP + "/_refresh", metodo="POST")
    return ok, mal


def _ip_o_nada(v: str) -> str | None:
    try:
        return str(ipaddress.ip_address((v or "").strip()))
    except ValueError:
        return None


def _docs_pcap(ruta: str, tshark: str) -> list[dict]:
    import subprocess
    campos = ["frame.time_epoch", "ip.src", "ip.dst", "ipv6.src", "ipv6.dst", "tcp.srcport", "udp.srcport",
              "tcp.dstport", "udp.dstport", "_ws.col.Protocol", "frame.len", "dns.qry.name", "http.host",
              "http.request.uri", "tls.handshake.extensions_server_name", "_ws.col.Info"]
    cmd = [tshark, "-r", ruta, "-n", "-c", str(MAX_DOCS_ARCHIVO), "-T", "fields", "-E", "separator=/t", "-E", "occurrence=f"]
    for c in campos:
        cmd += ["-e", c]
    extra = {"creationflags": 0x08000000} if __import__("os").name == "nt" else {}
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, **extra)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError("tshark no pudo leer la captura: " + (r.stderr or "")[-300:])
    nombre = __import__("os").path.basename(ruta)
    docs = []
    for linea in r.stdout.splitlines():
        v = linea.split("\t") + [""] * len(campos)
        try:
            ts = dt.datetime.fromtimestamp(float(v[0]), dt.timezone.utc).isoformat()
        except ValueError:
            continue
        d = {"@timestamp": ts, "archivo": nombre, "proto": v[9] or None, "mensaje": v[15] or None,
             "src_ip": _ip_o_nada(v[1] or v[3]), "dst_ip": _ip_o_nada(v[2] or v[4])}
        for k, a, b in (("src_port", 5, 6), ("dst_port", 7, 8)):
            if (v[a] or v[b]).isdigit():
                d[k] = int(v[a] or v[b])
        if v[10].isdigit():
            d["bytes"] = int(v[10])
        h = v[12] or v[14] or v[11]
        if h:
            d["host"] = h
        if v[13]:
            d["url"] = v[13]
        docs.append({k: x for k, x in d.items() if x is not None})
    return docs


def _docs_texto(ruta: str) -> list[dict]:
    import csv
    import os
    import re
    global _RE_IP
    _RE_IP = _RE_IP or re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    nombre, ext = os.path.basename(ruta), os.path.splitext(ruta)[1].lower()
    ahora = dt.datetime.now(dt.timezone.utc).isoformat()
    docs: list[dict] = []
    with open(ruta, encoding="utf-8", errors="replace", newline="") as f:
        if ext == ".csv":
            for fila in csv.DictReader(f):
                d = {k.strip(): v for k, v in fila.items() if k}
                d.setdefault("@timestamp", d.pop("timestamp", None) or ahora)
                d["archivo"] = nombre
                docs.append(d)
                if len(docs) >= MAX_DOCS_ARCHIVO:
                    break
        elif ext in (".json", ".ndjson", ".jsonl"):
            texto = f.read()
            try:  # un arreglo JSON completo
                datos = json.loads(texto)
                filas = datos if isinstance(datos, list) else [datos]
            except ValueError:  # NDJSON: un objeto por línea
                filas = []
                for l in texto.splitlines():
                    try:
                        filas.append(json.loads(l))
                    except ValueError:
                        pass
            for d in filas[:MAX_DOCS_ARCHIVO]:
                if isinstance(d, dict):
                    d = dict(d)
                    d.setdefault("@timestamp", d.pop("timestamp", None) or ahora)
                    d["archivo"] = nombre
                    docs.append(d)
        else:  # .log / .txt: una línea = un evento
            for l in f:
                l = l.rstrip("\r\n")
                if not l.strip():
                    continue
                d = {"@timestamp": ahora, "mensaje": l, "archivo": nombre}
                ips = _RE_IP.findall(l)
                if ips and _ip_o_nada(ips[0]):
                    d["src_ip"] = ips[0]
                if len(ips) > 1 and _ip_o_nada(ips[1]):
                    d["dst_ip"] = ips[1]
                docs.append(d)
                if len(docs) >= MAX_DOCS_ARCHIVO:
                    break
    return docs


def listar_importables(carpeta: str) -> list[dict]:
    import os
    if not os.path.isdir(carpeta):
        return []
    out = []
    for n in sorted(os.listdir(carpeta)):
        p = os.path.join(carpeta, n)
        if os.path.isfile(p) and n.lower().endswith(EXT_IMP):
            out.append({"nombre": n, "mb": round(os.path.getsize(p) / 1024 ** 2, 2)})
    return out


def importar(carpeta: str, nombres: list[str], tshark: str | None, progreso=lambda *_: None) -> dict:
    """Carga en Elasticsearch (índice 'importados') los archivos elegidos de la carpeta de importación."""
    import os
    if not es_vivo():
        raise RuntimeError("Elasticsearch no responde: enciende la VM del SIEM y espera a que caliente.")
    _asegurar_indice_imp()
    rep = []
    validos = {f["nombre"] for f in listar_importables(carpeta)}
    for n in nombres:
        if n not in validos:  # solo archivos que de verdad están en la carpeta (nada de rutas)
            continue
        ruta = os.path.join(carpeta, n)
        progreso(f"Leyendo {n}…")
        try:
            if n.lower().endswith((".pcap", ".pcapng", ".cap")):
                if not tshark:
                    raise RuntimeError("No encontré tshark para leer capturas.")
                docs = _docs_pcap(ruta, tshark)
            else:
                docs = _docs_texto(ruta)
            progreso(f"Cargando {len(docs)} eventos de {n} en Elasticsearch…")
            ok, mal = _bulk_imp(docs)
            rep.append({"archivo": n, "eventos": ok, "errores": mal})
        except Exception as e:  # noqa: BLE001
            rep.append({"archivo": n, "eventos": 0, "errores": 0, "fallo": str(e)[:200]})
    return {"reporte": rep, "indice": INDICE_IMP}


def borrar_importados() -> None:
    _pedir("/" + INDICE_IMP, metodo="DELETE")
