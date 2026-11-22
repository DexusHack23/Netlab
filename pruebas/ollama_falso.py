"""Ollama simulado para probar la app sin GPU. Uso: python -m pruebas.ollama_falso"""
import copy
import re
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True
from core.generador import _EJEMPLO  # noqa: E402

LLAMADAS = {"practica": 0}


def practica():
    LLAMADAS["practica"] += 1
    p = copy.deepcopy(_EJEMPLO)
    p["tareas"] = ["En SW1 crea la VLAN 10 (VENTAS) y la 20 (CONTA).", "Asigna Fa0/1 a la VLAN 10 y Fa0/2 a la 20.",
                   "Configura Gi0/1 de SW1 como troncal.", "Enciende Gi0/0 de R1 y crea las subinterfaces .10 y .20.",
                   "Configura las PCs y comprueba que PC1 haga ping a PC2."]
    p["pistas"] = ["El puerto del switch hacia el router debe llevar varias VLANs.", "Cada subinterfaz necesita encapsulation dot1Q."]
    if LLAMADAS["practica"] % 2 == 1:  # primera versión con un error para probar la reparación
        p["solucion"][1]["config"] = p["solucion"][1]["config"].replace(" no shutdown\n", "")
    return p


EXAMEN = {"titulo": "VLANs y troncales", "preguntas": [
    {"tipo": "opcion", "enunciado": "¿Qué comando muestra las VLANs y sus puertos de acceso?",
     "opciones": ["show vlan brief", "show interfaces trunk", "show ip route", "show mac address-table"],
     "correcta": 0, "explicacion": "show vlan brief lista VLANs y puertos asignados.", "subtema": "vlan"},
    {"tipo": "opcion", "enunciado": "¿Qué protocolo etiqueta tramas en un enlace troncal estándar?",
     "opciones": ["802.1Q", "ISL", "802.3ad", "802.1D"], "correcta": 0,
     "explicacion": "802.1Q es el estándar IEEE de etiquetado.", "subtema": "troncal"},
    {"tipo": "opcion", "enunciado": "¿Cuál es la VLAN nativa por defecto?", "opciones": ["1", "10", "99", "1002"],
     "correcta": 0, "explicacion": "Por defecto la VLAN nativa es la 1.", "subtema": "troncal"},
    {"tipo": "comando", "enunciado": "Pon la interfaz actual en modo acceso.",
     "respuestas_validas": ["switchport mode access"], "explicacion": "Fija el puerto como acceso.", "subtema": "vlan"},
    {"tipo": "opcion", "enunciado": "Pregunta con clave mala", "opciones": ["a", "b", "c", "d"], "correcta": 2,
     "explicacion": "x", "subtema": "x"},
]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, d):
        b = json.dumps(d, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/api/tags":
            return self._j({"models": [{"name": n} for n in ["gpt-oss:20b", "qwen3:4b-instruct", "qwen3:30b", "gemma4:12b", "qwen3-vl:8b", "nomic-embed-text:latest"]]})
        if self.path == "/api/ps":
            return self._j({"models": []})
        self._j({})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/generate":
            return self._j({"done": True})
        if self.path == "/api/embed":  # vectores de juguete: bolsa de palabras con hash
            import hashlib
            vecs = []
            for t in body["input"]:
                v = [0.0] * 64
                for w in t.lower().split():
                    v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
                vecs.append(v)
            return self._j({"embeddings": vecs})
        if any(m.get("images") for m in body.get("messages", [])):
            return self._j({"message": {"content": "R1#show ip interface brief\nInterface  IP-Address  OK? Method Status  Protocol"}})
        props = (body.get("format") or {}).get("properties", {}) if isinstance(body.get("format"), dict) else {}
        if "accion" in props:
            ops = re.findall(r"'([a-z_]+)'", body["messages"][-1]["content"].split("Opciones:")[1].split("\n")[0])
            out = {"accion": ops[0] if ops else "", "mensaje": "Tu firewall no me asusta."}
        elif "secciones" in props:
            out = {"titulo": "VLANs y troncales", "intro": "Una VLAN separa un switch en varias redes lógicas.",
                   "secciones": [{"titulo": "Qué es", "texto": "Una VLAN es un dominio de difusión. Cada puerto pertenece a una."},
                                 {"titulo": "Troncales", "texto": "Un troncal 802.1Q lleva varias VLANs etiquetadas.\nLa nativa va sin etiqueta."}],
                   "comandos": [{"comando": "SW1(config)# vlan 10", "que_hace": "Crea la VLAN 10"},
                                {"comando": "switchport mode trunk", "que_hace": "Hace troncal el puerto"}],
                   "puntos_clave": ["Cada VLAN es una subred."], "errores_comunes": ["Olvidar permitir la VLAN en el troncal."]}
        elif "configuracion" in props:
            LLAMADAS["topo"] = LLAMADAS.get("topo", 0) + 1
            t = copy.deepcopy(_EJEMPLO)
            t["descripcion"] = "Router-on-a-stick con dos VLANs."
            t["configuracion"] = t.pop("solucion")
            t["notas"] = ["Haz ping de PC1 a PC2.", "Revisa show ip interface brief en R1."]
            if LLAMADAS["topo"] % 2 == 1:  # primera versión con un puerto inexistente para probar la reparación
                t["enlaces"][1]["puerto_b"] = "FastEthernet0/30"
            out = t
        elif "dispositivos" in props:
            out = practica()
        elif "preguntas" in props:
            out = copy.deepcopy(EXAMEN)
        elif "respuestas" in props:
            txt = body["messages"][-1]["content"]
            res = []
            buenas = ["show vlan brief", "802.1Q", "1"]
            for k, bloque in enumerate(txt.split("\n\n"), 1):
                ops = [l.strip() for l in bloque.splitlines()[1:]]
                letra = next((o[0] for o in ops if o.split(") ", 1)[-1] in buenas), "A")
                res.append({"n": k, "correctas": [letra]})
            out = {"respuestas": res}
        elif "comandos" in props:
            out = {"comandos": [{"n": 1, "correcto": True}]}
        elif "correcta" in props:
            out = {"correcta": False, "motivo": "Ese comando no cambia el modo del puerto."}
            return self._j({"message": {"content": json.dumps(out)}})
        else:
            return self._j({"message": {"content": "- **Gi0/0 de R1** sigue apagada: usa `no shutdown`.\n- Te faltó pegar `show vlan brief` en SW1."}})
        self._j({"message": {"content": json.dumps(out, ensure_ascii=False)}})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 11434), H).serve_forever()
