"""Proyectos grandes de Rust con cargo: herramientas reales de redes/SOC construidas por niveles.

A diferencia de la Academia (un archivo con rustc), aquí cada misión es un proyecto cargo de verdad:
Cargo.toml + src/lib.rs (lo que escribe el alumno) + tests/ ocultos. Se califica con `cargo test`.
Todo es `std` puro (sin dependencias) → compila sin internet. Proyectos: escáner de puertos, parser .pcap, mini IDS.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile

CARGO_TOML = '[package]\nname = "lab"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'


def buscar_cargo() -> str | None:
    c = shutil.which("cargo")
    if c:
        return c
    for base in (os.path.expanduser("~/.cargo/bin"), os.path.join(os.environ.get("USERPROFILE", ""), ".cargo", "bin")):
        for nombre in ("cargo.exe", "cargo"):
            p = os.path.join(base, nombre)
            if os.path.isfile(p):
                return p
    return None


def _limpia(texto: str, proj: str) -> str:
    texto = texto.replace(os.path.join(proj, "src", "lib.rs"), "src/lib.rs")
    texto = texto.replace(os.path.join(proj, "src", "lib.rs").replace("\\", "/"), "src/lib.rs")
    return re.sub(r"note: run with `RUST_BACKTRACE=1`[^\n]*\n?", "", texto)


def calificar_cargo(codigo: str, carpeta_tmp: str, *, pruebas: str) -> dict:
    """Arma un proyecto cargo temporal (src/lib.rs del alumno + tests ocultos) y corre `cargo test`."""
    from .academia import _resultados_tests, _sin_ventana  # import perezoso (evita el ciclo con academia)
    cargo = buscar_cargo()
    if not cargo:
        return {"aprobado": False, "fase": "entorno",
                "fallo": "No encontré cargo. Instala Rust con rustup (incluye cargo) y reinicia NetLab."}
    reglas = ["Todavía hay `todo!()` sin resolver"] if "todo!(" in codigo else []
    os.makedirs(carpeta_tmp, exist_ok=True)  # la carpeta temporal se borra al cerrar NetLab; la recreamos
    proj = tempfile.mkdtemp(prefix="rp_", dir=carpeta_tmp)
    try:
        os.makedirs(os.path.join(proj, "src"), exist_ok=True)
        os.makedirs(os.path.join(proj, "tests"), exist_ok=True)
        with open(os.path.join(proj, "Cargo.toml"), "w", encoding="utf-8") as f:
            f.write(CARGO_TOML)
        with open(os.path.join(proj, "src", "lib.rs"), "w", encoding="utf-8") as f:
            f.write(codigo)
        with open(os.path.join(proj, "tests", "pruebas.rs"), "w", encoding="utf-8") as f:
            f.write(pruebas)
        env = {**os.environ, "CARGO_TERM_COLOR": "never", "RUST_BACKTRACE": "0"}
        try:
            r = subprocess.run([cargo, "test", "--offline", "--test", "pruebas"], cwd=proj,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=180, env=env, **_sin_ventana())
        except subprocess.TimeoutExpired:
            return {"aprobado": False, "fase": "correr", "fallo": "Tardó demasiado (¿bucle infinito?).", "reglas": reglas}
        pr = _resultados_tests(r.stdout)
        if not pr:  # no corrió ninguna prueba: casi siempre error de compilación
            err = _limpia((r.stderr + "\n" + r.stdout).strip(), proj)
            return {"aprobado": False, "fase": "compilar", "fallo": err[-3000:] or "No se pudo compilar.", "reglas": reglas}
        return {"aprobado": all(p["ok"] for p in pr) and not reglas, "pruebas": pr, "reglas": reglas, "avisos": ""}
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def calificar(mid: str, codigo: str, carpeta_tmp: str) -> dict:
    m = MISIONES.get(mid)
    if not m:
        return {"error": "misión desconocida"}
    return calificar_cargo(codigo, carpeta_tmp, pruebas=m["pruebas"])


# =============================================================================
#  Contenido de los proyectos
# =============================================================================
def _m(id, titulo, teoria, enunciado, inicial, pistas, pruebas, solucion, jefe=False):
    return {"id": id, "titulo": titulo, "teoria": teoria.strip(), "enunciado": enunciado.strip(),
            "inicial": inicial.strip() + "\n", "pistas": pistas, "pruebas": pruebas.strip() + "\n",
            "solucion": solucion.strip() + "\n", "jefe": jefe, "modo": "cargo", "modulo": ""}


# ---------------------------------------------------------------- Proyecto 1: escáner de puertos
ESCANER = [
    _m("rp_esc1", "Parsear los puertos",
       """Un escáner recibe los puertos a revisar como texto: `"22"`, un rango `"20-25"`, o una lista `"22,80,443"`.
Antes de tocar la red, hay que convertir ese texto en una lista de números limpia.

En Rust, `str::split(',')` parte por comas y `split_once('-')` separa un rango. `parse::<u16>()` convierte texto a número
(devuelve `Result`). Al final `sort()` y `dedup()` ordenan y quitan repetidos.""",
       """Implementa `parsear_puertos(spec: &str) -> Vec<u16>`: convierte la especificación en un `Vec<u16>`
**ordenado y sin repetidos**. Acepta puertos sueltos, rangos `a-b` (inclusivo) y listas separadas por comas (con o sin espacios).
Ignora lo que no sea un número válido.""",
       """/// Convierte "22,80,1000-1002" en un Vec<u16> ordenado y sin repetidos.
pub fn parsear_puertos(spec: &str) -> Vec<u16> {
    todo!("parsea la especificación de puertos")
}""",
       ["Recorre `spec.split(',')`; a cada parte quítale espacios con `.trim()`.",
        "Si la parte tiene `-`, úsalo con `split_once('-')` y genera el rango `a..=b`.",
        "Junta todo en un `Vec`, luego `v.sort(); v.dedup();` y devuélvelo."],
       """use lab::*;
#[test] fn un_puerto() { assert_eq!(parsear_puertos("80"), vec![80]); }
#[test] fn un_rango() { assert_eq!(parsear_puertos("20-23"), vec![20,21,22,23]); }
#[test] fn lista_ordena_y_dedup() { assert_eq!(parsear_puertos("443,22,80,22"), vec![22,80,443]); }
#[test] fn rango_y_sueltos_con_espacios() { assert_eq!(parsear_puertos("1000-1002, 25"), vec![25,1000,1001,1002]); }""",
       """pub fn parsear_puertos(spec: &str) -> Vec<u16> {
    let mut v = Vec::new();
    for parte in spec.split(',') {
        let parte = parte.trim();
        if parte.is_empty() { continue; }
        if let Some((a, b)) = parte.split_once('-') {
            if let (Ok(a), Ok(b)) = (a.trim().parse::<u16>(), b.trim().parse::<u16>()) {
                for p in a..=b { v.push(p); }
            }
        } else if let Ok(p) = parte.parse::<u16>() {
            v.push(p);
        }
    }
    v.sort();
    v.dedup();
    v
}"""),
    _m("rp_esc2", "¿El puerto está abierto?",
       """Para saber si un puerto TCP está abierto, se intenta **conectar**. Si la conexión se establece, está abierto;
si la rechazan o no contesta antes del tiempo límite, está cerrado o filtrado.

`TcpStream::connect_timeout(&addr, dur)` intenta conectar con un tope de tiempo (clave: sin timeout, un puerto filtrado
te cuelga el escáner). `addr` es un `SocketAddr`, que sale de parsear `"ip:puerto"`.""",
       """Implementa `puerto_abierto(ip: &str, puerto: u16, ms: u64) -> bool`: devuelve `true` si se logra conectar por TCP
a `ip:puerto` dentro de `ms` milisegundos. Si la dirección es inválida o no conecta, `false`.""",
       """use std::net::{TcpStream, SocketAddr};
use std::time::Duration;

/// true si se puede conectar por TCP a ip:puerto dentro de `ms` milisegundos.
pub fn puerto_abierto(ip: &str, puerto: u16, ms: u64) -> bool {
    todo!("intenta conectar con connect_timeout")
}""",
       ["Arma la dirección con `format!(\"{ip}:{puerto}\").parse::<SocketAddr>()` (devuelve `Result`).",
        "Si el parseo falla, devuelve `false` de una vez.",
        "`TcpStream::connect_timeout(&dir, Duration::from_millis(ms)).is_ok()` te da el bool."],
       """use lab::*;
use std::net::TcpListener;
#[test]
fn detecta_abierto() {
    let l = TcpListener::bind("127.0.0.1:0").unwrap();
    let p = l.local_addr().unwrap().port();
    assert!(puerto_abierto("127.0.0.1", p, 800));
}
#[test]
fn detecta_cerrado() {
    let p = { let l = TcpListener::bind("127.0.0.1:0").unwrap(); l.local_addr().unwrap().port() };
    assert!(!puerto_abierto("127.0.0.1", p, 400));
}
#[test]
fn ip_invalida_es_falso() { assert!(!puerto_abierto("no-es-ip", 80, 200)); }""",
       """use std::net::{TcpStream, SocketAddr};
use std::time::Duration;

pub fn puerto_abierto(ip: &str, puerto: u16, ms: u64) -> bool {
    let dir: SocketAddr = match format!("{ip}:{puerto}").parse() {
        Ok(d) => d,
        Err(_) => return false,
    };
    TcpStream::connect_timeout(&dir, Duration::from_millis(ms)).is_ok()
}"""),
    _m("rp_esc3", "👑 Escaneo concurrente",
       """Revisar mil puertos uno por uno es lentísimo. Un escáner real lanza muchas comprobaciones **en paralelo** con hilos.

`std::thread::spawn(move || { ... })` lanza un hilo; `handle.join()` espera su resultado. Cada hilo revisa un puerto y
devuelve `Some(puerto)` si está abierto. Al final juntas los `Some` y ordenas.""",
       """Ya tienes `puerto_abierto` (incluida abajo). Implementa `escanear(ip: &str, puertos: &[u16]) -> Vec<u16>`:
revisa **todos los puertos en paralelo** (un hilo por puerto) y devuelve los abiertos, **ordenados**.""",
       """use std::net::{TcpStream, SocketAddr};
use std::time::Duration;
use std::thread;

pub fn puerto_abierto(ip: &str, puerto: u16, ms: u64) -> bool {
    let dir: SocketAddr = match format!("{ip}:{puerto}").parse() { Ok(d) => d, Err(_) => return false };
    TcpStream::connect_timeout(&dir, Duration::from_millis(ms)).is_ok()
}

/// Revisa los puertos en paralelo y devuelve los abiertos, ordenados.
pub fn escanear(ip: &str, puertos: &[u16]) -> Vec<u16> {
    todo!("lanza un hilo por puerto y junta los abiertos")
}""",
       ["Por cada puerto, clona la ip con `ip.to_string()` y lánzalo: `thread::spawn(move || if puerto_abierto(&ip, p, 500) { Some(p) } else { None })`.",
        "Guarda los handles en un `Vec` y luego `.join().unwrap()` en cada uno.",
        "Usa `.filter_map(|h| h.join().unwrap())` para quedarte solo con los `Some`, y `sort()` al final."],
       """use lab::*;
use std::net::TcpListener;
#[test]
fn escanea_en_paralelo() {
    let l1 = TcpListener::bind("127.0.0.1:0").unwrap();
    let l2 = TcpListener::bind("127.0.0.1:0").unwrap();
    let p1 = l1.local_addr().unwrap().port();
    let p2 = l2.local_addr().unwrap().port();
    let cerrado = { let l = TcpListener::bind("127.0.0.1:0").unwrap(); l.local_addr().unwrap().port() };
    let mut abiertos = escanear("127.0.0.1", &[p1, cerrado, p2]);
    abiertos.sort();
    let mut esperado = vec![p1, p2];
    esperado.sort();
    assert_eq!(abiertos, esperado);
}""",
       """use std::net::{TcpStream, SocketAddr};
use std::time::Duration;
use std::thread;

pub fn puerto_abierto(ip: &str, puerto: u16, ms: u64) -> bool {
    let dir: SocketAddr = match format!("{ip}:{puerto}").parse() { Ok(d) => d, Err(_) => return false };
    TcpStream::connect_timeout(&dir, Duration::from_millis(ms)).is_ok()
}

pub fn escanear(ip: &str, puertos: &[u16]) -> Vec<u16> {
    let mut hilos = Vec::new();
    for &p in puertos {
        let ip = ip.to_string();
        hilos.push(thread::spawn(move || if puerto_abierto(&ip, p, 500) { Some(p) } else { None }));
    }
    let mut abiertos: Vec<u16> = hilos.into_iter().filter_map(|h| h.join().unwrap()).collect();
    abiertos.sort();
    abiertos
}""", jefe=True),
]

# ---------------------------------------------------------------- Proyecto 2: parser de .pcap
PCAP = [
    _m("rp_pcap1", "Leer enteros little-endian",
       """Un archivo `.pcap` (el formato de Wireshark/tcpdump) guarda los números en **little-endian**: el byte menos
significativo primero. Para parsearlo hay que leer enteros de 4 bytes desde una posición dada.

En Rust, `u32::from_le_bytes([a,b,c,d])` arma el entero. El reto es tomar los 4 bytes correctos del slice sin salirte.""",
       """Implementa `leer_u32_le(bytes: &[u8], offset: usize) -> u32`: lee 4 bytes a partir de `offset` como un `u32`
little-endian. Si no hay 4 bytes disponibles desde `offset`, devuelve `0`.""",
       """/// Lee 4 bytes little-endian desde `offset`. Si no caben, devuelve 0.
pub fn leer_u32_le(bytes: &[u8], offset: usize) -> u32 {
    todo!("arma el u32 little-endian")
}""",
       ["Primero valida: si `offset + 4 > bytes.len()`, devuelve `0`.",
        "Toma los bytes `bytes[offset]`, `bytes[offset+1]`, `bytes[offset+2]`, `bytes[offset+3]`.",
        "`u32::from_le_bytes([..])` los convierte en el entero."],
       """use lab::*;
#[test] fn magic_pcap() { assert_eq!(leer_u32_le(&[0xd4,0xc3,0xb2,0xa1], 0), 0xa1b2c3d4); }
#[test] fn con_offset() { assert_eq!(leer_u32_le(&[0,0, 1,0,0,0], 2), 1); }
#[test] fn fuera_de_rango_es_cero() { assert_eq!(leer_u32_le(&[1,2,3], 0), 0); }""",
       """pub fn leer_u32_le(bytes: &[u8], offset: usize) -> u32 {
    if offset + 4 > bytes.len() { return 0; }
    u32::from_le_bytes([bytes[offset], bytes[offset+1], bytes[offset+2], bytes[offset+3]])
}"""),
    _m("rp_pcap2", "Validar la cabecera",
       """Todo `.pcap` empieza con una **cabecera global** de 24 bytes cuyos primeros 4 son un número mágico:
`0xa1b2c3d4`. Según el orden de bytes del equipo que lo grabó, aparece como `d4 c3 b2 a1` (little-endian) o
`a1 b2 c3 d4` (big-endian). Validar esto evita parsear basura.""",
       """Implementa `cabecera_valida(bytes: &[u8]) -> bool`: `true` solo si el archivo mide al menos 24 bytes y sus
primeros 4 bytes son el número mágico pcap en cualquiera de los dos órdenes.""",
       """/// true si es un .pcap válido (>=24 bytes y número mágico correcto).
pub fn cabecera_valida(bytes: &[u8]) -> bool {
    todo!("revisa tamaño y número mágico")
}""",
       ["Si `bytes.len() < 24`, ya es `false`.",
        "Compara el slice `&bytes[0..4]` contra `[0xd4,0xc3,0xb2,0xa1]` y `[0xa1,0xb2,0xc3,0xd4]`.",
        "Devuelve `true` si coincide con cualquiera de los dos."],
       """use lab::*;
fn cab() -> Vec<u8> { let mut v = vec![0xd4,0xc3,0xb2,0xa1]; v.extend(std::iter::repeat(0).take(20)); v }
#[test] fn valida_le() { assert!(cabecera_valida(&cab())); }
#[test] fn valida_be() { let mut v = vec![0xa1,0xb2,0xc3,0xd4]; v.extend(std::iter::repeat(0).take(20)); assert!(cabecera_valida(&v)); }
#[test] fn magico_malo() { let mut v = vec![1,2,3,4]; v.extend(std::iter::repeat(0).take(20)); assert!(!cabecera_valida(&v)); }
#[test] fn muy_corto() { assert!(!cabecera_valida(&[0xd4,0xc3,0xb2,0xa1])); }""",
       """pub fn cabecera_valida(bytes: &[u8]) -> bool {
    if bytes.len() < 24 { return false; }
    let m = &bytes[0..4];
    m == [0xd4, 0xc3, 0xb2, 0xa1] || m == [0xa1, 0xb2, 0xc3, 0xd4]
}"""),
    _m("rp_pcap3", "👑 Contar los paquetes",
       """Después de los 24 bytes de cabecera global, el `.pcap` es una secuencia de **paquetes**. Cada uno trae una
cabecera de registro de 16 bytes: `ts_sec`, `ts_usec`, `incl_len`, `orig_len` (cada uno u32 little-endian). `incl_len`
dice cuántos bytes de datos siguen. Para recorrer el archivo: lees `incl_len`, saltas `16 + incl_len` y repites.""",
       """Ya tienes `leer_u32_le`. Implementa `longitudes_paquetes(bytes: &[u8]) -> Vec<u32>`: recorre los paquetes y
devuelve la lista de sus `incl_len` (tamaño de cada paquete capturado), en orden. Empieza tras los 24 bytes de cabecera.""",
       """pub fn leer_u32_le(bytes: &[u8], offset: usize) -> u32 {
    if offset + 4 > bytes.len() { return 0; }
    u32::from_le_bytes([bytes[offset], bytes[offset+1], bytes[offset+2], bytes[offset+3]])
}

/// Recorre los registros de paquete y devuelve sus incl_len.
pub fn longitudes_paquetes(bytes: &[u8]) -> Vec<u32> {
    todo!("recorre los paquetes leyendo incl_len")
}""",
       ["Empieza en `i = 24` (saltas la cabecera global).",
        "Mientras `i + 16 <= bytes.len()`: `incl_len` está en `leer_u32_le(bytes, i + 8)`.",
        "Guarda `incl_len`, avanza `i += 16 + incl_len as usize` y repite."],
       """use lab::*;
fn u32le(n: u32) -> [u8;4] { n.to_le_bytes() }
#[test]
fn dos_paquetes() {
    let mut b = vec![0u8; 24];
    b.extend_from_slice(&u32le(0)); b.extend_from_slice(&u32le(0));
    b.extend_from_slice(&u32le(3)); b.extend_from_slice(&u32le(3));
    b.extend_from_slice(&[1,2,3]);
    b.extend_from_slice(&u32le(0)); b.extend_from_slice(&u32le(0));
    b.extend_from_slice(&u32le(2)); b.extend_from_slice(&u32le(2));
    b.extend_from_slice(&[9,9]);
    assert_eq!(longitudes_paquetes(&b), vec![3,2]);
}
#[test] fn sin_paquetes() { assert_eq!(longitudes_paquetes(&vec![0u8;24]), Vec::<u32>::new()); }""",
       """pub fn leer_u32_le(bytes: &[u8], offset: usize) -> u32 {
    if offset + 4 > bytes.len() { return 0; }
    u32::from_le_bytes([bytes[offset], bytes[offset+1], bytes[offset+2], bytes[offset+3]])
}

pub fn longitudes_paquetes(bytes: &[u8]) -> Vec<u32> {
    let mut out = Vec::new();
    let mut i = 24;
    while i + 16 <= bytes.len() {
        let incl = leer_u32_le(bytes, i + 8);
        out.push(incl);
        i += 16 + incl as usize;
    }
    out
}""", jefe=True),
]

# ---------------------------------------------------------------- Proyecto 3: mini IDS
IDS = [
    _m("rp_ids1", "¿IP interna o externa?",
       """Un IDS clasifica el tráfico. Lo primero: saber si una IP es **privada** (interna, RFC 1918: `10.0.0.0/8`,
`172.16.0.0/12`, `192.168.0.0/16`) o pública (externa). Un login exitoso desde una IP externa pesa distinto que desde la red interna.

`std::net::Ipv4Addr` parsea una IP y trae el método `.is_private()`. Parsear devuelve `Result`: una cadena inválida es `Err`.""",
       """Implementa `es_ip_privada(ip: &str) -> bool`: `true` si `ip` es una IPv4 privada válida. Si no parsea o es pública, `false`.""",
       """use std::net::Ipv4Addr;

/// true si la cadena es una IPv4 privada (RFC 1918).
pub fn es_ip_privada(ip: &str) -> bool {
    todo!("parsea la IP y revisa si es privada")
}""",
       ["`ip.parse::<Ipv4Addr>()` devuelve `Result<Ipv4Addr, _>`.",
        "Con `match`, en `Ok(a)` devuelve `a.is_private()`, en `Err(_)` devuelve `false`.",
        "Recuerda que `172.32.0.1` ya NO es privada (el rango privado es 172.16–172.31)."],
       """use lab::*;
#[test] fn privadas() { assert!(es_ip_privada("10.0.0.5")); assert!(es_ip_privada("192.168.1.1")); assert!(es_ip_privada("172.16.4.4")); }
#[test] fn publicas() { assert!(!es_ip_privada("8.8.8.8")); assert!(!es_ip_privada("172.32.0.1")); }
#[test] fn no_es_ip() { assert!(!es_ip_privada("hola")); }""",
       """use std::net::Ipv4Addr;

pub fn es_ip_privada(ip: &str) -> bool {
    match ip.parse::<Ipv4Addr>() {
        Ok(a) => a.is_private(),
        Err(_) => false,
    }
}"""),
    _m("rp_ids2", "Detectar un escaneo de puertos",
       """Regla clásica de IDS: una IP que, en poco tiempo, toca **muchos puertos distintos** del mismo o varios equipos,
probablemente está escaneando. Para medir "puertos distintos" por IP se usa un mapa de IP → conjunto de puertos.

`HashMap<&str, HashSet<u16>>`: por cada evento insertas el puerto en el conjunto de esa IP. Luego cuentas cuántos tiene cada una.""",
       """Implementa `detectar_escaneo(eventos: &[(&str, u16)], umbral: usize) -> Vec<String>`. Cada evento es `(ip_origen, puerto_destino)`.
Devuelve, **ordenadas**, las IPs que tocaron **al menos `umbral` puertos distintos**.""",
       """use std::collections::{HashMap, HashSet};

/// IPs (ordenadas) que tocaron >= `umbral` puertos distintos.
pub fn detectar_escaneo(eventos: &[(&str, u16)], umbral: usize) -> Vec<String> {
    todo!("agrupa puertos distintos por IP y filtra por umbral")
}""",
       ["Crea `HashMap<&str, HashSet<u16>>` y por cada `(ip, p)` haz `mapa.entry(ip).or_default().insert(*p);`.",
        "Un `HashSet` ignora los puertos repetidos automáticamente.",
        "Filtra las entradas con `conjunto.len() >= umbral`, saca la IP a `String`, y `sort()` al final."],
       """use lab::*;
#[test]
fn caza_al_escaneador() {
    let ev = [("10.0.0.5",22),("10.0.0.5",80),("10.0.0.5",443),("8.8.8.8",80)];
    assert_eq!(detectar_escaneo(&ev, 3), vec!["10.0.0.5".to_string()]);
}
#[test]
fn repetir_puerto_no_cuenta() {
    let ev = [("1.1.1.1",22),("1.1.1.1",22),("1.1.1.1",22)];
    assert!(detectar_escaneo(&ev, 2).is_empty());
}
#[test]
fn ordena_resultados() {
    let ev = [("9.9.9.9",1),("9.9.9.9",2),("1.1.1.1",1),("1.1.1.1",2)];
    assert_eq!(detectar_escaneo(&ev, 2), vec!["1.1.1.1".to_string(), "9.9.9.9".to_string()]);
}""",
       """use std::collections::{HashMap, HashSet};

pub fn detectar_escaneo(eventos: &[(&str, u16)], umbral: usize) -> Vec<String> {
    let mut m: HashMap<&str, HashSet<u16>> = HashMap::new();
    for (ip, p) in eventos {
        m.entry(ip).or_default().insert(*p);
    }
    let mut out: Vec<String> = m.into_iter()
        .filter(|(_, s)| s.len() >= umbral)
        .map(|(ip, _)| ip.to_string())
        .collect();
    out.sort();
    out
}"""),
    _m("rp_ids3", "👑 Detectar fuerza bruta",
       """La regla estrella de un SOC N1: una IP con **muchos intentos de login fallidos** es un ataque de fuerza bruta.
Se cuentan los fallos por IP y se alerta de las que pasan un umbral. Es exactamente lo que cazas en el mundo SIEM, pero ahora
lo programas tú.""",
       """Implementa `detectar_fuerza_bruta(intentos: &[(&str, bool)], umbral: usize) -> Vec<String>`. Cada intento es
`(ip_origen, exito)`. Devuelve, **ordenadas**, las IPs con **al menos `umbral` intentos fallidos** (`exito == false`).""",
       """use std::collections::HashMap;

/// IPs (ordenadas) con >= `umbral` logins fallidos.
pub fn detectar_fuerza_bruta(intentos: &[(&str, bool)], umbral: usize) -> Vec<String> {
    todo!("cuenta los fallos por IP y filtra")
}""",
       ["Usa `HashMap<&str, usize>` para contar fallos.",
        "Por cada `(ip, exito)`, si `!exito` haz `*mapa.entry(ip).or_insert(0) += 1;`.",
        "Filtra las que tengan `conteo >= umbral`, pásalas a `String` y ordénalas."],
       """use lab::*;
#[test]
fn caza_fuerza_bruta() {
    let a = [("9.9.9.9",false),("9.9.9.9",false),("9.9.9.9",false),("9.9.9.9",true),("2.2.2.2",false)];
    assert_eq!(detectar_fuerza_bruta(&a, 3), vec!["9.9.9.9".to_string()]);
}
#[test]
fn pocos_fallos_no_alertan() {
    let a = [("5.5.5.5",false),("5.5.5.5",true)];
    assert!(detectar_fuerza_bruta(&a, 3).is_empty());
}
#[test]
fn varias_ordenadas() {
    let a = [("9.9.9.9",false),("9.9.9.9",false),("1.1.1.1",false),("1.1.1.1",false)];
    assert_eq!(detectar_fuerza_bruta(&a, 2), vec!["1.1.1.1".to_string(), "9.9.9.9".to_string()]);
}""",
       """use std::collections::HashMap;

pub fn detectar_fuerza_bruta(intentos: &[(&str, bool)], umbral: usize) -> Vec<String> {
    let mut m: HashMap<&str, usize> = HashMap::new();
    for (ip, exito) in intentos {
        if !exito { *m.entry(ip).or_insert(0) += 1; }
    }
    let mut out: Vec<String> = m.into_iter()
        .filter(|(_, n)| *n >= umbral)
        .map(|(ip, _)| ip.to_string())
        .collect();
    out.sort();
    out
}""", jefe=True),
]

NIVELES_RUSTPROJ = [
    {"nombre": "🔌 Escáner de puertos", "cap": "Sockets TCP y concurrencia con hilos", "misiones": ESCANER},
    {"nombre": "📦 Parser de .pcap", "cap": "Parseo binario y little-endian", "misiones": PCAP},
    {"nombre": "🛡️ Mini IDS", "cap": "Reglas de detección con mapas y conjuntos", "misiones": IDS},
]

CURSO = {"nombre": "Proyectos Rust", "icono": "🛠️", "lema": "Herramientas reales de redes y SOC con cargo: un escáner de puertos, un parser de .pcap y un mini IDS",
         "niveles": NIVELES_RUSTPROJ}

MISIONES = {m["id"]: {**m, "curso": "rustproj", "nivel": n}
            for n, nivel in enumerate(NIVELES_RUSTPROJ) for m in nivel["misiones"]}
