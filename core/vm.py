"""Laboratorio Linux REAL: una VM de Ubuntu Server en VirtualBox que NetLab crea, enciende, prepara y califica.

- La imagen oficial (cloud image .ova de Canonical) se importa una sola vez como "NetLab-Ubuntu".
- cloud-init toma su configuración de NetLab por HTTP (SMBIOS serial "ds=nocloud;s=http://10.0.2.2:PUERTO/ci/"),
  así no hace falta crear ISOs: usuario `alumno`, contraseña `netlab`, y la llave SSH de NetLab.
- NetLab entra por SSH (puerto 2222 del host → 22 de la VM) para preparar cada misión y revisarla.
- Al terminar la primera preparación se toma la instantánea "limpio": "Reiniciar máquina" vuelve a ella.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time

NOMBRE = "NetLab-Ubuntu"
OVA = "ubuntu-24.04-server-cloudimg-amd64.ova"
PUERTO_SSH = 2222
USUARIO = "alumno"
CLAVE = "netlab"
SNAP = "limpio"
_SIN_VENTANA = {"creationflags": 0x08000000} if os.name == "nt" else {}

CI_LOG: list[str] = []  # quién pidió la configuración de cloud-init (diagnóstico)
CARPETA = ""  # la pone app.py (MIS CARPETAS\Lab CCNA\vms)
PUERTO_NETLAB = 8765


def configurar(carpeta: str, puerto: int) -> None:
    global CARPETA, PUERTO_NETLAB
    CARPETA, PUERTO_NETLAB = carpeta, puerto


def llave() -> str:
    return os.path.join(CARPETA, "netlab_ed25519")


# ---------------------------------------------------------------- VirtualBox
def vboxmanage() -> str | None:
    for c in (shutil.which("VBoxManage"), os.path.join(os.environ.get("VBOX_MSI_INSTALL_PATH", ""), "VBoxManage.exe"),
              r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"):
        if c and os.path.isfile(c):
            return c
    return None


def vbox(*args, timeout: int = 120) -> tuple[int, str]:
    vb = vboxmanage()
    if not vb:
        raise RuntimeError("No encontré VirtualBox (VBoxManage.exe).")
    r = subprocess.run([vb, *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, **_SIN_VENTANA)
    return r.returncode, (r.stdout + r.stderr).strip()


def info() -> dict:
    code, out = vbox("showvminfo", NOMBRE, "--machinereadable", timeout=30)
    if code != 0:
        return {}
    return {m.group(1).strip('"'): m.group(2).strip('"') for m in re.finditer(r'^("?[^=]+"?)=(.*)$', out, re.M)}


def existe() -> bool:
    try:
        return bool(info())
    except Exception:  # noqa: BLE001
        return False


def corriendo() -> bool:
    i = info()
    return i.get("VMState") in ("running", "starting")


def tiene_snapshot() -> bool:
    code, out = vbox("snapshot", NOMBRE, "list", "--machinereadable", timeout=30)
    return code == 0 and f'="{SNAP}"' in out


# ---------------------------------------------------------------- SSH
def _ssh_base() -> list[str]:
    ssh = shutil.which("ssh") or r"C:\Windows\System32\OpenSSH\ssh.exe"
    nul = "NUL" if os.name == "nt" else "/dev/null"
    return [ssh, "-i", llave(), "-p", str(PUERTO_SSH), "-o", "StrictHostKeyChecking=no", "-o", f"UserKnownHostsFile={nul}",
            "-o", "LogLevel=ERROR", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", f"{USUARIO}@127.0.0.1"]


def ssh(script: str, timeout: int = 120, root: bool = True) -> tuple[int, str]:
    """Corre un script de bash en la VM (como root por sudo). Devuelve (código, salida)."""
    cmd = _ssh_base() + (["sudo", "bash", "-s"] if root else ["bash", "-s"])
    try:
        # en bytes: en modo texto Windows convertiría cada \n en \r\n y bash no entendería el script
        r = subprocess.run(cmd, input=script.replace("\r\n", "\n").encode("utf-8"), capture_output=True, timeout=timeout, **_SIN_VENTANA)
    except subprocess.TimeoutExpired:
        return 124, "tiempo agotado"
    return r.returncode, (r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")).replace("\r\n", "\n").strip()


def ssh_ok() -> bool:
    code, out = ssh("echo ok", timeout=15, root=False)
    return code == 0 and out.endswith("ok")


def esperar_ssh(progreso, limite: int = 420) -> None:
    t0 = time.time()
    while time.time() - t0 < limite:
        if ssh_ok():
            return
        progreso(f"Esperando a que Ubuntu arranque… ({int(time.time() - t0)} s)")
        time.sleep(5)
    raise RuntimeError("La VM no respondió por SSH. Revisa VirtualBox (¿Hyper-V o la virtualización desactivada en el BIOS?).")


def abrir_terminal() -> None:
    """Abre una terminal real de Windows conectada a la VM."""
    base = _ssh_base()  # igual que la de NetLab pero interactiva (sin BatchMode)
    limpio, i = [], 0
    while i < len(base):
        if base[i] == "-o" and i + 1 < len(base) and base[i + 1] == "BatchMode=yes":
            i += 2
            continue
        limpio.append(base[i])
        i += 1
    wt = shutil.which("wt.exe")
    if wt:
        subprocess.Popen([wt, "new-tab", "--title", "NetLab Linux", *limpio], **_SIN_VENTANA)
    else:
        subprocess.Popen(["cmd", "/c", "start", "NetLab Linux", *limpio])


# ---------------------------------------------------------------- cloud-init (lo sirve NetLab)
def _pub() -> str:
    try:
        with open(llave() + ".pub", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def cloud_init(archivo: str) -> str | None:
    if archivo == "meta-data":
        return "instance-id: netlab-ubuntu-1\nlocal-hostname: netlab\n"
    if archivo == "vendor-data":
        return ""
    if archivo == "user-data":
        return f"""#cloud-config
hostname: netlab
ssh_pwauth: true
users:
  - name: {USUARIO}
    gecos: Alumno NetLab
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    groups: [adm, sudo, systemd-journal]
    lock_passwd: false
    plain_text_passwd: {CLAVE}
    ssh_authorized_keys:
      - {_pub()}
package_update: false
package_upgrade: false
runcmd:
  - systemctl disable --now unattended-upgrades apt-daily.timer apt-daily-upgrade.timer || true
  - mkdir -p /opt/netlab && touch /opt/netlab/listo
"""
    return None


# ---------------------------------------------------------------- crear / encender / apagar
def _llave_nueva() -> None:
    if os.path.isfile(llave()):
        return
    kg = shutil.which("ssh-keygen") or r"C:\Windows\System32\OpenSSH\ssh-keygen.exe"
    r = subprocess.run([kg, "-q", "-t", "ed25519", "-N", "", "-C", "netlab", "-f", llave()], capture_output=True, text=True,
                       timeout=30, **_SIN_VENTANA)
    if r.returncode != 0:
        raise RuntimeError("No pude crear la llave SSH: " + (r.stderr or r.stdout)[:200])
    if os.name == "nt":  # ssh de Windows exige que solo tú puedas leer la llave privada
        usuario = os.environ.get("USERNAME", "")
        subprocess.run(["icacls", llave(), "/inheritance:r", "/grant:r", f"{usuario}:F"], capture_output=True, **_SIN_VENTANA)


def crear(progreso) -> None:
    ova = os.path.join(CARPETA, OVA)
    if not os.path.isfile(ova):
        raise RuntimeError("Falta la imagen de Ubuntu (.ova). Bájala primero.")
    _llave_nueva()
    if not existe():
        progreso("Importando Ubuntu en VirtualBox (1-2 min)…")
        code, out = vbox("import", ova, "--vsys", "0", "--vmname", NOMBRE, "--basefolder", CARPETA, "--memory", "2048",
                         "--cpus", "2", timeout=900)
        if code != 0:
            raise RuntimeError("VirtualBox no pudo importar la imagen: " + out[-400:])
        i = info()
        # disco más grande para los labs (la imagen trae ~3.5 GB): VMDK → VDI de 12 GB
        disco = next(((k, v) for k, v in i.items() if re.match(r".+-\d+-\d+$", k) and v.lower().endswith((".vmdk", ".vdi"))), None)
        if disco:
            progreso("Agrandando el disco a 12 GB…")
            ctl, puerto, disp = disco[0].rsplit("-", 2)
            vdi = os.path.join(os.path.dirname(disco[1]), "netlab-disco.vdi")
            if not os.path.isfile(vdi):
                code, out = vbox("clonemedium", "disk", disco[1], vdi, "--format", "VDI", timeout=900)
                if code == 0:
                    vbox("modifymedium", "disk", vdi, "--resize", "12288", timeout=300)
                    vbox("storageattach", NOMBRE, "--storagectl", ctl, "--port", puerto, "--device", disp, "--type", "hdd",
                         "--medium", vdi, timeout=120)
                    vbox("closemedium", "disk", disco[1], "--delete", timeout=120)
        progreso("Configurando red, consola y cloud-init…")
        vbox("modifyvm", NOMBRE, "--nic1", "nat", "--natpf1", f"ssh,tcp,127.0.0.1,{PUERTO_SSH},,22",
             "--uart1", "0x3F8", "4", "--uartmode1", "file", os.path.join(CARPETA, "consola.log"), "--audio-enabled", "off")

        vbox("setextradata", NOMBRE, "VBoxInternal/Devices/pcbios/0/Config/DmiSystemSerial",
             f"ds=nocloud;s=http://10.0.2.2:{PUERTO_NETLAB}/ci/")
    encender(progreso)
    progreso("Esperando a que cloud-init termine…")
    t0 = time.time()
    while time.time() - t0 < 300:
        code, _ = ssh("test -f /opt/netlab/listo && cloud-init status --wait >/dev/null 2>&1; test -f /opt/netlab/listo", timeout=320)
        if code == 0:
            break
        time.sleep(5)
    if not tiene_snapshot():
        progreso("Guardando la instantánea 'limpio' para poder reiniciar la máquina…")
        apagar()
        vbox("snapshot", NOMBRE, "take", SNAP, timeout=600)
        encender(progreso)


# recursos de la VM: 2 GB / 1 núcleo basta para los labs de Linux; el SIEM (Elasticsearch + Kibana) necesita más
RAM_MB, CPUS = 2048, 1
RAM_SIEM_MB, CPUS_SIEM = 16384, 1
CPUS_SIEM_RAPIDO = 6  # sin Hyper-V (VT-x nativo) la VM aguanta varios núcleos sin congelarse

_MODO: dict = {}


def modo_hipervisor() -> str:
    """'rapido' = Hyper-V apagado (VirtualBox usa VT-x nativo); 'nem' = Hyper-V encendido (modo NEM, lento).
    Solo cambia al reiniciar Windows, así que se pregunta una vez por proceso."""
    if "m" in _MODO:
        return _MODO["m"]
    m = "desconocido"
    if os.name == "nt":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "(Get-CimInstance Win32_ComputerSystem).HypervisorPresent"],
                               capture_output=True, text=True, timeout=30, **_SIN_VENTANA)
            v = (r.stdout or "").strip().lower()
            m = "nem" if v == "true" else "rapido" if v == "false" else "desconocido"
        except Exception:  # noqa: BLE001
            pass
    _MODO["m"] = m
    return m


def cpus_siem() -> int:
    """Núcleos para la VM del SIEM: 4 en modo rápido; 1 bajo Hyper-V (con 2 la VM se congela por soft-lockups NEM)."""
    return CPUS_SIEM_RAPIDO if modo_hipervisor() == "rapido" else CPUS_SIEM


def _marca(nombre: str) -> str:
    return os.path.join(CARPETA, nombre) if CARPETA else nombre


def _modo_siem() -> bool:
    """¿La VM debe arrancar con recursos de SIEM? (instalado ya, o instalándose ahora). Basado en archivos-marca (robusto)."""
    return os.path.isfile(_marca("siem.ok")) or os.path.isfile(_marca("siem.provisionando"))


def _siem_preparado() -> bool:
    """¿Esta VM ya tiene el SIEM instalado y horneado en la instantánea?"""
    return os.path.isfile(_marca("siem.ok"))


def _natpf_idempotente(nombre: str, hostport: int, guestport: int) -> None:
    """Asegura una regla de reenvío de puerto (host→VM) sin duplicar: borra la previa (si hay) y la agrega. VM apagada."""
    vbox("modifyvm", NOMBRE, "--natpf1", "delete", nombre, timeout=30)  # si no existe, error inofensivo
    vbox("modifyvm", NOMBRE, "--natpf1", f"{nombre},tcp,127.0.0.1,{hostport},,{guestport}", timeout=30)


REENVIOS_LAB = (("lab_dvwa", 4280, 4280), ("lab_juice", 4300, 3000), ("lab_webgoat", 4290, 8080))


def reenvios_lab_en_caliente() -> None:
    """Agrega los reenvíos del laboratorio con la VM encendida (controlvm). Con la VM apagada lo hace _asegurar_nat."""
    for n, h, g in REENVIOS_LAB:
        vbox("controlvm", NOMBRE, "natpf1", "delete", n, timeout=30)  # si no existe, error inofensivo
        vbox("controlvm", NOMBRE, "natpf1", f"{n},tcp,127.0.0.1,{h},,{g}", timeout=30)


def _asegurar_nat() -> None:
    """VirtualBox 7 ya no deja que la VM vea el localhost del host por la NAT; cloud-init lo necesita para hablar con NetLab.
    También fija RAM/núcleos y reenvíos de puertos del SIEM. Se llama con la VM apagada (antes de arrancar)."""
    siem = _modo_siem()
    for args in (("modifyvm", NOMBRE, "--nat-localhostreachable1=on"),
                 # Hyper-V activo → VirtualBox en modo NEM. 1 núcleo evita soft lockups en los labs ligeros;
                 # el SIEM necesita 2 núcleos y 6 GB o Elasticsearch ahoga la VM (OOM y se cae el SSH).
                 ("modifyvm", NOMBRE, "--cpus", str(cpus_siem() if siem else CPUS)),
                 ("modifyvm", NOMBRE, "--memory", str(RAM_SIEM_MB if siem else RAM_MB)),
                 ("setextradata", NOMBRE, "VBoxInternal/Devices/e1000/0/LUN#0/Config/LocalhostReachable", "1")):
        code, out = vbox(*args, timeout=60)
        CI_LOG.append(f"{' '.join(args[:1] + args[2:])} → {code} {out[-160:]}")
    # puertos del SIEM: Elasticsearch (9200) y Kibana (5601), para que el host y el navegador los alcancen
    _natpf_idempotente("es", 9200, 9200)
    _natpf_idempotente("kibana", 5601, 5601)
    # laboratorio Docker (DVWA y Juice Shop): solo el localhost de Windows los alcanza
    for n, h, g in REENVIOS_LAB:
        _natpf_idempotente(n, h, g)


def _arrancar(progreso) -> None:
    _asegurar_nat()
    progreso("Encendiendo la máquina Ubuntu…")
    code, out = vbox("startvm", NOMBRE, "--type", "headless", timeout=180)
    if code != 0:
        raise RuntimeError("No arrancó la VM: " + out[-400:])


SNAP_CALIENTE = "caliente"
_LOCK = threading.RLock()  # que el calentado automático y un clic en "Encender" no arranquen la VM dos veces


def _leer_marca(nombre: str) -> str:
    try:
        with open(_marca(nombre), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _escribir_marca(nombre: str, valor: str) -> None:
    try:
        with open(_marca(nombre), "w", encoding="utf-8") as f:
            f.write(valor)
    except OSError:
        pass


def suspender() -> bool:
    """Guarda el estado de la VM (savestate) para reanudarla al instante la próxima vez: Elasticsearch y Kibana
    siguen 'vivos' congelados, así no hay que esperar a que calienten. Libera la RAM (se vuelca a disco).
    Anota el modo del hipervisor: un estado guardado bajo Hyper-V no sirve en modo rápido (y al revés)."""
    with _LOCK:
        if not corriendo():
            return False
        code, out = vbox("controlvm", NOMBRE, "savestate", timeout=300)
        CI_LOG.append(f"savestate → {code} {out[-120:]}")
        if code == 0:
            _escribir_marca("estado.modo", modo_hipervisor())
        return code == 0


def tiene_caliente() -> bool:
    code, out = vbox("snapshot", NOMBRE, "list", "--machinereadable", timeout=30)
    return code == 0 and f'="{SNAP_CALIENTE}"' in out


def caliente_valida() -> bool:
    """¿Hay instantánea en caliente tomada en el MISMO modo del hipervisor que ahora?"""
    return _leer_marca("caliente.modo") == modo_hipervisor() and tiene_caliente()


def tomar_caliente(progreso=lambda *_: None) -> None:
    """Instantánea EN CALIENTE (con la RAM): Elasticsearch y Kibana quedan vivos dentro de ella. Sobrevive a reiniciar
    Windows, a diferencia de un estado guardado que se descarta. Ocupa en disco ~lo mismo que la RAM de la VM."""
    with _LOCK:
        if not corriendo():
            raise RuntimeError("La VM tiene que estar encendida y con el SIEM listo para tomar la instantánea en caliente.")
        libre = espacio()["libre_gb"]
        if libre < RAM_SIEM_MB / 1024 + 4:
            raise RuntimeError(f"Poco espacio en disco ({libre} GB libres): la instantánea en caliente necesita ~{RAM_SIEM_MB // 1024 + 4} GB.")
        if tiene_caliente():
            progreso("Borrando la instantánea en caliente anterior…")
            vbox("snapshot", NOMBRE, "delete", SNAP_CALIENTE, timeout=900)
        progreso("Tomando la instantánea en caliente (vuelca la RAM a disco; 1-3 min)…")
        code, out = vbox("snapshot", NOMBRE, "take", SNAP_CALIENTE, "--live", timeout=1200)
        if code != 0:
            raise RuntimeError("No pude tomar la instantánea en caliente: " + out[-300:])
        _escribir_marca("caliente.modo", modo_hipervisor())


def borrar_caliente(progreso=lambda *_: None) -> None:
    with _LOCK:
        if tiene_caliente():
            progreso("Borrando la instantánea en caliente…")
            vbox("snapshot", NOMBRE, "delete", SNAP_CALIENTE, timeout=900)
        try:
            os.remove(_marca("caliente.modo"))
        except OSError:
            pass


def descartar_estado() -> bool:
    """Borra el estado guardado (.sav) para liberar disco; la próxima vez la VM arranca desde la instantánea en caliente
    (si hay) o en frío."""
    with _LOCK:
        if (info().get("VMState") or "").lower() != "saved":
            return False
        code, _ = vbox("discardstate", NOMBRE, timeout=120)
        return code == 0


def encender(progreso) -> None:
    with _LOCK:
        _encender(progreso)


def _encender(progreso) -> None:
    st = (info().get("VMState") or "").lower()
    if st == "saved" and _leer_marca("estado.modo") not in ("", modo_hipervisor()):
        # el estado se guardó con el otro hipervisor (cambiaste Hyper-V): no reanuda, mejor ni intentarlo
        progreso("El estado guardado es del otro modo de Hyper-V; lo descarto…")
        vbox("discardstate", NOMBRE, timeout=120)
        time.sleep(2)
        st = "poweroff"
    if st in ("poweroff", "aborted") and _siem_preparado() and caliente_valida():
        # sin estado guardado (p. ej. lo descartaste): volver a la instantánea en caliente = SIEM vivo en segundos
        progreso("Restaurando la instantánea en caliente (Elastic y Kibana ya vivos)…")
        code, out = vbox("snapshot", NOMBRE, "restore", SNAP_CALIENTE, timeout=600)
        CI_LOG.append(f"restore caliente → {code} {out[-120:]}")
        st = (info().get("VMState") or "").lower()
    if st == "saved":  # reanudar el estado suspendido: Elastic/Kibana vuelven al instante
        progreso("Reanudando la VM (Elastic y Kibana siguen vivos)…")
        code, out = vbox("startvm", NOMBRE, "--type", "headless", timeout=180)
        if code != 0:  # si no reanuda, descarta y arranca en frío
            vbox("discardstate", NOMBRE, timeout=90)
            time.sleep(2)
            _arrancar(progreso)
    elif not corriendo():
        _arrancar(progreso)
    try:
        esperar_ssh(progreso, limite=100)
    except RuntimeError:
        # con Hyper-V activo, VirtualBox a veces se queda congelado al arrancar: un reinicio en frío lo resuelve
        progreso("La máquina se atoró al arrancar; la reinicio en frío…")
        apagar(rapido=True)
        time.sleep(3)
        _arrancar(progreso)
        esperar_ssh(progreso, limite=240)


# ---------------------------------------------------------------- calentado (indicador de fases)
CALOR: dict = {"fase": "inactiva", "msg": "", "desde": 0.0, "error": ""}
_FASES = ("arrancando", "ssh", "elastic", "kibana", "lista")


def _fase(f: str, msg: str = "") -> None:
    if CALOR.get("fase") != f:
        CALOR["desde"] = time.time()
    CALOR.update(fase=f, msg=msg, error="")


def calentar(progreso=lambda *_: None, limite: int = 900, auto_caliente: bool = False) -> bool:
    """Enciende/reanuda la VM y espera a que Elasticsearch y Kibana respondan, actualizando CALOR para la UI.
    Si auto_caliente y no hay instantánea en caliente de este modo, la toma al quedar todo listo."""
    from core import siem
    if CALOR.get("fase") in _FASES[:-1] and time.time() - CALOR.get("desde", 0) < limite:
        return False  # ya hay un calentado en marcha
    t0 = time.time()

    def p(msg):
        CALOR["msg"] = msg
        progreso(msg)
    try:
        _fase("arrancando", "Encendiendo la VM…")
        encender(p)
        _fase("elastic", "Esperando a Elasticsearch…")
        while not siem.es_vivo():
            if time.time() - t0 > limite:
                raise RuntimeError("Elasticsearch no respondió a tiempo.")
            p(f"Calentando Elasticsearch… ({int(time.time() - t0)} s)")
            time.sleep(5)
        _fase("kibana", "Esperando a Kibana…")
        while not siem.kibana_vivo():
            if time.time() - t0 > limite:
                raise RuntimeError("Kibana no respondió a tiempo.")
            p(f"Calentando Kibana… ({int(time.time() - t0)} s)")
            time.sleep(5)
        _fase("lista", f"SIEM listo en {int(time.time() - t0)} s")
        # solo en modo rápido: con Hyper-V (NEM, 1 núcleo) la instantánea EN VIVO se arrastra a ~100 KB/s y se cuelga
        # 20 min hasta el timeout dejando la VM sin SSH (pasó el 20-nov). En NEM se arranca en frío y listo.
        if (auto_caliente and modo_hipervisor() == "rapido" and not caliente_valida()
                and espacio()["libre_gb"] >= RAM_SIEM_MB / 1024 + 10):
            try:
                tomar_caliente(p)
                _fase("lista", "SIEM listo · instantánea en caliente guardada")
            except Exception as e:  # noqa: BLE001
                CI_LOG.append(f"auto caliente: {e}")
        return True
    except Exception as e:  # noqa: BLE001
        CALOR.update(fase="error", error=str(e)[:300], msg="")
        return False


def calentar_en_fondo(auto_caliente: bool = True) -> bool:
    """Para el arranque de NetLab: si el SIEM está instalado, la VM se calienta sola en segundo plano."""
    if not vboxmanage() or not _siem_preparado():
        return False
    threading.Thread(target=calentar, kwargs={"auto_caliente": auto_caliente}, daemon=True).start()
    return True


# ---------------------------------------------------------------- disco
def espacio() -> dict:
    """Espacio libre del disco de NetLab y lo que ocupan el estado guardado (.sav) y las instantáneas."""
    try:
        du = shutil.disk_usage(CARPETA or ".")
        libre = round(du.free / 1024 ** 3, 1)
    except OSError:
        libre = 0.0
    sav, snaps = 0, 0
    carpeta_vm = os.path.join(CARPETA, NOMBRE) if CARPETA else ""
    for raiz, _, archivos in os.walk(carpeta_vm) if carpeta_vm and os.path.isdir(carpeta_vm) else []:
        for a in archivos:
            try:
                t = os.path.getsize(os.path.join(raiz, a))
            except OSError:
                continue
            if a.lower().endswith(".sav"):
                sav += t
            elif "snapshots" in raiz.lower():
                snaps += t
    return {"libre_gb": libre, "sav_gb": round(sav / 1024 ** 3, 1), "snaps_gb": round(snaps / 1024 ** 3, 1),
            "poco": libre < RAM_SIEM_MB / 1024 + 4}


def apagar(rapido: bool = False) -> None:
    if not vboxmanage() or not corriendo():
        return
    if not rapido:
        vbox("controlvm", NOMBRE, "acpipowerbutton", timeout=30)
        for _ in range(20):
            time.sleep(1.5)
            if not corriendo():
                return
    vbox("controlvm", NOMBRE, "poweroff", timeout=60)


def _apagar_total(progreso=lambda *_: None) -> None:
    """Deja la VM en 'poweroff' de verdad: si está corriendo la apaga, y si está 'saved' (suspendida) descarta el estado.
    Necesario antes de cambiar RAM/núcleos: VirtualBox no modifica una VM suspendida."""
    if not vboxmanage():
        return
    if corriendo():
        apagar()
        time.sleep(2)
    st = (info().get("VMState") or "").lower()
    if st == "saved":  # NetLab suspende la VM al cerrarse; hay que descartar ese estado para poder tocar la RAM
        progreso("Descartando el estado suspendido de la VM…")
        vbox("discardstate", NOMBRE, timeout=90)
        time.sleep(2)


def reiniciar(progreso) -> None:
    """Regresa la VM a la instantánea limpia (borra lo que hiciste en ella) y la enciende."""
    if not tiene_snapshot():
        raise RuntimeError("Aún no hay instantánea limpia: crea la máquina primero.")
    progreso("Apagando…")
    _apagar_total(progreso)  # 'saved' o encendida → poweroff real; restaurar instantánea exige la VM apagada
    progreso("Regresando a la instantánea limpia…")
    code, out = vbox("snapshot", NOMBRE, "restore", _uuid_limpio(), timeout=300)
    if code != 0:
        raise RuntimeError("No pude restaurar la instantánea: " + out[-300:])
    encender(progreso)


def _uuid_limpio() -> str:
    """UUID de la instantánea 'limpio' MÁS NUEVA. Puede haber varias con el mismo nombre (una nueva quedó anidada dentro de
    la vieja cuando VirtualBox no pudo borrar la vieja); restaurar por nombre tomaría la vieja. La lista sale en preorden,
    así que la última 'limpio' es la más profunda = la más nueva. Si no se puede leer, regresa el nombre."""
    code, out = vbox("snapshot", NOMBRE, "list", "--machinereadable", timeout=30)
    if code != 0:
        return SNAP
    nombres, uuids = {}, {}
    for linea in out.splitlines():
        k, _, v = linea.partition("=")
        v = v.strip().strip('"')
        if k.startswith("SnapshotName"):
            nombres[k[len("SnapshotName"):]] = v
        elif k.startswith("SnapshotUUID"):
            uuids[k[len("SnapshotUUID"):]] = v
    ult = SNAP
    for suf, nom in nombres.items():
        if nom == SNAP and uuids.get(suf):
            ult = uuids[suf]
    return ult


def _uuids_limpio() -> list[str]:
    """Todas las 'limpio' en preorden (la última es la más nueva)."""
    code, out = vbox("snapshot", NOMBRE, "list", "--machinereadable", timeout=30)
    if code != 0:
        return []
    nombres, uuids = {}, {}
    for linea in out.splitlines():
        k, _, v = linea.partition("=")
        v = v.strip().strip('"')
        if k.startswith("SnapshotName"):
            nombres[k[len("SnapshotName"):]] = v
        elif k.startswith("SnapshotUUID"):
            uuids[k[len("SnapshotUUID"):]] = v
    return [uuids[s] for s, n in nombres.items() if n == SNAP and uuids.get(s)]


def _discos_huerfanos() -> list[dict]:
    """Discos diferenciales de ESTA VM que VirtualBox tiene registrados pero que ninguna VM/instantánea usa."""
    code, out = vbox("list", "hdds", timeout=60)
    if code != 0:
        return []
    carpeta = os.path.normcase(os.path.abspath(os.path.join(CARPETA, NOMBRE)))
    res = []
    for bloque in out.replace("\r\n", "\n").split("\n\n"):
        campos = {}
        for linea in bloque.splitlines():
            k, _, v = linea.partition(":")
            campos[k.strip()] = v.strip()
        uuid, ruta, padre = campos.get("UUID", ""), campos.get("Location", ""), campos.get("Parent UUID", "base")
        if not uuid or not ruta or padre in ("", "base") or "In use by VMs" in campos:
            continue
        if not os.path.normcase(os.path.abspath(ruta)).startswith(carpeta):  # solo dentro de la carpeta de NetLab-Ubuntu
            continue
        if os.path.basename(ruta).lower() != f"{{{uuid}}}.vdi".lower():  # nombre típico de un diff de instantánea
            continue
        res.append({"uuid": uuid, "ruta": ruta, "gb": round(os.path.getsize(ruta) / 2**30, 2) if os.path.isfile(ruta) else 0})
    return res


def limpiar_discos(progreso) -> dict:
    """🧹 Quita discos diferenciales huérfanos y las instantáneas 'limpio' viejas (deja SOLO la más nueva). VM apagada."""
    with _LOCK:
        progreso("Apagando la VM para limpiar discos…")
        _apagar_total(progreso)
        borrados, liberado = [], 0.0
        for d in _discos_huerfanos():
            progreso(f"Quitando disco huérfano {os.path.basename(d['ruta'])} ({d['gb']} GB)…")
            code, out = vbox("closemedium", "disk", d["uuid"], "--delete", timeout=300)
            if code == 0:
                borrados.append(os.path.basename(d["ruta"]))
                liberado += d["gb"]
            else:
                CI_LOG.append(f"closemedium {d['uuid']} → {code} {out[-160:]}")
        viejas = _uuids_limpio()[:-1]
        quitadas = []
        for u in viejas:
            progreso("Fusionando la instantánea 'limpio' vieja (puede tardar unos minutos)…")
            code, out = vbox("snapshot", NOMBRE, "delete", u, timeout=1800)
            if code == 0:
                quitadas.append(u)
            else:
                CI_LOG.append(f"snapshot delete {u} → {code} {out[-200:]}")
    progreso("Encendiendo la VM…")
    encender(progreso)
    return {"discos_borrados": borrados, "gb_liberados": round(liberado, 2), "limpio_viejas_quitadas": len(quitadas),
            "limpio_quedan": len(_uuids_limpio())}


def ampliar_recursos(progreso) -> dict:
    """Deja la VM en RAM_SIEM_MB y cpus_siem() de forma permanente: apaga total, modifyvm, verifica y rehornea 'limpio'."""
    with _LOCK:
        progreso(f"Apagando la VM para ampliarla a {RAM_SIEM_MB // 1024} GB de RAM y {cpus_siem()} núcleos…")
        _apagar_total(progreso)
        vbox("modifyvm", NOMBRE, "--memory", str(RAM_SIEM_MB), "--cpus", str(cpus_siem()), timeout=60)
        ram = int(info().get("memory", "0") or 0)
        cpus = int(info().get("cpus", "0") or 0)
        if ram < RAM_SIEM_MB or cpus < cpus_siem():
            raise RuntimeError(f"No pude ampliar la VM (quedó en {ram} MB y {cpus} núcleos).")
    hornear_limpio(progreso)  # rehace 'limpio' con la nueva config y reenciende
    return {"ram_mb": ram, "cpus": cpus}


def hornear_limpio(progreso) -> None:
    """Rehace la instantánea 'limpio' con lo que tenga la VM ahora (p. ej. Docker + laboratorio), con la VM APAGADA
    (instantánea en frío: segura y rápida). Así 'Reiniciar máquina' ya no borra lo instalado."""
    with _LOCK:
        progreso("Apagando la VM para guardar la instantánea 'limpio'…")
        _apagar_total(progreso)
        borrar_caliente(progreso)  # cuelga de 'limpio': se rehace sola después
        if tiene_snapshot():  # si no se puede borrar (p. ej. un disco huérfano), la nueva queda anidada: _uuid_limpio la elige
            vbox("snapshot", NOMBRE, "delete", _uuid_limpio(), timeout=900)
        code, out = vbox("snapshot", NOMBRE, "take", SNAP, timeout=900)
        if code != 0:
            raise RuntimeError("No pude guardar la instantánea 'limpio': " + out[-300:])
    progreso("Encendiendo la VM…")
    encender(progreso)


def preparar_siem(progreso) -> None:
    """Instala Elasticsearch + Kibana en la VM y lo hornea en la instantánea 'limpio' (una sola vez).

    Deja la VM con 6 GB de RAM, los puertos 9200/5601 reenviados al host y los servicios encendidos.
    Tarda bastante (descarga ~1 GB y arranca Elastic): es normal que vaya lento en modo NEM.
    """
    from core import siem

    if not existe():
        raise RuntimeError("Primero crea la máquina Linux (botón Crear) antes de instalar el SIEM.")
    # marca de "provisionando": hace que _asegurar_nat le dé 6 GB + 2 núcleos a cada arranque de aquí en adelante
    with open(_marca("siem.provisionando"), "w", encoding="utf-8") as f:
        f.write("1")
    try:
        progreso(f"Dejando la VM totalmente apagada para ampliarla a {RAM_SIEM_MB // 1024} GB de RAM y {cpus_siem()} núcleo(s)…")
        _apagar_total(progreso)  # clave: una VM 'saved' (suspendida) NO deja cambiar la RAM
        # fijamos recursos explícitamente y VERIFICAMOS (el bug anterior era que la RAM se quedaba en 2 GB)
        code, out = vbox("modifyvm", NOMBRE, "--memory", str(RAM_SIEM_MB), "--cpus", str(cpus_siem()), timeout=60)
        ram = int(info().get("memory", "0") or 0)
        if ram < RAM_SIEM_MB:
            raise RuntimeError(f"No pude ampliar la RAM de la VM (quedó en {ram} MB; modifyvm devolvió {code}: {out[-160:]}).")
        CI_LOG.append(f"RAM verificada = {ram} MB")
        encender(progreso)  # _asegurar_nat ya ve la marca → RAM+núcleos de SIEM + puertos 9200/5601

        progreso("Instalando Elasticsearch + Kibana en la VM (descarga ~1 GB, puede tardar 10-20 min)…")
        code, out = ssh(siem.script_instalar(), timeout=1500, root=True)
        if code != 0 or ("INSTALADO_OK" not in out and "YA_INSTALADO" not in out):
            raise RuntimeError("Falló la instalación del SIEM: " + out[-600:])

        # Arranque limpio para que systemd levante Elasticsearch+Kibana sin la carga del apt;
        # NO esperamos por SSH (Elastic ahoga la VM al arrancar), verificamos desde el HOST por el puerto 9200.
        progreso("Reiniciando la VM para encender el SIEM…")
        apagar()
        time.sleep(2)
        encender(progreso)  # arranca + espera SSH (con reintento en frío si se atora); Elastic calienta en segundo plano
        progreso("Esperando a que Elasticsearch responda (puede tardar varios minutos en esta VM)…")
        t0 = time.time()
        vivo = False
        while time.time() - t0 < 600:  # esta VM es muy lenta bajo Hyper-V; damos margen amplio
            # verdad de fondo: preguntamos DENTRO de la VM por SSH (más fiable que el puerto reenviado)
            code, _ = ssh("curl -s -m 4 http://localhost:9200 >/dev/null && echo ok", timeout=25)
            if code == 0:
                vivo = True
                break
            progreso(f"Calentando Elasticsearch… ({int(time.time() - t0)} s)")
            time.sleep(10)
        if not vivo:
            raise RuntimeError("Elasticsearch no respondió dentro de la VM tras varios minutos. "
                               "Revisa el diagnóstico de la VM (botón de diagnóstico).")
        # ES vivo dentro de la VM; confirmamos que también llega al host por el puerto reenviado 9200
        if not siem.es_vivo():
            progreso("Elasticsearch vivo en la VM pero el host aún no lo alcanza; reintentando el reenvío de puertos…")
            time.sleep(10)

        progreso("Guardando la instantánea 'limpio' con el SIEM ya instalado…")
        apagar()
        time.sleep(2)
        borrar_caliente(progreso)  # la instantánea en caliente cuelga de 'limpio': se rehace después
        if tiene_snapshot():
            vbox("snapshot", NOMBRE, "delete", SNAP, timeout=900)
        code, out = vbox("snapshot", NOMBRE, "take", SNAP, timeout=900)
        if code != 0:
            raise RuntimeError("No pude guardar la instantánea con el SIEM: " + out[-300:])
        # marca persistente: a partir de aquí la VM arranca siempre con recursos de SIEM
        with open(_marca("siem.ok"), "w", encoding="utf-8") as f:
            f.write("1")
        progreso("Encendiendo la VM con el SIEM (Kibana tarda 1-3 min en calentar)…")
        encender(progreso)
    finally:
        try:
            os.remove(_marca("siem.provisionando"))
        except OSError:
            pass


def siem_instalado() -> bool:
    return _siem_preparado()


def diagnostico() -> dict:
    """Para cuando la VM no responde: estado, foto de su pantalla y el final de su consola serial."""
    i = info()
    foto = os.path.join(CARPETA, "pantalla.png")
    code, out = vbox("controlvm", NOMBRE, "screenshotpng", foto, timeout=30) if corriendo() else (1, "apagada")
    try:
        with open(os.path.join(CARPETA, "consola.log"), encoding="utf-8", errors="replace") as f:
            cola = f.read()[-3000:]
    except OSError:
        cola = ""
    return {"estado": i.get("VMState"), "foto": foto if code == 0 else out[-200:], "consola": cola,
            "nat": {k: v for k, v in i.items() if "Forwarding" in k or k.startswith("nic")}}


def borrar_vm() -> None:
    """Quita la VM de NetLab de VirtualBox con sus discos (solo NetLab-Ubuntu; la imagen .ova se queda)."""
    apagar(rapido=True)
    time.sleep(2)
    vbox("unregistervm", NOMBRE, "--delete", timeout=300)


def estado() -> dict:
    vb = vboxmanage()
    d = {"vbox": bool(vb), "ova": os.path.isfile(os.path.join(CARPETA, OVA)), "existe": False, "corriendo": False, "ssh": False,
         "snapshot": False, "usuario": USUARIO, "clave": CLAVE, "puerto": PUERTO_SSH, "vmstate": "",
         "modo": modo_hipervisor(), "cpus_siem": cpus_siem(), "caliente": False, "calor": dict(CALOR)}
    if not vb:
        return d
    try:
        i = info()
        d["existe"] = bool(i)
        d["corriendo"] = i.get("VMState") in ("running", "starting")
        d["vmstate"] = i.get("VMState", "")
        d["cpus"] = i.get("cpus")
        d["caliente"] = d["existe"] and caliente_valida()
        d["espacio"] = espacio()
        d["snapshot"] = d["existe"] and tiene_snapshot()
        d["ssh"] = d["corriendo"] and ssh_ok()
    except Exception as e:  # noqa: BLE001
        d["error"] = str(e)[:200]
    return d
