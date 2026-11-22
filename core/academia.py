"""Academia de NetLab: Rust (con enfoque en ciberseguridad), IA y Procesadores.

Cada misión es código Rust que TÚ escribes. NetLab lo compila con el rustc de tu PC y lo califica con
pruebas ocultas (#[test]) o comparando la salida. Nada de esto usa la IA: la IA solo es el tutor.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile


def M(id, titulo, teoria, enunciado, inicial, solucion, pruebas, pistas, requiere=(), prohibido=(), modo="tests",
      salida="", entrada="", jefe=False):
    return {"id": id, "titulo": titulo, "teoria": teoria.strip(), "enunciado": enunciado.strip(), "inicial": inicial.strip() + "\n",
            "solucion": solucion.strip() + "\n", "pruebas": pruebas.strip(), "pistas": list(pistas), "requiere": list(requiere),
            "prohibido": list(prohibido), "modo": modo, "salida": salida, "entrada": entrada, "jefe": jefe}


# =============================================================================
#  🦀 RUST — sigue el orden del Rust Book, con ejercicios de ciberseguridad
# =============================================================================
RUST = [
  {"nombre": "Primeros pasos", "cap": "Rust Book cap. 1-3", "misiones": [
    M("rs0_1", "Hola, Ferris",
      """`println!` imprime una línea. Las variables se declaran con `let` y por defecto **no cambian** (son inmutables).
`{}` dentro del texto se reemplaza por el valor: `println!("Puerto: {}", p);` o directo `println!("Puerto: {p}");`.""",
      """Haz que el programa imprima exactamente estas dos líneas:
```
Hola, Rustacean
Puerto seguro: 443
```
El 443 debe salir de una variable `puerto`.""",
      """fn main() {
    // escribe aquí
}""",
      """fn main() {
    let puerto = 443;
    println!("Hola, Rustacean");
    println!("Puerto seguro: {puerto}");
}""",
      "", ["Usa dos `println!`.", "Declara `let puerto = 443;` y usa `{puerto}` dentro del texto."],
      requiere=[(r"let\s+puerto", "Declara la variable `puerto` con let")], modo="salida",
      salida="Hola, Rustacean\nPuerto seguro: 443"),
    M("rs0_2", "Variables, mut y tuplas",
      """Para que una variable cambie usa `let mut`. Una función devuelve el valor de su **última expresión** (sin `;`).
Una tupla agrupa valores: `(u32, u32)`. `/` entre enteros es división entera y `%` el residuo.""",
      """Escribe `fn tiempo_bloqueo(segundos: u32) -> (u32, u32)` que convierta segundos de bloqueo de una cuenta en
`(minutos, segundos_restantes)`. Ej.: 125 → (2, 5).""",
      """fn tiempo_bloqueo(segundos: u32) -> (u32, u32) {
    todo!()
}

fn main() {
    println!("{:?}", tiempo_bloqueo(125));
}""",
      """fn tiempo_bloqueo(segundos: u32) -> (u32, u32) {
    (segundos / 60, segundos % 60)
}

fn main() {
    println!("{:?}", tiempo_bloqueo(125));
}""",
      """#[test] fn ciento_veinticinco() { assert_eq!(tiempo_bloqueo(125), (2, 5)); }
#[test] fn cero() { assert_eq!(tiempo_bloqueo(0), (0, 0)); }
#[test] fn una_hora() { assert_eq!(tiempo_bloqueo(3600), (60, 0)); }
#[test] fn menos_de_un_minuto() { assert_eq!(tiempo_bloqueo(59), (0, 59)); }""",
      ["Minutos = segundos / 60.", "Lo que sobra = segundos % 60. Devuelve `(a, b)` sin punto y coma."]),
    M("rs0_3", "Overflow: el bug que Rust no perdona",
      """En C, sumar `250 + 10` en un byte da **4** en silencio: así nacen muchas vulnerabilidades (buffers mal calculados).
En Rust, en modo debug eso **truena** (panic). Para controlarlo: `a.checked_add(b)` devuelve `Option<u8>` (`None` si se desborda)
y `a.saturating_add(b)` se queda en el máximo (255).""",
      """1. `fn sumar_seguro(a: u8, b: u8) -> Option<u8>`: la suma o `None` si se desborda.
2. `fn sumar_tope(a: u8, b: u8) -> u8`: la suma, pero sin pasar de 255.""",
      """fn sumar_seguro(a: u8, b: u8) -> Option<u8> {
    todo!()
}

fn sumar_tope(a: u8, b: u8) -> u8 {
    todo!()
}

fn main() {
    println!("{:?} {}", sumar_seguro(250, 10), sumar_tope(250, 10));
}""",
      """fn sumar_seguro(a: u8, b: u8) -> Option<u8> {
    a.checked_add(b)
}

fn sumar_tope(a: u8, b: u8) -> u8 {
    a.saturating_add(b)
}

fn main() {
    println!("{:?} {}", sumar_seguro(250, 10), sumar_tope(250, 10));
}""",
      """#[test] fn suma_normal() { assert_eq!(sumar_seguro(100, 55), Some(155)); }
#[test] fn desborde_detectado() { assert_eq!(sumar_seguro(250, 10), None); }
#[test] fn justo_255() { assert_eq!(sumar_seguro(200, 55), Some(255)); }
#[test] fn tope_no_pasa_de_255() { assert_eq!(sumar_tope(250, 10), 255); }
#[test] fn tope_suma_normal() { assert_eq!(sumar_tope(1, 2), 3); }""",
      ["Los enteros traen métodos: escribe `a.` y busca `checked_add`.", "`a.checked_add(b)` y `a.saturating_add(b)`."]),
    M("rs0_4", "match con rangos de puertos",
      """`match` compara un valor contra patrones, y obliga a cubrir **todos** los casos. Acepta rangos: `0..=1023 => ...`.
`_` atrapa todo lo demás. Un texto fijo es `&'static str`.""",
      """`fn clasificar_puerto(p: u16) -> &'static str`:
- 0 a 1023 → `"bien conocido"`
- 1024 a 49151 → `"registrado"`
- el resto → `"dinamico"`""",
      """fn clasificar_puerto(p: u16) -> &'static str {
    todo!()
}

fn main() {
    println!("{}", clasificar_puerto(22));
}""",
      """fn clasificar_puerto(p: u16) -> &'static str {
    match p {
        0..=1023 => "bien conocido",
        1024..=49151 => "registrado",
        _ => "dinamico",
    }
}

fn main() {
    println!("{}", clasificar_puerto(22));
}""",
      """#[test] fn ssh() { assert_eq!(clasificar_puerto(22), "bien conocido"); }
#[test] fn borde_1023() { assert_eq!(clasificar_puerto(1023), "bien conocido"); }
#[test] fn borde_1024() { assert_eq!(clasificar_puerto(1024), "registrado"); }
#[test] fn rdp() { assert_eq!(clasificar_puerto(3389), "registrado"); }
#[test] fn efimero() { assert_eq!(clasificar_puerto(51000), "dinamico"); }""",
      ["`match p { 0..=1023 => \"bien conocido\", ... }`", "El último brazo es `_ => \"dinamico\"`."],
      requiere=[(r"\bmatch\b", "Resuélvelo con `match`")]),
    M("rs0_5", "JEFE: calculadora de subred",
      """Combina todo: `if`, operaciones de bits y tipos. `1u32 << n` vale 2ⁿ. Ojo: `1u32 << 32` truena (overflow del shift),
por eso /0 se trata aparte. Recuerda del CCNA: hosts útiles = 2^(32-prefijo) − 2, salvo /31 (2, enlaces punto a punto) y /32 (1).""",
      """`fn hosts_utiles(prefijo: u8) -> u64` para prefijos 0 a 32. Ej.: /24 → 254, /30 → 2, /31 → 2, /32 → 1, /0 → 4294967294.""",
      """fn hosts_utiles(prefijo: u8) -> u64 {
    todo!()
}

fn main() {
    println!("{}", hosts_utiles(24));
}""",
      """fn hosts_utiles(prefijo: u8) -> u64 {
    match prefijo {
        32 => 1,
        31 => 2,
        p => (1u64 << (32 - p as u64)) - 2,
    }
}

fn main() {
    println!("{}", hosts_utiles(24));
}""",
      """#[test] fn barra_24() { assert_eq!(hosts_utiles(24), 254); }
#[test] fn barra_30() { assert_eq!(hosts_utiles(30), 2); }
#[test] fn barra_31_punto_a_punto() { assert_eq!(hosts_utiles(31), 2); }
#[test] fn barra_32_host() { assert_eq!(hosts_utiles(32), 1); }
#[test] fn barra_26() { assert_eq!(hosts_utiles(26), 62); }
#[test] fn barra_0_toda_internet() { assert_eq!(hosts_utiles(0), 4294967294); }""",
      ["Trabaja en u64 para que /0 quepa.", "`(1u64 << (32 - prefijo as u64)) - 2` y casos aparte para 31 y 32."], jefe=True),
  ]},
  {"nombre": "Ownership y préstamos", "cap": "Rust Book cap. 4", "misiones": [
    M("rs1_1", "El valor se movió",
      """Cada valor tiene **un dueño**. `let b = a;` con un `String` **mueve** el dato: `a` ya no sirve. Así Rust evita el
*double free* y el *use-after-free* de C sin recolector de basura. Soluciones: prestar (`&a`) o copiar (`a.clone()`).""",
      """Este programa no compila. Arréglalo (sin borrar ningún `println!`) para que imprima:
```
10.0.0.1 10.0.0.1
```""",
      """fn main() {
    let ip = String::from("10.0.0.1");
    let copia = ip;
    println!("{} {}", ip, copia);
}""",
      """fn main() {
    let ip = String::from("10.0.0.1");
    let copia = ip.clone();
    println!("{} {}", ip, copia);
}""",
      "", ["Lee el error del compilador: dice *value borrowed here after move*.", "Cambia `let copia = ip;` por `ip.clone()` o por `&ip`."],
      modo="salida", salida="10.0.0.1 10.0.0.1"),
    M("rs1_2", "Préstamos & y &mut",
      """`&T` presta para **leer** (puede haber muchos a la vez). `&mut T` presta para **modificar** (solo uno a la vez y sin lectores).
Esa regla elimina las *data races* en tiempo de compilación.""",
      """1. `fn contar_puntos(ip: &str) -> usize`: cuántos `.` tiene el texto.
2. `fn agregar_puerto(destino: &mut String, puerto: u16)`: agrega `:puerto` al final. Ej.: "10.0.0.1" → "10.0.0.1:22".""",
      """fn contar_puntos(ip: &str) -> usize {
    todo!()
}

fn agregar_puerto(destino: &mut String, puerto: u16) {
    todo!()
}

fn main() {
    let mut d = String::from("10.0.0.1");
    agregar_puerto(&mut d, 22);
    println!("{} {}", contar_puntos(&d), d);
}""",
      """fn contar_puntos(ip: &str) -> usize {
    ip.chars().filter(|c| *c == '.').count()
}

fn agregar_puerto(destino: &mut String, puerto: u16) {
    destino.push_str(&format!(":{puerto}"));
}

fn main() {
    let mut d = String::from("10.0.0.1");
    agregar_puerto(&mut d, 22);
    println!("{} {}", contar_puntos(&d), d);
}""",
      """#[test] fn puntos_ipv4() { assert_eq!(contar_puntos("192.168.1.10"), 3); }
#[test] fn sin_puntos() { assert_eq!(contar_puntos("localhost"), 0); }
#[test] fn agrega_puerto() { let mut s = String::from("10.0.0.1"); agregar_puerto(&mut s, 22); assert_eq!(s, "10.0.0.1:22"); }
#[test] fn agrega_puerto_alto() { let mut s = String::from("srv"); agregar_puerto(&mut s, 8443); assert_eq!(s, "srv:8443"); }""",
      ["Recorre con `ip.chars()` y cuenta los que son '.'.", "`destino.push_str(&format!(\":{puerto}\"))`."]),
    M("rs1_3", "Slices: rebanadas sin copiar",
      """Un slice `&str` es una **vista** a parte de un texto, sin copiarlo: `&s[0..3]`. Como es un préstamo, el compilador
garantiza que el texto original sigue vivo mientras uses la rebanada.""",
      """`fn primer_octeto(ip: &str) -> &str`: devuelve lo que hay antes del primer `.`; si no hay punto, todo el texto.
Ej.: "192.168.0.1" → "192".""",
      """fn primer_octeto(ip: &str) -> &str {
    todo!()
}

fn main() {
    println!("{}", primer_octeto("192.168.0.1"));
}""",
      """fn primer_octeto(ip: &str) -> &str {
    match ip.find('.') {
        Some(i) => &ip[..i],
        None => ip,
    }
}

fn main() {
    println!("{}", primer_octeto("192.168.0.1"));
}""",
      """#[test] fn clase_c() { assert_eq!(primer_octeto("192.168.0.1"), "192"); }
#[test] fn clase_a() { assert_eq!(primer_octeto("10.1.2.3"), "10"); }
#[test] fn sin_punto() { assert_eq!(primer_octeto("localhost"), "localhost"); }""",
      ["`ip.find('.')` te da `Some(posición)` o `None`.", "Con la posición `i`, devuelve `&ip[..i]`."]),
    M("rs1_4", "JEFE: enmascarar datos personales",
      """En logs y reportes nunca debes exponer datos personales completos (privacidad / cumplimiento). Combina préstamos,
slices y `String` nuevos. `split_once('@')` divide en dos partes y devuelve `Option<(&str, &str)>`.""",
      """`fn enmascarar_correo(correo: &str) -> String`: deja la primera letra del usuario, luego `***`, y el dominio completo.
- "user@example.com" → "u***@example.com"
- si no hay `@` o el usuario está vacío → "***\"""",
      """fn enmascarar_correo(correo: &str) -> String {
    todo!()
}

fn main() {
    println!("{}", enmascarar_correo("user@example.com"));
}""",
      """fn enmascarar_correo(correo: &str) -> String {
    match correo.split_once('@') {
        Some((usuario, dominio)) if !usuario.is_empty() => {
            let primera = usuario.chars().next().unwrap();
            format!("{primera}***@{dominio}")
        }
        _ => String::from("***"),
    }
}

fn main() {
    println!("{}", enmascarar_correo("user@example.com"));
}""",
      """#[test] fn correo_normal() { assert_eq!(enmascarar_correo("user@example.com"), "u***@example.com"); }
#[test] fn usuario_de_una_letra() { assert_eq!(enmascarar_correo("a@x.mx"), "a***@x.mx"); }
#[test] fn sin_arroba() { assert_eq!(enmascarar_correo("no-es-correo"), "***"); }
#[test] fn usuario_vacio() { assert_eq!(enmascarar_correo("@dominio.com"), "***"); }""",
      ["`correo.split_once('@')` → `Some((usuario, dominio))`.", "La primera letra: `usuario.chars().next()`; arma con `format!`."], jefe=True),
  ]},
  {"nombre": "Structs, enums y match", "cap": "Rust Book cap. 5-6", "misiones": [
    M("rs2_1", "Struct Paquete",
      """Un `struct` agrupa datos con nombre. Sus métodos van en `impl`: `&self` lee el struct. `Self` es el propio tipo,
y por convención el constructor se llama `new` o `nuevo`.""",
      """Completa `impl Paquete` con:
1. `fn nuevo(origen: &str, destino: &str, puerto: u16) -> Self`
2. `fn es_web(&self) -> bool`: true si el puerto es 80 o 443.""",
      """struct Paquete {
    origen: String,
    destino: String,
    puerto: u16,
}

impl Paquete {
    // fn nuevo(...)
    // fn es_web(...)
}

fn main() {}""",
      """struct Paquete {
    origen: String,
    destino: String,
    puerto: u16,
}

impl Paquete {
    fn nuevo(origen: &str, destino: &str, puerto: u16) -> Self {
        Paquete { origen: origen.to_string(), destino: destino.to_string(), puerto }
    }

    fn es_web(&self) -> bool {
        self.puerto == 80 || self.puerto == 443
    }
}

fn main() {}""",
      """#[test] fn construye() { let p = Paquete::nuevo("10.0.0.5", "8.8.8.8", 53); assert_eq!(p.origen, "10.0.0.5"); assert_eq!(p.destino, "8.8.8.8"); assert_eq!(p.puerto, 53); }
#[test] fn https_es_web() { assert!(Paquete::nuevo("a", "b", 443).es_web()); }
#[test] fn http_es_web() { assert!(Paquete::nuevo("a", "b", 80).es_web()); }
#[test] fn dns_no_es_web() { assert!(!Paquete::nuevo("a", "b", 53).es_web()); }""",
      ["`Paquete { origen: origen.to_string(), ... }`", "`matches!(self.puerto, 80 | 443)` también funciona."]),
    M("rs2_2", "Enum Protocolo y Option",
      """Un `enum` es un valor que puede ser **una** de varias variantes. `Option<T>` es un enum de la librería estándar:
`Some(valor)` o `None`. Rust no tiene `null`: tienes que manejar el `None` sí o sí.""",
      """Con `enum Protocolo { Tcp, Udp, Icmp }`:
1. `fn desde_numero(n: u8) -> Option<Protocolo>`: 6 → Tcp, 17 → Udp, 1 → Icmp, otro → None (números del campo *Protocol* de IPv4).
2. `fn nombre(p: &Protocolo) -> &'static str`: "TCP", "UDP" o "ICMP".""",
      """enum Protocolo {
    Tcp,
    Udp,
    Icmp,
}

fn desde_numero(n: u8) -> Option<Protocolo> {
    todo!()
}

fn nombre(p: &Protocolo) -> &'static str {
    todo!()
}

fn main() {}""",
      """enum Protocolo {
    Tcp,
    Udp,
    Icmp,
}

fn desde_numero(n: u8) -> Option<Protocolo> {
    match n {
        6 => Some(Protocolo::Tcp),
        17 => Some(Protocolo::Udp),
        1 => Some(Protocolo::Icmp),
        _ => None,
    }
}

fn nombre(p: &Protocolo) -> &'static str {
    match p {
        Protocolo::Tcp => "TCP",
        Protocolo::Udp => "UDP",
        Protocolo::Icmp => "ICMP",
    }
}

fn main() {}""",
      """#[test] fn seis_es_tcp() { assert!(matches!(desde_numero(6), Some(Protocolo::Tcp))); }
#[test] fn diecisiete_es_udp() { assert!(matches!(desde_numero(17), Some(Protocolo::Udp))); }
#[test] fn uno_es_icmp() { assert!(matches!(desde_numero(1), Some(Protocolo::Icmp))); }
#[test] fn desconocido_es_none() { assert!(desde_numero(99).is_none()); }
#[test] fn nombres() { assert_eq!(nombre(&Protocolo::Tcp), "TCP"); assert_eq!(nombre(&Protocolo::Udp), "UDP"); assert_eq!(nombre(&Protocolo::Icmp), "ICMP"); }""",
      ["`6 => Some(Protocolo::Tcp)`.", "En `nombre` haz `match p { Protocolo::Tcp => \"TCP\", ... }`."]),
    M("rs2_3", "Enums con datos: eventos del SIEM",
      """Las variantes de un enum pueden llevar datos: `Login { usuario: String, ok: bool }`, `Malware(String)`.
`match` los destapa y además puede llevar condiciones (*guards*): `Evento::Escaneo { puertos } if puertos > 100 => ...`.""",
      """`fn severidad(e: &Evento) -> u8`:
- Login exitoso → 0 · Login fallido → 3
- Escaneo de más de 100 puertos → 7, si no → 4
- Malware → 10""",
      """enum Evento {
    Login { usuario: String, ok: bool },
    Escaneo { puertos: u32 },
    Malware(String),
}

fn severidad(e: &Evento) -> u8 {
    todo!()
}

fn main() {}""",
      """enum Evento {
    Login { usuario: String, ok: bool },
    Escaneo { puertos: u32 },
    Malware(String),
}

fn severidad(e: &Evento) -> u8 {
    match e {
        Evento::Login { ok: true, .. } => 0,
        Evento::Login { ok: false, .. } => 3,
        Evento::Escaneo { puertos } if *puertos > 100 => 7,
        Evento::Escaneo { .. } => 4,
        Evento::Malware(_) => 10,
    }
}

fn main() {}""",
      """#[test] fn login_ok() { assert_eq!(severidad(&Evento::Login { usuario: "ana".into(), ok: true }), 0); }
#[test] fn login_fallido() { assert_eq!(severidad(&Evento::Login { usuario: "root".into(), ok: false }), 3); }
#[test] fn escaneo_grande() { assert_eq!(severidad(&Evento::Escaneo { puertos: 1000 }), 7); }
#[test] fn escaneo_chico() { assert_eq!(severidad(&Evento::Escaneo { puertos: 100 }), 4); }
#[test] fn malware() { assert_eq!(severidad(&Evento::Malware("emotet".into())), 10); }""",
      ["`Evento::Login { ok: true, .. } => 0`.", "Guard: `Evento::Escaneo { puertos } if *puertos > 100 => 7`."]),
    M("rs2_4", "JEFE: el firewall",
      """Un firewall (como una ACL de Cisco) revisa las reglas **en orden** y la primera que coincide decide.
Si ninguna coincide: **deny implícito**. `for r in reglas` recorre un slice; `return` sale antes.""",
      """`fn decidir(reglas: &[Regla], puerto: u16) -> bool`: true = permitir. La primera regla con ese puerto gana.
Sin coincidencia → false. Un `puerto: 0` en una regla significa **cualquier puerto**.""",
      """struct Regla {
    puerto: u16,
    permitir: bool,
}

fn decidir(reglas: &[Regla], puerto: u16) -> bool {
    todo!()
}

fn main() {}""",
      """struct Regla {
    puerto: u16,
    permitir: bool,
}

fn decidir(reglas: &[Regla], puerto: u16) -> bool {
    for r in reglas {
        if r.puerto == puerto || r.puerto == 0 {
            return r.permitir;
        }
    }
    false
}

fn main() {}""",
      """fn r(p: u16, ok: bool) -> Regla { Regla { puerto: p, permitir: ok } }
#[test] fn permite_https() { assert!(decidir(&[r(443, true)], 443)); }
#[test] fn deny_implicito() { assert!(!decidir(&[r(443, true)], 22)); }
#[test] fn primera_gana() { assert!(!decidir(&[r(22, false), r(22, true)], 22)); }
#[test] fn cualquiera() { assert!(decidir(&[r(23, false), r(0, true)], 8080)); assert!(!decidir(&[r(23, false), r(0, true)], 23)); }
#[test] fn sin_reglas() { assert!(!decidir(&[], 80)); }""",
      ["Recorre con `for r in reglas` y `return r.permitir` en cuanto coincida.", "Coincide si `r.puerto == puerto || r.puerto == 0`; al final `false`."], jefe=True),
  ]},
  {"nombre": "Colecciones y errores", "cap": "Rust Book cap. 8-9", "misiones": [
    M("rs3_1", "Vec: puertos abiertos",
      """`Vec<T>` es una lista que crece. `v.push(x)` agrega, `v.sort()` ordena. Un slice de tuplas `&[(u16, bool)]` se recorre
con `for &(puerto, abierto) in lista`.""",
      """`fn puertos_abiertos(resultado: &[(u16, bool)]) -> Vec<u16>`: los puertos con `true`, ordenados de menor a mayor.""",
      """fn puertos_abiertos(resultado: &[(u16, bool)]) -> Vec<u16> {
    todo!()
}

fn main() {
    println!("{:?}", puertos_abiertos(&[(443, true), (22, true), (23, false)]));
}""",
      """fn puertos_abiertos(resultado: &[(u16, bool)]) -> Vec<u16> {
    let mut v = Vec::new();
    for &(p, abierto) in resultado {
        if abierto {
            v.push(p);
        }
    }
    v.sort();
    v
}

fn main() {
    println!("{:?}", puertos_abiertos(&[(443, true), (22, true), (23, false)]));
}""",
      """#[test] fn ordenados() { assert_eq!(puertos_abiertos(&[(443, true), (22, true), (23, false)]), vec![22, 443]); }
#[test] fn ninguno() { assert_eq!(puertos_abiertos(&[(21, false)]), Vec::<u16>::new()); }
#[test] fn vacio() { assert_eq!(puertos_abiertos(&[]), Vec::<u16>::new()); }""",
      ["`let mut v = Vec::new();` y `v.push(p)` si está abierto.", "No olvides `v.sort();` antes de devolver `v`."]),
    M("rs3_2", "HashMap: ¿quién hace más ruido?",
      """`HashMap<K, V>` guarda pares clave → valor. El truco para contar: `*mapa.entry(clave).or_insert(0) += 1;`.
Se importa con `use std::collections::HashMap;`.""",
      """`fn contar_ips(lineas: &[&str]) -> HashMap<String, usize>`: cada línea de log empieza con la IP seguida de un espacio.
Cuenta cuántas líneas tiene cada IP. Ignora líneas vacías.""",
      """use std::collections::HashMap;

fn contar_ips(lineas: &[&str]) -> HashMap<String, usize> {
    todo!()
}

fn main() {}""",
      """use std::collections::HashMap;

fn contar_ips(lineas: &[&str]) -> HashMap<String, usize> {
    let mut mapa = HashMap::new();
    for linea in lineas {
        if let Some(ip) = linea.split_whitespace().next() {
            *mapa.entry(ip.to_string()).or_insert(0) += 1;
        }
    }
    mapa
}

fn main() {}""",
      """#[test] fn cuenta() { let m = contar_ips(&["1.1.1.1 GET /", "2.2.2.2 GET /a", "1.1.1.1 POST /login"]); assert_eq!(m["1.1.1.1"], 2); assert_eq!(m["2.2.2.2"], 1); assert_eq!(m.len(), 2); }
#[test] fn ignora_vacias() { let m = contar_ips(&["", "9.9.9.9 x"]); assert_eq!(m.len(), 1); }""",
      ["La IP es `linea.split_whitespace().next()` (un Option).", "`*mapa.entry(ip.to_string()).or_insert(0) += 1;`"]),
    M("rs3_3", "Result: validar entradas",
      """Rust no usa excepciones: una función que puede fallar devuelve `Result<T, E>` → `Ok(valor)` o `Err(error)`.
**Nunca confíes en la entrada del usuario**: valídala. `"80".parse::<u16>()` devuelve un `Result`.""",
      """`fn parsear_puerto(s: &str) -> Result<u16, String>`:
- quita espacios (`trim`); vacío → `Err("vacio")`
- no es número válido de 16 bits → `Err` (el mensaje que quieras)
- 0 → `Err("puerto 0 no valido")`
- si todo bien → `Ok(puerto)`""",
      """fn parsear_puerto(s: &str) -> Result<u16, String> {
    todo!()
}

fn main() {
    println!("{:?}", parsear_puerto(" 8080 "));
}""",
      """fn parsear_puerto(s: &str) -> Result<u16, String> {
    let s = s.trim();
    if s.is_empty() {
        return Err("vacio".to_string());
    }
    let p: u16 = s.parse().map_err(|_| format!("'{s}' no es un puerto"))?;
    if p == 0 {
        return Err("puerto 0 no valido".to_string());
    }
    Ok(p)
}

fn main() {
    println!("{:?}", parsear_puerto(" 8080 "));
}""",
      """#[test] fn valido_con_espacios() { assert_eq!(parsear_puerto(" 8080 "), Ok(8080)); }
#[test] fn vacio() { assert_eq!(parsear_puerto("   "), Err("vacio".to_string())); }
#[test] fn letras() { assert!(parsear_puerto("http").is_err()); }
#[test] fn muy_grande() { assert!(parsear_puerto("70000").is_err()); }
#[test] fn negativo() { assert!(parsear_puerto("-1").is_err()); }
#[test] fn cero() { assert_eq!(parsear_puerto("0"), Err("puerto 0 no valido".to_string())); }""",
      ["Empieza con `let s = s.trim();`.", "`s.parse::<u16>()` y conviértelo con `.map_err(|_| ...)`."]),
    M("rs3_4", "El operador ?: parsear IPv4",
      """`?` al final de un `Result` significa: si es `Err`, regresa ese error ya; si es `Ok`, dame el valor.
Hace el manejo de errores corto sin esconderlo. Un arreglo fijo se escribe `[u8; 4]`.""",
      """`fn parsear_ipv4(s: &str) -> Result<[u8; 4], String>`: exactamente 4 partes separadas por `.`, cada una un número 0-255.
"192.168.1.1" → `Ok([192,168,1,1])`; "1.2.3", "1.2.3.4.5", "1.2.3.256", "a.b.c.d" → `Err`.""",
      """fn parsear_ipv4(s: &str) -> Result<[u8; 4], String> {
    todo!()
}

fn main() {
    println!("{:?}", parsear_ipv4("192.168.1.1"));
}""",
      """fn parsear_ipv4(s: &str) -> Result<[u8; 4], String> {
    let partes: Vec<&str> = s.split('.').collect();
    if partes.len() != 4 {
        return Err(format!("se esperaban 4 octetos y hay {}", partes.len()));
    }
    let mut ip = [0u8; 4];
    for (i, p) in partes.iter().enumerate() {
        ip[i] = p.parse::<u8>().map_err(|_| format!("octeto inválido: {p}"))?;
    }
    Ok(ip)
}

fn main() {
    println!("{:?}", parsear_ipv4("192.168.1.1"));
}""",
      """#[test] fn valida() { assert_eq!(parsear_ipv4("192.168.1.1"), Ok([192, 168, 1, 1])); }
#[test] fn ceros() { assert_eq!(parsear_ipv4("0.0.0.0"), Ok([0, 0, 0, 0])); }
#[test] fn faltan_octetos() { assert!(parsear_ipv4("1.2.3").is_err()); }
#[test] fn sobran_octetos() { assert!(parsear_ipv4("1.2.3.4.5").is_err()); }
#[test] fn octeto_256() { assert!(parsear_ipv4("1.2.3.256").is_err()); }
#[test] fn letras() { assert!(parsear_ipv4("a.b.c.d").is_err()); }
#[test] fn vacio() { assert!(parsear_ipv4("").is_err()); }""",
      ["`s.split('.').collect::<Vec<&str>>()` y revisa que sean 4.", "Dentro del for: `ip[i] = p.parse::<u8>().map_err(|_| ...)?;`"],
      requiere=[(r"\?\s*;", "Usa el operador `?`")]),
    M("rs3_5", "JEFE: detector de fuerza bruta SSH",
      """Esto es trabajo real de SOC: buscar en `/var/log/auth.log` las IPs con muchos intentos fallidos.
Las líneas se ven así: `Failed password for root from 203.0.113.9 port 4242 ssh2`.""",
      """`fn sospechosos(log: &str, umbral: usize) -> Vec<String>`: de las líneas que contienen `Failed password`, toma la IP que va
después de `from ` y cuenta. Devuelve las IPs con **umbral o más** fallos, ordenadas.""",
      """use std::collections::HashMap;

fn sospechosos(log: &str, umbral: usize) -> Vec<String> {
    todo!()
}

fn main() {}""",
      """use std::collections::HashMap;

fn sospechosos(log: &str, umbral: usize) -> Vec<String> {
    let mut cuenta: HashMap<&str, usize> = HashMap::new();
    for linea in log.lines().filter(|l| l.contains("Failed password")) {
        if let Some((_, resto)) = linea.split_once("from ") {
            if let Some(ip) = resto.split_whitespace().next() {
                *cuenta.entry(ip).or_insert(0) += 1;
            }
        }
    }
    let mut v: Vec<String> = cuenta.into_iter().filter(|(_, n)| *n >= umbral).map(|(ip, _)| ip.to_string()).collect();
    v.sort();
    v
}

fn main() {}""",
      """const LOG: &str = "Nov 14 10:00:01 srv sshd[1]: Failed password for root from 203.0.113.9 port 4242 ssh2
Nov 14 10:00:02 srv sshd[1]: Failed password for root from 203.0.113.9 port 4243 ssh2
Nov 14 10:00:03 srv sshd[1]: Accepted password for ana from 10.0.0.5 port 5000 ssh2
Nov 14 10:00:04 srv sshd[1]: Failed password for invalid user admin from 198.51.100.7 port 1 ssh2
Nov 14 10:00:05 srv sshd[1]: Failed password for root from 203.0.113.9 port 4244 ssh2
Nov 14 10:00:06 srv sshd[1]: Failed password for root from 198.51.100.7 port 2 ssh2";
#[test] fn umbral_3() { assert_eq!(sospechosos(LOG, 3), vec!["203.0.113.9".to_string()]); }
#[test] fn umbral_2_ordenado() { assert_eq!(sospechosos(LOG, 2), vec!["198.51.100.7".to_string(), "203.0.113.9".to_string()]); }
#[test] fn exitosos_no_cuentan() { assert!(!sospechosos(LOG, 1).contains(&"10.0.0.5".to_string())); }
#[test] fn log_vacio() { assert!(sospechosos("", 1).is_empty()); }""",
      ["`log.lines()` y quédate con las que `contains(\"Failed password\")`.", "`linea.split_once(\"from \")` → la IP es la primera palabra de lo que queda."], jefe=True),
  ]},
  {"nombre": "Genéricos, traits y lifetimes", "cap": "Rust Book cap. 10", "misiones": [
    M("rs4_1", "Traits: detectores intercambiables",
      """Un `trait` es un contrato: "todo lo que implemente `Detector` sabe `analiza`". Con `fn f<D: Detector>(d: &D)` la función
sirve para **cualquier** detector (genéricos, sin costo en tiempo de ejecución).""",
      """1. Implementa `Detector` para `PalabraClave`: dispara si la línea contiene la palabra (sin importar mayúsculas).
2. `fn cuantas<D: Detector>(d: &D, lineas: &[&str]) -> usize`: cuántas líneas disparan.""",
      """trait Detector {
    fn analiza(&self, linea: &str) -> bool;
}

struct PalabraClave {
    palabra: String,
}

// impl Detector for PalabraClave { ... }

fn cuantas<D: Detector>(d: &D, lineas: &[&str]) -> usize {
    todo!()
}

fn main() {}""",
      """trait Detector {
    fn analiza(&self, linea: &str) -> bool;
}

struct PalabraClave {
    palabra: String,
}

impl Detector for PalabraClave {
    fn analiza(&self, linea: &str) -> bool {
        linea.to_lowercase().contains(&self.palabra.to_lowercase())
    }
}

fn cuantas<D: Detector>(d: &D, lineas: &[&str]) -> usize {
    lineas.iter().filter(|l| d.analiza(l)).count()
}

fn main() {}""",
      """#[test] fn dispara() { let d = PalabraClave { palabra: "mimikatz".into() }; assert!(d.analiza("proceso MIMIKATZ.exe iniciado")); }
#[test] fn no_dispara() { let d = PalabraClave { palabra: "mimikatz".into() }; assert!(!d.analiza("notepad.exe")); }
#[test] fn cuenta() { let d = PalabraClave { palabra: "sqlmap".into() }; assert_eq!(cuantas(&d, &["UA: sqlmap/1.7", "UA: Mozilla", "UA: SQLMap"]), 2); }""",
      ["`impl Detector for PalabraClave { fn analiza(&self, linea: &str) -> bool { ... } }`", "Pasa ambos a minúsculas con `to_lowercase()` antes del `contains`."],
      requiere=[(r"impl\s+Detector\s+for\s+PalabraClave", "Implementa el trait con `impl Detector for PalabraClave`")]),
    M("rs4_2", "Genéricos: el máximo de lo que sea",
      """`fn maximo<T: PartialOrd + Copy>(v: &[T]) -> Option<T>` funciona igual con u16, f64, char…
Los *trait bounds* (`PartialOrd + Copy`) dicen qué necesita el tipo: poder compararse y copiarse.""",
      """Implementa `maximo`: el valor más grande del slice, o `None` si está vacío. Sin usar `.max()` de iteradores.""",
      """fn maximo<T: PartialOrd + Copy>(v: &[T]) -> Option<T> {
    todo!()
}

fn main() {
    println!("{:?}", maximo(&[22u16, 443, 80]));
}""",
      """fn maximo<T: PartialOrd + Copy>(v: &[T]) -> Option<T> {
    let mut mejor = *v.first()?;
    for &x in v {
        if x > mejor {
            mejor = x;
        }
    }
    Some(mejor)
}

fn main() {
    println!("{:?}", maximo(&[22u16, 443, 80]));
}""",
      """#[test] fn puertos() { assert_eq!(maximo(&[22u16, 443, 80]), Some(443)); }
#[test] fn flotantes() { assert_eq!(maximo(&[0.5f64, 9.75, 3.0]), Some(9.75)); }
#[test] fn letras() { assert_eq!(maximo(&['a', 'z', 'm']), Some('z')); }
#[test] fn vacio() { assert_eq!(maximo::<u8>(&[]), None); }""",
      ["Empieza con el primero: `let mut mejor = *v.first()?;`", "Recorre y si `x > mejor` lo reemplazas."], prohibido=[(r"\.max\(", "Sin `.max()`: hazlo tú")]),
    M("rs4_3", "Lifetimes: referencias que no mueren antes",
      """Un *lifetime* (`'a`) le dice al compilador cuánto vive una referencia. Si una función devuelve un `&str` que sale de sus
parámetros, hay que decir de cuál: `fn f<'a>(linea: &'a str) -> &'a str`. Así es **imposible** devolver un puntero colgante.""",
      """1. `fn mas_largo<'a>(a: &'a str, b: &'a str) -> &'a str` (en empate, `a`).
2. `fn campo<'a>(linea: &'a str, n: usize) -> Option<&'a str>`: la palabra número `n` (desde 0) de la línea.""",
      """fn mas_largo(a: &str, b: &str) -> &str {
    todo!()
}

fn campo(linea: &str, n: usize) -> Option<&str> {
    todo!()
}

fn main() {}""",
      """fn mas_largo<'a>(a: &'a str, b: &'a str) -> &'a str {
    if b.len() > a.len() { b } else { a }
}

fn campo<'a>(linea: &'a str, n: usize) -> Option<&'a str> {
    linea.split_whitespace().nth(n)
}

fn main() {}""",
      """#[test] fn largo() { assert_eq!(mas_largo("ssh", "telnet"), "telnet"); }
#[test] fn empate() { assert_eq!(mas_largo("abc", "xyz"), "abc"); }
#[test] fn tercer_campo() { assert_eq!(campo("DROP IN=eth0 SRC=1.2.3.4", 2), Some("SRC=1.2.3.4")); }
#[test] fn fuera_de_rango() { assert_eq!(campo("a b", 5), None); }""",
      ["El primero no compila sin `<'a>`: lee el error *missing lifetime specifier*.", "`campo`: `linea.split_whitespace().nth(n)`."],
      requiere=[(r"'a", "Declara el lifetime `'a`")]),
    M("rs4_4", "JEFE: motor de reglas con dyn Trait",
      """`Box<dyn Detector>` permite guardar detectores **distintos** en un mismo `Vec` (despacho dinámico). Así funcionan
los motores tipo Snort/Suricata/Sigma: una lista de reglas heterogéneas sobre cada evento.""",
      """Implementa `Detector` para `PalabraClave` y para `Largo { max: usize }` (dispara si la línea mide más de `max`, típico
de payloads de overflow), y `fn alertas(dets: &[Box<dyn Detector>], linea: &str) -> Vec<String>` con el `nombre()` de los
que disparan, en orden.""",
      """trait Detector {
    fn nombre(&self) -> String;
    fn analiza(&self, linea: &str) -> bool;
}

struct PalabraClave {
    palabra: String,
}

struct Largo {
    max: usize,
}

fn alertas(dets: &[Box<dyn Detector>], linea: &str) -> Vec<String> {
    todo!()
}

fn main() {}""",
      """trait Detector {
    fn nombre(&self) -> String;
    fn analiza(&self, linea: &str) -> bool;
}

struct PalabraClave {
    palabra: String,
}

struct Largo {
    max: usize,
}

impl Detector for PalabraClave {
    fn nombre(&self) -> String {
        format!("palabra:{}", self.palabra)
    }
    fn analiza(&self, linea: &str) -> bool {
        linea.contains(&self.palabra)
    }
}

impl Detector for Largo {
    fn nombre(&self) -> String {
        format!("largo>{}", self.max)
    }
    fn analiza(&self, linea: &str) -> bool {
        linea.len() > self.max
    }
}

fn alertas(dets: &[Box<dyn Detector>], linea: &str) -> Vec<String> {
    dets.iter().filter(|d| d.analiza(linea)).map(|d| d.nombre()).collect()
}

fn main() {}""",
      """fn reglas() -> Vec<Box<dyn Detector>> { vec![Box::new(PalabraClave { palabra: "../".into() }), Box::new(Largo { max: 30 })] }
#[test] fn path_traversal() { assert_eq!(alertas(&reglas(), "GET /../../etc/passwd").len(), 1); }
#[test] fn ambas() { assert_eq!(alertas(&reglas(), "GET /../../../../etc/shadow HTTP/1.1").len(), 2); }
#[test] fn limpio() { assert!(alertas(&reglas(), "GET /").is_empty()); }
#[test] fn largo_solo() { let r = alertas(&reglas(), &"A".repeat(50)); assert_eq!(r.len(), 1); }""",
      ["Dos bloques: `impl Detector for PalabraClave` y `impl Detector for Largo`.", "`dets.iter().filter(|d| d.analiza(linea)).map(|d| d.nombre()).collect()`"], jefe=True),
  ]},
  {"nombre": "Iteradores y closures", "cap": "Rust Book cap. 13", "misiones": [
    M("rs5_1", "map + sum",
      """Los iteradores encadenan pasos sin bucles a mano: `v.iter().map(|x| ...).sum::<u32>()`.
Un *closure* `|x| x.1` es una función anónima. Son igual de rápidos que un `for` (*zero-cost abstractions*).""",
      """`fn bytes_totales(flujos: &[(String, u32)]) -> u32`: suma los bytes (segundo campo). **Sin `for`.**""",
      """fn bytes_totales(flujos: &[(String, u32)]) -> u32 {
    todo!()
}

fn main() {}""",
      """fn bytes_totales(flujos: &[(String, u32)]) -> u32 {
    flujos.iter().map(|f| f.1).sum()
}

fn main() {}""",
      """#[test] fn suma() { assert_eq!(bytes_totales(&[("a".into(), 100), ("b".into(), 250)]), 350); }
#[test] fn vacio() { assert_eq!(bytes_totales(&[]), 0); }""",
      ["`flujos.iter()` te da cada tupla.", "`.map(|f| f.1).sum()`"], prohibido=[(r"\bfor\b", "Hazlo sin `for`: usa iteradores")]),
    M("rs5_2", "filter_map, collect y dedup",
      """`filter_map` transforma y descarta los `None` en un paso. `collect()` junta el resultado en un `Vec`.
`sort()` + `dedup()` quita repetidos.""",
      """`fn ips_unicas(lineas: &[&str]) -> Vec<String>`: de líneas tipo `SRC=1.2.3.4 DST=...`, saca la IP después de `SRC=`
(hasta el espacio). Líneas sin `SRC=` se ignoran. Devuelve las únicas, ordenadas. **Sin `for`.**""",
      """fn ips_unicas(lineas: &[&str]) -> Vec<String> {
    todo!()
}

fn main() {}""",
      """fn ips_unicas(lineas: &[&str]) -> Vec<String> {
    let mut v: Vec<String> = lineas
        .iter()
        .filter_map(|l| l.split_once("SRC="))
        .filter_map(|(_, resto)| resto.split_whitespace().next())
        .map(|s| s.to_string())
        .collect();
    v.sort();
    v.dedup();
    v
}

fn main() {}""",
      """#[test] fn unicas() { assert_eq!(ips_unicas(&["SRC=9.9.9.9 DST=1", "x", "SRC=1.1.1.1 DST=2", "SRC=9.9.9.9 DST=3"]), vec!["1.1.1.1".to_string(), "9.9.9.9".to_string()]); }
#[test] fn ninguna() { assert!(ips_unicas(&["hola"]).is_empty()); }""",
      ["`.filter_map(|l| l.split_once(\"SRC=\"))` te deja `(antes, resto)`.", "Luego la primera palabra de `resto`, `collect`, `sort`, `dedup`."],
      prohibido=[(r"\bfor\b", "Hazlo sin `for`")]),
    M("rs5_3", "Closures que capturan",
      """Un closure puede **capturar** variables de su entorno. Una función puede devolver uno: `-> impl Fn(&T) -> bool`.
Con `move` el closure se lleva la variable consigo.""",
      """`fn filtro_puerto(p: u16) -> impl Fn(&(String, u16)) -> bool`: devuelve un filtro que acepta las conexiones a ese puerto.
Se usará así: `conexiones.iter().filter(|c| f(c))`.""",
      """fn filtro_puerto(p: u16) -> impl Fn(&(String, u16)) -> bool {
    todo!()
}

fn main() {}""",
      """fn filtro_puerto(p: u16) -> impl Fn(&(String, u16)) -> bool {
    move |c| c.1 == p
}

fn main() {}""",
      """#[test] fn filtra() { let f = filtro_puerto(3389); let c = vec![("a".to_string(), 3389u16), ("b".to_string(), 22), ("c".to_string(), 3389)]; assert_eq!(c.iter().filter(|x| f(x)).count(), 2); }
#[test] fn otro_puerto() { let f = filtro_puerto(22); assert!(f(&("x".to_string(), 22))); assert!(!f(&("x".to_string(), 23))); }""",
      ["Devuelve un closure: `move |c| ...`.", "`move |c| c.1 == p`"]),
    M("rs5_4", "JEFE: top de atacantes",
      """Ordenar por varios criterios: `v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)))` (cuenta descendente y, si empatan,
IP ascendente). `truncate(n)` deja solo los primeros n.""",
      """`fn top_atacantes(log: &str, n: usize) -> Vec<(String, usize)>`: cuenta las líneas `DROP` por `SRC=` y devuelve las `n`
IPs con más bloqueos (más bloqueos primero; empate → IP menor primero). Líneas que no empiezan con `DROP` no cuentan.""",
      """use std::collections::HashMap;

fn top_atacantes(log: &str, n: usize) -> Vec<(String, usize)> {
    todo!()
}

fn main() {}""",
      """use std::collections::HashMap;

fn top_atacantes(log: &str, n: usize) -> Vec<(String, usize)> {
    let mut cuenta: HashMap<String, usize> = HashMap::new();
    log.lines()
        .filter(|l| l.starts_with("DROP"))
        .filter_map(|l| l.split_once("SRC="))
        .filter_map(|(_, r)| r.split_whitespace().next())
        .for_each(|ip| *cuenta.entry(ip.to_string()).or_insert(0) += 1);
    let mut v: Vec<(String, usize)> = cuenta.into_iter().collect();
    v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    v.truncate(n);
    v
}

fn main() {}""",
      """const LOG: &str = "DROP IN=eth0 SRC=5.5.5.5 DST=10.0.0.1
ACCEPT IN=eth0 SRC=5.5.5.5 DST=10.0.0.1
DROP IN=eth0 SRC=1.1.1.1 DST=10.0.0.1
DROP IN=eth0 SRC=5.5.5.5 DST=10.0.0.2
DROP IN=eth0 SRC=2.2.2.2 DST=10.0.0.1
DROP IN=eth0 SRC=2.2.2.2 DST=10.0.0.3";
#[test] fn top2() { assert_eq!(top_atacantes(LOG, 2), vec![("2.2.2.2".to_string(), 2), ("5.5.5.5".to_string(), 2)]); }
#[test] fn top_todos() { assert_eq!(top_atacantes(LOG, 10).len(), 3); assert_eq!(top_atacantes(LOG, 10)[2], ("1.1.1.1".to_string(), 1)); }
#[test] fn accept_no_cuenta() { assert_eq!(top_atacantes("ACCEPT SRC=9.9.9.9", 5), vec![]); }""",
      ["Cuenta con un HashMap como en el jefe de colecciones.", "`v.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)))` y `v.truncate(n)`."], jefe=True),
  ]},
  {"nombre": "Herramientas de seguridad", "cap": "Rust aplicado", "misiones": [
    M("rs6_1", "Hex: ver los bytes",
      """Los hashes, payloads y dumps de memoria se leen en hexadecimal. `format!("{:02x}", byte)` da 2 dígitos en minúscula.
`u8::from_str_radix("ff", 16)` hace lo contrario.""",
      """1. `fn a_hex(datos: &[u8]) -> String` → `[0xde, 0xad]` = "dead".
2. `fn de_hex(s: &str) -> Option<Vec<u8>>`: None si la longitud es impar o hay caracteres no hex.""",
      """fn a_hex(datos: &[u8]) -> String {
    todo!()
}

fn de_hex(s: &str) -> Option<Vec<u8>> {
    todo!()
}

fn main() {}""",
      """fn a_hex(datos: &[u8]) -> String {
    datos.iter().map(|b| format!("{:02x}", b)).collect()
}

fn de_hex(s: &str) -> Option<Vec<u8>> {
    if s.len() % 2 != 0 || !s.is_ascii() {
        return None;
    }
    (0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i + 2], 16).ok()).collect()
}

fn main() {}""",
      """#[test] fn dead_beef() { assert_eq!(a_hex(&[0xde, 0xad, 0xbe, 0xef]), "deadbeef"); }
#[test] fn ceros() { assert_eq!(a_hex(&[0, 1, 15]), "00010f"); }
#[test] fn ida_y_vuelta() { assert_eq!(de_hex("cafe00ff"), Some(vec![0xca, 0xfe, 0x00, 0xff])); }
#[test] fn impar() { assert_eq!(de_hex("abc"), None); }
#[test] fn no_hex() { assert_eq!(de_hex("zz"), None); }
#[test] fn mayusculas() { assert_eq!(de_hex("FF"), Some(vec![255])); }""",
      ["`a_hex`: `datos.iter().map(|b| format!(\"{:02x}\", b)).collect()`.", "`de_hex`: recorre de 2 en 2 con `step_by(2)` y `u8::from_str_radix(&s[i..i+2], 16)`."]),
    M("rs6_2", "Cifrado XOR",
      """XOR (`^`) con una clave es la base de muchos cifrados y de la ofuscación que usa el malware. Propiedad clave:
`(dato ^ k) ^ k == dato`, así que la misma función cifra y descifra. Con clave repetida es **débil** (se rompe con análisis).""",
      """`fn xor(datos: &[u8], clave: &[u8]) -> Vec<u8>`: aplica la clave repetida a lo largo de los datos. Clave vacía → datos sin cambio.""",
      """fn xor(datos: &[u8], clave: &[u8]) -> Vec<u8> {
    todo!()
}

fn main() {}""",
      """fn xor(datos: &[u8], clave: &[u8]) -> Vec<u8> {
    if clave.is_empty() {
        return datos.to_vec();
    }
    datos.iter().enumerate().map(|(i, b)| b ^ clave[i % clave.len()]).collect()
}

fn main() {}""",
      """#[test] fn conocido() { assert_eq!(xor(b"ABC", b"\\x01"), b"@CB".to_vec()); }
#[test] fn ida_y_vuelta() { let c = xor(b"password123", b"k3y"); assert_ne!(c, b"password123".to_vec()); assert_eq!(xor(&c, b"k3y"), b"password123".to_vec()); }
#[test] fn clave_vacia() { assert_eq!(xor(b"hola", b""), b"hola".to_vec()); }""",
      ["`enumerate()` te da el índice `i` de cada byte.", "`b ^ clave[i % clave.len()]`."]),
    M("rs6_3", "César y fuerza bruta",
      """El cifrado César recorre cada letra `k` posiciones. Solo hay 26 claves, así que se rompe probando todas
(**fuerza bruta**) y buscando una palabra conocida (*known plaintext*).""",
      """1. `fn cesar(texto: &str, k: u8) -> String`: recorre a-z y A-Z `k` posiciones; lo demás queda igual.
2. `fn romper(cifrado: &str, pista: &str) -> Option<u8>`: la clave `k` (0-25) con la que se cifró, sabiendo que el original contiene `pista`.""",
      """fn cesar(texto: &str, k: u8) -> String {
    todo!()
}

fn romper(cifrado: &str, pista: &str) -> Option<u8> {
    todo!()
}

fn main() {}""",
      """fn cesar(texto: &str, k: u8) -> String {
    texto
        .chars()
        .map(|c| match c {
            'a'..='z' => (((c as u8 - b'a' + k % 26) % 26) + b'a') as char,
            'A'..='Z' => (((c as u8 - b'A' + k % 26) % 26) + b'A') as char,
            _ => c,
        })
        .collect()
}

fn romper(cifrado: &str, pista: &str) -> Option<u8> {
    (0..26u8).find(|k| cesar(cifrado, 26 - k).contains(pista))
}

fn main() {}""",
      """#[test] fn cifra() { assert_eq!(cesar("Ataque al amanecer", 3), "Dwdtxh do dpdqhfhu"); }
#[test] fn vuelta_completa() { assert_eq!(cesar("xyz", 26), "xyz"); }
#[test] fn rompe() { let c = cesar("la clave es netlab", 11); assert_eq!(romper(&c, "netlab"), Some(11)); }
#[test] fn sin_solucion() { assert_eq!(romper("abc", "zzzz"), None); }""",
      ["Para una minúscula: `((c as u8 - b'a' + k) % 26 + b'a') as char`.", "`romper`: prueba `k` de 0 a 25 descifrando con `26 - k`."]),
    M("rs6_4", "Checksum de IPv4 (RFC 1071)",
      """El checksum de la cabecera IPv4 suma los datos en palabras de 16 bits (complemento a uno): se suman, los acarreos que
pasan de 16 bits se vuelven a sumar, y al final se invierten los bits (`!`). Así detectan los routers una cabecera corrupta.""",
      """`fn checksum(datos: &[u8]) -> u16`. Si la longitud es impar, el último byte se completa con un 0 a la derecha.
Prueba conocida: la cabecera `45 00 00 73 00 00 40 00 40 11 00 00 c0 a8 00 01 c0 a8 00 c7` da `0xb861`.""",
      """fn checksum(datos: &[u8]) -> u16 {
    todo!()
}

fn main() {}""",
      """fn checksum(datos: &[u8]) -> u16 {
    let mut suma: u32 = 0;
    for par in datos.chunks(2) {
        let palabra = (par[0] as u32) << 8 | *par.get(1).unwrap_or(&0) as u32;
        suma += palabra;
    }
    while suma >> 16 != 0 {
        suma = (suma & 0xffff) + (suma >> 16);
    }
    !(suma as u16)
}

fn main() {}""",
      """#[test] fn cabecera_ipv4() { let h = [0x45,0x00,0x00,0x73,0x00,0x00,0x40,0x00,0x40,0x11,0x00,0x00,0xc0,0xa8,0x00,0x01,0xc0,0xa8,0x00,0xc7]; assert_eq!(checksum(&h), 0xb861); }
#[test] fn verificacion_da_cero() { let h = [0x45,0x00,0x00,0x73,0x00,0x00,0x40,0x00,0x40,0x11,0xb8,0x61,0xc0,0xa8,0x00,0x01,0xc0,0xa8,0x00,0xc7]; assert_eq!(checksum(&h), 0); }
#[test] fn impar() { assert_eq!(checksum(&[0x01]), !0x0100u16); }
#[test] fn vacio() { assert_eq!(checksum(&[]), 0xffff); }""",
      ["`datos.chunks(2)` te da pares; arma la palabra con `(a << 8) | b`.", "Dobla los acarreos con `while suma >> 16 != 0` y al final `!(suma as u16)`."]),
    M("rs6_5", "JEFE: Base64 desde cero",
      """Base64 convierte cada 3 bytes (24 bits) en 4 caracteres de 6 bits. Si al final sobran 1 o 2 bytes se rellena con `=`.
Lo vas a ver en cabeceras HTTP `Authorization: Basic`, en payloads de PowerShell (`-enc`) y en correos de phishing.""",
      """`fn base64(datos: &[u8]) -> String` con el alfabeto estándar `A-Z a-z 0-9 + /` y relleno `=`.
"Man" → "TWFu", "Ma" → "TWE=", "M" → "TQ==".""",
      """const ALFABETO: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64(datos: &[u8]) -> String {
    todo!()
}

fn main() {}""",
      """const ALFABETO: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64(datos: &[u8]) -> String {
    let mut out = String::new();
    for bloque in datos.chunks(3) {
        let b = [bloque[0], *bloque.get(1).unwrap_or(&0), *bloque.get(2).unwrap_or(&0)];
        let n = (b[0] as u32) << 16 | (b[1] as u32) << 8 | b[2] as u32;
        for i in 0..4 {
            if i <= bloque.len() {
                out.push(ALFABETO[((n >> (18 - 6 * i)) & 63) as usize] as char);
            } else {
                out.push('=');
            }
        }
    }
    out
}

fn main() {}""",
      """#[test] fn man() { assert_eq!(base64(b"Man"), "TWFu"); }
#[test] fn ma() { assert_eq!(base64(b"Ma"), "TWE="); }
#[test] fn m() { assert_eq!(base64(b"M"), "TQ=="); }
#[test] fn vacio() { assert_eq!(base64(b""), ""); }
#[test] fn basic_auth() { assert_eq!(base64(b"admin:admin"), "YWRtaW46YWRtaW4="); }
#[test] fn binario() { assert_eq!(base64(&[0xff, 0xfe, 0xfd, 0x00]), "//79AA=="); }""",
      ["Junta 3 bytes en un `u32`: `(a << 16) | (b << 8) | c`.", "Saca 4 índices de 6 bits con `(n >> (18 - 6*i)) & 63`; si el bloque tenía menos bytes, pon `=`."], jefe=True),
  ]},
  {"nombre": "Concurrencia y memoria segura", "cap": "Rust Book cap. 16 y 20", "misiones": [
    M("rs7_1", "Hilos: escaneo en paralelo",
      """`thread::spawn(move || ...)` lanza un hilo y `.join()` espera su resultado. Para compartir datos de solo lectura entre
hilos se usa `Arc` (contador de referencias atómico). Si intentas compartir algo inseguro, **no compila**.""",
      """`fn escanear(puertos: Vec<u16>, abiertos: Vec<u16>, hilos: usize) -> Vec<u16>`: reparte `puertos` en `hilos` grupos
(`chunks`), cada hilo revisa cuáles están en `abiertos` (simulado, sin red) y al final junta y ordena.""",
      """use std::sync::Arc;
use std::thread;

fn escanear(puertos: Vec<u16>, abiertos: Vec<u16>, hilos: usize) -> Vec<u16> {
    todo!()
}

fn main() {}""",
      """use std::sync::Arc;
use std::thread;

fn escanear(puertos: Vec<u16>, abiertos: Vec<u16>, hilos: usize) -> Vec<u16> {
    let abiertos = Arc::new(abiertos);
    let tam = (puertos.len() + hilos.max(1) - 1) / hilos.max(1);
    let mut manejadores = Vec::new();
    for grupo in puertos.chunks(tam.max(1)) {
        let grupo = grupo.to_vec();
        let abiertos = Arc::clone(&abiertos);
        manejadores.push(thread::spawn(move || grupo.into_iter().filter(|p| abiertos.contains(p)).collect::<Vec<u16>>()));
    }
    let mut res: Vec<u16> = manejadores.into_iter().flat_map(|h| h.join().unwrap()).collect();
    res.sort();
    res
}

fn main() {}""",
      """#[test] fn encuentra() { assert_eq!(escanear((1..=1024).collect(), vec![443, 22, 80, 5000], 4), vec![22, 80, 443]); }
#[test] fn un_hilo() { assert_eq!(escanear(vec![1, 2, 3], vec![2], 1), vec![2]); }
#[test] fn nada() { assert!(escanear(vec![], vec![80], 3).is_empty()); }""",
      ["Envuelve `abiertos` en `Arc::new` y clónalo (`Arc::clone`) para cada hilo.", "Guarda los `JoinHandle` en un Vec y al final `h.join().unwrap()`."],
      requiere=[(r"thread::spawn", "Usa `thread::spawn`")]),
    M("rs7_2", "Canales: mensajes entre hilos",
      """"No te comuniques compartiendo memoria; comparte memoria comunicándote". `mpsc::channel()` da un transmisor `tx` y un
receptor `rx`. Cada hilo recibe un clon de `tx`; cuando todos se sueltan, `rx` termina.""",
      """`fn total_alertas(sensores: Vec<Vec<u32>>) -> u32`: cada sensor (un hilo) suma sus alertas y manda el subtotal por un canal.
El hilo principal suma lo que llega.""",
      """use std::sync::mpsc;
use std::thread;

fn total_alertas(sensores: Vec<Vec<u32>>) -> u32 {
    todo!()
}

fn main() {}""",
      """use std::sync::mpsc;
use std::thread;

fn total_alertas(sensores: Vec<Vec<u32>>) -> u32 {
    let (tx, rx) = mpsc::channel();
    for s in sensores {
        let tx = tx.clone();
        thread::spawn(move || {
            tx.send(s.iter().sum::<u32>()).unwrap();
        });
    }
    drop(tx);
    rx.iter().sum()
}

fn main() {}""",
      """#[test] fn suma() { assert_eq!(total_alertas(vec![vec![1, 2], vec![10], vec![], vec![5, 5]]), 23); }
#[test] fn sin_sensores() { assert_eq!(total_alertas(vec![]), 0); }""",
      ["`let (tx, rx) = mpsc::channel();` y un `tx.clone()` por hilo.", "Haz `drop(tx)` del original y luego `rx.iter().sum()`."], requiere=[(r"mpsc", "Usa `mpsc`")]),
    M("rs7_3", "Arc<Mutex>: contador compartido",
      """Para **modificar** algo desde varios hilos: `Arc<Mutex<T>>`. `lock()` da acceso exclusivo y se suelta solo al salir del
bloque. En C olvidar el lock es una *race condition*; en Rust ni siquiera compila sin él.""",
      """`fn contar(hilos: usize, eventos_por_hilo: usize) -> usize`: lanza `hilos` hilos y cada uno suma 1 al contador compartido
`eventos_por_hilo` veces. Devuelve el total.""",
      """use std::sync::{Arc, Mutex};
use std::thread;

fn contar(hilos: usize, eventos_por_hilo: usize) -> usize {
    todo!()
}

fn main() {}""",
      """use std::sync::{Arc, Mutex};
use std::thread;

fn contar(hilos: usize, eventos_por_hilo: usize) -> usize {
    let total = Arc::new(Mutex::new(0usize));
    let mut hs = Vec::new();
    for _ in 0..hilos {
        let total = Arc::clone(&total);
        hs.push(thread::spawn(move || {
            for _ in 0..eventos_por_hilo {
                *total.lock().unwrap() += 1;
            }
        }));
    }
    for h in hs {
        h.join().unwrap();
    }
    let n = *total.lock().unwrap();
    n
}

fn main() {}""",
      """#[test] fn ocho_por_mil() { assert_eq!(contar(8, 1000), 8000); }
#[test] fn cero_hilos() { assert_eq!(contar(0, 50), 0); }""",
      ["`Arc::new(Mutex::new(0usize))`.", "En cada hilo: `*total.lock().unwrap() += 1;` y al final `join` de todos."], requiere=[(r"Mutex", "Usa `Mutex`")]),
    M("rs7_4", "JEFE: adiós al buffer overflow",
      """El `strcpy`/`memcpy` sin revisar tamaños de C es la vulnerabilidad más famosa de la historia. En Rust los slices saben
su tamaño: `dest[..n].copy_from_slice(src)` revisa límites, y `v.get(i)` devuelve `None` en vez de leer memoria ajena.
**Sin `unsafe`.**""",
      """1. `fn copiar(dest: &mut [u8], src: &[u8]) -> Result<usize, String>`: si `src` no cabe → `Err`, si cabe copia y `Ok(bytes)`.
2. `fn leer(buf: &[u8], i: usize) -> Option<u8>`: el byte o `None` si está fuera.""",
      """fn copiar(dest: &mut [u8], src: &[u8]) -> Result<usize, String> {
    todo!()
}

fn leer(buf: &[u8], i: usize) -> Option<u8> {
    todo!()
}

fn main() {}""",
      """fn copiar(dest: &mut [u8], src: &[u8]) -> Result<usize, String> {
    if src.len() > dest.len() {
        return Err(format!("overflow: {} bytes no caben en {}", src.len(), dest.len()));
    }
    dest[..src.len()].copy_from_slice(src);
    Ok(src.len())
}

fn leer(buf: &[u8], i: usize) -> Option<u8> {
    buf.get(i).copied()
}

fn main() {}""",
      """#[test] fn copia_bien() { let mut d = [0u8; 8]; assert_eq!(copiar(&mut d, b"hola"), Ok(4)); assert_eq!(&d[..4], b"hola"); assert_eq!(d[4], 0); }
#[test] fn detecta_overflow() { let mut d = [0u8; 8]; assert!(copiar(&mut d, &[b'A'; 64]).is_err()); assert_eq!(d, [0u8; 8]); }
#[test] fn exacto() { let mut d = [0u8; 3]; assert_eq!(copiar(&mut d, b"abc"), Ok(3)); }
#[test] fn lectura_fuera() { assert_eq!(leer(&[1, 2, 3], 3), None); assert_eq!(leer(&[1, 2, 3], 1000000), None); }
#[test] fn lectura_dentro() { assert_eq!(leer(&[1, 2, 3], 2), Some(3)); }""",
      ["Revisa `src.len() > dest.len()` antes de copiar.", "`dest[..src.len()].copy_from_slice(src)` y `buf.get(i).copied()`."],
      prohibido=[(r"\bunsafe\b", "Nada de `unsafe`: el chiste es hacerlo seguro")], jefe=True),
  ]},
]

# =============================================================================
#  🧠 IA — de las matemáticas a un mini modelo de lenguaje, todo en Rust
# =============================================================================
IA = [
  {"nombre": "Matemáticas de la IA", "cap": "Mathematics for ML cap. 2-3", "misiones": [
    M("ia0_1", "Vectores: producto punto y norma",
      """Una red neuronal es, en el fondo, montones de productos punto: `a·b = Σ aᵢ·bᵢ`. La norma (largo) de un vector es
`√(a·a)`. En Rust: `a.iter().zip(b).map(|(x, y)| x * y).sum()`.""",
      """1. `fn punto(a: &[f64], b: &[f64]) -> f64`
2. `fn norma(a: &[f64]) -> f64`""",
      """fn punto(a: &[f64], b: &[f64]) -> f64 {
    todo!()
}

fn norma(a: &[f64]) -> f64 {
    todo!()
}

fn main() {}""",
      """fn punto(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

fn norma(a: &[f64]) -> f64 {
    punto(a, a).sqrt()
}

fn main() {}""",
      """fn cerca(a: f64, b: f64) -> bool { (a - b).abs() < 1e-9 }
#[test] fn punto_basico() { assert!(cerca(punto(&[1.0, 2.0, 3.0], &[4.0, 5.0, 6.0]), 32.0)); }
#[test] fn ortogonales() { assert!(cerca(punto(&[1.0, 0.0], &[0.0, 1.0]), 0.0)); }
#[test] fn norma_3_4() { assert!(cerca(norma(&[3.0, 4.0]), 5.0)); }""",
      ["`zip` empareja los dos vectores.", "`norma` = `punto(a, a).sqrt()`."]),
    M("ia0_2", "Matriz por vector: una capa densa",
      """Una capa de red neuronal hace `y = W·x + b`: cada fila de la matriz `W` hace un producto punto con la entrada `x`.""",
      """`fn capa(w: &[Vec<f64>], x: &[f64], b: &[f64]) -> Vec<f64>`: para cada fila `i`: `punto(w[i], x) + b[i]`.""",
      """fn capa(w: &[Vec<f64>], x: &[f64], b: &[f64]) -> Vec<f64> {
    todo!()
}

fn main() {}""",
      """fn capa(w: &[Vec<f64>], x: &[f64], b: &[f64]) -> Vec<f64> {
    w.iter()
        .zip(b)
        .map(|(fila, bi)| fila.iter().zip(x).map(|(a, c)| a * c).sum::<f64>() + bi)
        .collect()
}

fn main() {}""",
      """#[test] fn identidad() { assert_eq!(capa(&[vec![1.0, 0.0], vec![0.0, 1.0]], &[3.0, 7.0], &[0.0, 0.0]), vec![3.0, 7.0]); }
#[test] fn con_sesgo() { assert_eq!(capa(&[vec![1.0, 2.0], vec![3.0, 4.0], vec![0.5, 0.5]], &[1.0, 1.0], &[1.0, 0.0, -1.0]), vec![4.0, 7.0, 0.0]); }""",
      ["Recorre las filas de `w` junto con `b` (`zip`).", "Cada salida = producto punto de la fila con `x` + `b[i]`."]),
    M("ia0_3", "JEFE: softmax estable",
      """Softmax convierte números (logits) en probabilidades: `eˣⁱ / Σ eˣʲ`. Truco profesional: resta el máximo antes de
`exp()` o con logits grandes da `inf`/`NaN` (overflow numérico). Así lo hacen PyTorch y llama.cpp.""",
      """`fn softmax(x: &[f64]) -> Vec<f64>`: debe sumar 1 y funcionar con logits enormes como `[1000.0, 1000.0]`.""",
      """fn softmax(x: &[f64]) -> Vec<f64> {
    todo!()
}

fn main() {}""",
      """fn softmax(x: &[f64]) -> Vec<f64> {
    let max = x.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let e: Vec<f64> = x.iter().map(|v| (v - max).exp()).collect();
    let s: f64 = e.iter().sum();
    e.iter().map(|v| v / s).collect()
}

fn main() {}""",
      """fn cerca(a: f64, b: f64) -> bool { (a - b).abs() < 1e-6 }
#[test] fn suma_uno() { let s = softmax(&[1.0, 2.0, 3.0]); assert!(cerca(s.iter().sum::<f64>(), 1.0)); assert!(cerca(s[2], 0.665240955)); }
#[test] fn iguales() { let s = softmax(&[5.0, 5.0]); assert!(cerca(s[0], 0.5)); }
#[test] fn logits_enormes() { let s = softmax(&[1000.0, 1000.0]); assert!(cerca(s[0], 0.5) && !s[0].is_nan()); }""",
      ["Saca el máximo con `fold(f64::NEG_INFINITY, f64::max)`.", "`exp(x - max)` para cada uno y divide entre la suma."], jefe=True),
  ]},
  {"nombre": "Aprender de los datos", "cap": "Dive into Deep Learning cap. 3", "misiones": [
    M("ia1_1", "Error cuadrático medio",
      """Para que un modelo aprenda hay que medir qué tan mal lo hace: la *función de pérdida*. MSE = promedio de `(pred − real)²`.""",
      """`fn mse(pred: &[f64], real: &[f64]) -> f64`. Vacío → 0.""",
      """fn mse(pred: &[f64], real: &[f64]) -> f64 {
    todo!()
}

fn main() {}""",
      """fn mse(pred: &[f64], real: &[f64]) -> f64 {
    if pred.is_empty() {
        return 0.0;
    }
    pred.iter().zip(real).map(|(p, r)| (p - r).powi(2)).sum::<f64>() / pred.len() as f64
}

fn main() {}""",
      """#[test] fn perfecto() { assert_eq!(mse(&[1.0, 2.0], &[1.0, 2.0]), 0.0); }
#[test] fn errores() { assert_eq!(mse(&[3.0, 0.0], &[1.0, 2.0]), 4.0); }
#[test] fn vacio() { assert_eq!(mse(&[], &[]), 0.0); }""",
      ["`(p - r).powi(2)` para cada par.", "Divide la suma entre `pred.len() as f64`."]),
    M("ia1_2", "Descenso de gradiente: regresión lineal",
      """Aprender = ajustar `w` y `b` para bajar la pérdida. El gradiente dice hacia dónde sube el error, así que caminamos al revés:
`w -= lr · ∂L/∂w`. Para `pred = w·x + b` con MSE: `∂L/∂w = 2/n Σ (pred−y)·x` y `∂L/∂b = 2/n Σ (pred−y)`.""",
      """`fn entrenar(xs: &[f64], ys: &[f64], lr: f64, epocas: usize) -> (f64, f64)`: empieza en w=0, b=0 y regresa `(w, b)`.
Con datos de `y = 2x + 1` debe acercarse a (2, 1).""",
      """fn entrenar(xs: &[f64], ys: &[f64], lr: f64, epocas: usize) -> (f64, f64) {
    todo!()
}

fn main() {
    let xs = [0.0, 1.0, 2.0, 3.0, 4.0];
    let ys = [1.0, 3.0, 5.0, 7.0, 9.0];
    println!("{:?}", entrenar(&xs, &ys, 0.05, 2000));
}""",
      """fn entrenar(xs: &[f64], ys: &[f64], lr: f64, epocas: usize) -> (f64, f64) {
    let (mut w, mut b) = (0.0, 0.0);
    let n = xs.len() as f64;
    for _ in 0..epocas {
        let (mut gw, mut gb) = (0.0, 0.0);
        for (x, y) in xs.iter().zip(ys) {
            let err = w * x + b - y;
            gw += 2.0 * err * x / n;
            gb += 2.0 * err / n;
        }
        w -= lr * gw;
        b -= lr * gb;
    }
    (w, b)
}

fn main() {
    let xs = [0.0, 1.0, 2.0, 3.0, 4.0];
    let ys = [1.0, 3.0, 5.0, 7.0, 9.0];
    println!("{:?}", entrenar(&xs, &ys, 0.05, 2000));
}""",
      """#[test] fn aprende_2x_mas_1() { let (w, b) = entrenar(&[0.0, 1.0, 2.0, 3.0, 4.0], &[1.0, 3.0, 5.0, 7.0, 9.0], 0.05, 2000); assert!((w - 2.0).abs() < 0.01, "w = {w}"); assert!((b - 1.0).abs() < 0.01, "b = {b}"); }
#[test] fn aprende_pendiente_negativa() { let (w, b) = entrenar(&[0.0, 1.0, 2.0], &[5.0, 2.0, -1.0], 0.05, 3000); assert!((w + 3.0).abs() < 0.01 && (b - 5.0).abs() < 0.01); }
#[test] fn cero_epocas() { assert_eq!(entrenar(&[1.0], &[1.0], 0.1, 0), (0.0, 0.0)); }""",
      ["En cada época acumula `gw` y `gb` recorriendo los datos.", "`err = w*x + b - y`; `gw += 2*err*x/n`; `gb += 2*err/n`; luego `w -= lr*gw`."]),
    M("ia1_3", "JEFE: perceptrón",
      """El perceptrón (1958) es la neurona original: `salida = 1 si w·x + b > 0`. Regla de aprendizaje: si se equivoca,
`w += lr·(real − pred)·x` y `b += lr·(real − pred)`. Aprende cualquier cosa **linealmente separable** (AND, OR… pero no XOR).""",
      """1. `fn predecir(w: &[f64; 2], b: f64, x: &[f64; 2]) -> f64` (1.0 o 0.0)
2. `fn entrenar(datos: &[([f64; 2], f64)], epocas: usize) -> ([f64; 2], f64)` con lr = 0.1 empezando en ceros.""",
      """fn predecir(w: &[f64; 2], b: f64, x: &[f64; 2]) -> f64 {
    todo!()
}

fn entrenar(datos: &[([f64; 2], f64)], epocas: usize) -> ([f64; 2], f64) {
    todo!()
}

fn main() {}""",
      """fn predecir(w: &[f64; 2], b: f64, x: &[f64; 2]) -> f64 {
    if w[0] * x[0] + w[1] * x[1] + b > 0.0 { 1.0 } else { 0.0 }
}

fn entrenar(datos: &[([f64; 2], f64)], epocas: usize) -> ([f64; 2], f64) {
    let (mut w, mut b) = ([0.0, 0.0], 0.0);
    for _ in 0..epocas {
        for (x, y) in datos {
            let e = y - predecir(&w, b, x);
            w[0] += 0.1 * e * x[0];
            w[1] += 0.1 * e * x[1];
            b += 0.1 * e;
        }
    }
    (w, b)
}

fn main() {}""",
      """fn tabla(f: fn(bool, bool) -> bool) -> Vec<([f64; 2], f64)> { [(0., 0.), (0., 1.), (1., 0.), (1., 1.)].iter().map(|&(a, b)| ([a, b], f(a > 0.5, b > 0.5) as u8 as f64)).collect() }
#[test] fn aprende_and() { let d = tabla(|a, b| a && b); let (w, b) = entrenar(&d, 50); for (x, y) in &d { assert_eq!(predecir(&w, b, x), *y); } }
#[test] fn aprende_or() { let d = tabla(|a, b| a || b); let (w, b) = entrenar(&d, 50); for (x, y) in &d { assert_eq!(predecir(&w, b, x), *y); } }
#[test] fn predice() { assert_eq!(predecir(&[1.0, 1.0], -1.5, &[1.0, 1.0]), 1.0); assert_eq!(predecir(&[1.0, 1.0], -1.5, &[1.0, 0.0]), 0.0); }""",
      ["`predecir`: `if w·x + b > 0 { 1.0 } else { 0.0 }`.", "Error `e = y - pred`; `w[i] += 0.1*e*x[i]`, `b += 0.1*e`."], jefe=True),
  ]},
  {"nombre": "IA para ciberseguridad", "cap": "ML aplicado a detección", "misiones": [
    M("ia2_1", "Activaciones: sigmoide y ReLU",
      """Sin funciones no lineales, una red de 100 capas equivale a una sola. Sigmoide `1/(1+e⁻ˣ)` aplasta todo a (0,1) (útil para
"probabilidad de ataque"); ReLU `max(0,x)` es la que usan casi todas las redes modernas.""",
      """`fn sigmoide(x: f64) -> f64` y `fn relu(x: f64) -> f64`.""",
      """fn sigmoide(x: f64) -> f64 {
    todo!()
}

fn relu(x: f64) -> f64 {
    todo!()
}

fn main() {}""",
      """fn sigmoide(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

fn relu(x: f64) -> f64 {
    x.max(0.0)
}

fn main() {}""",
      """#[test] fn sigmoide_cero() { assert!((sigmoide(0.0) - 0.5).abs() < 1e-12); }
#[test] fn sigmoide_extremos() { assert!(sigmoide(20.0) > 0.999 && sigmoide(-20.0) < 0.001); }
#[test] fn relu_valores() { assert_eq!(relu(-3.0), 0.0); assert_eq!(relu(2.5), 2.5); }""",
      ["`(-x).exp()`", "`x.max(0.0)`"]),
    M("ia2_2", "k-NN: ¿tráfico normal o ataque?",
      """k vecinos más cercanos: para clasificar algo nuevo, busca los `k` ejemplos conocidos más parecidos (distancia euclidiana)
y vota. Aquí cada conexión es `[paquetes_por_seg, bytes_promedio]` con etiqueta `"normal"` o `"ataque"`.""",
      """`fn knn(datos: &[([f64; 2], &str)], x: [f64; 2], k: usize) -> String`: la etiqueta mayoritaria entre los `k` más cercanos
(en empate, `"ataque"`: mejor una falsa alarma que un ataque sin ver).""",
      """fn knn(datos: &[([f64; 2], &str)], x: [f64; 2], k: usize) -> String {
    todo!()
}

fn main() {}""",
      """fn knn(datos: &[([f64; 2], &str)], x: [f64; 2], k: usize) -> String {
    let mut d: Vec<(f64, &str)> = datos
        .iter()
        .map(|(p, et)| (((p[0] - x[0]).powi(2) + (p[1] - x[1]).powi(2)).sqrt(), *et))
        .collect();
    d.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
    let ataques = d.iter().take(k).filter(|(_, e)| *e == "ataque").count();
    let normales = d.iter().take(k).count() - ataques;
    if ataques >= normales { "ataque".into() } else { "normal".into() }
}

fn main() {}""",
      """const D: [([f64; 2], &str); 6] = [([10.0, 500.0], "normal"), ([12.0, 480.0], "normal"), ([8.0, 520.0], "normal"), ([900.0, 60.0], "ataque"), ([1000.0, 64.0], "ataque"), ([850.0, 70.0], "ataque")];
#[test] fn syn_flood() { assert_eq!(knn(&D, [950.0, 62.0], 3), "ataque"); }
#[test] fn navegacion() { assert_eq!(knn(&D, [11.0, 505.0], 3), "normal"); }
#[test] fn empate_es_ataque() { assert_eq!(knn(&[([0.0, 0.0], "normal"), ([2.0, 0.0], "ataque")], [1.0, 0.0], 2), "ataque"); }""",
      ["Calcula la distancia de `x` a cada ejemplo y ordena con `partial_cmp`.", "Cuenta `\"ataque\"` entre los primeros `k`."]),
    M("ia2_3", "JEFE: detector de anomalías (z-score)",
      """Muchos SIEM/UEBA detectan anomalías con estadística: `z = (x − media) / desviación`. Si |z| es grande (p. ej. > 3),
ese valor es raro: un usuario que de repente baja 50 GB, un pico de logins…""",
      """`fn anomalias(v: &[f64], umbral: f64) -> Vec<usize>`: índices con `|z| > umbral` (desviación estándar poblacional).
Si la desviación es 0 → vacío.""",
      """fn anomalias(v: &[f64], umbral: f64) -> Vec<usize> {
    todo!()
}

fn main() {}""",
      """fn anomalias(v: &[f64], umbral: f64) -> Vec<usize> {
    if v.is_empty() {
        return vec![];
    }
    let n = v.len() as f64;
    let media = v.iter().sum::<f64>() / n;
    let desv = (v.iter().map(|x| (x - media).powi(2)).sum::<f64>() / n).sqrt();
    if desv == 0.0 {
        return vec![];
    }
    (0..v.len()).filter(|&i| ((v[i] - media) / desv).abs() > umbral).collect()
}

fn main() {}""",
      """#[test] fn pico_de_descarga() { let mut v = vec![1.0; 30]; v[17] = 50.0; assert_eq!(anomalias(&v, 3.0), vec![17]); }
#[test] fn todo_igual() { assert!(anomalias(&[5.0, 5.0, 5.0], 1.0).is_empty()); }
#[test] fn umbral_bajo() { assert_eq!(anomalias(&[1.0, 2.0, 3.0, 4.0, 5.0], 1.2), vec![0, 4]); }""",
      ["Media = suma / n; desviación = raíz del promedio de (x − media)².", "Filtra índices donde `((v[i]-media)/desv).abs() > umbral`."], jefe=True),
  ]},
  {"nombre": "Modelos de lenguaje", "cap": "Cómo funciona un LLM (y RAG)", "misiones": [
    M("ia3_1", "Tokenizador",
      """Un LLM no ve letras: ve **tokens**. El paso 1 es partir el texto. Aquí uno simple: minúsculas y separar por todo lo que
no sea letra o número (los reales como BPE parten en sub-palabras).""",
      """`fn tokenizar(texto: &str) -> Vec<String>`: minúsculas, separa por cualquier carácter no alfanumérico y quita vacíos.""",
      """fn tokenizar(texto: &str) -> Vec<String> {
    todo!()
}

fn main() {}""",
      """fn tokenizar(texto: &str) -> Vec<String> {
    texto
        .to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|t| !t.is_empty())
        .map(String::from)
        .collect()
}

fn main() {}""",
      """#[test] fn basico() { assert_eq!(tokenizar("Hola, Mundo!"), vec!["hola", "mundo"]); }
#[test] fn comando() { assert_eq!(tokenizar("nmap -sV 10.0.0.1"), vec!["nmap", "sv", "10", "0", "0", "1"]); }
#[test] fn acentos() { assert_eq!(tokenizar("Configuración BÁSICA"), vec!["configuración", "básica"]); }
#[test] fn vacio() { assert!(tokenizar("...").is_empty()); }""",
      ["`split(|c: char| !c.is_alphanumeric())`", "Quita vacíos con `filter(|t| !t.is_empty())`."]),
    M("ia3_2", "Similitud coseno: el corazón del RAG",
      """Así busca NetLab en tus guías: cada texto se vuelve un vector (*embedding*) y se compara con la pregunta por
**similitud coseno** = `a·b / (|a|·|b|)`: 1 = misma dirección, 0 = nada que ver.""",
      """1. `fn coseno(a: &[f64], b: &[f64]) -> f64` (si alguna norma es 0 → 0).
2. `fn mejor(consulta: &[f64], docs: &[Vec<f64>]) -> Option<usize>`: índice del documento más parecido.""",
      """fn coseno(a: &[f64], b: &[f64]) -> f64 {
    todo!()
}

fn mejor(consulta: &[f64], docs: &[Vec<f64>]) -> Option<usize> {
    todo!()
}

fn main() {}""",
      """fn coseno(a: &[f64], b: &[f64]) -> f64 {
    let p: f64 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let na = a.iter().map(|x| x * x).sum::<f64>().sqrt();
    let nb = b.iter().map(|x| x * x).sum::<f64>().sqrt();
    if na == 0.0 || nb == 0.0 { 0.0 } else { p / (na * nb) }
}

fn mejor(consulta: &[f64], docs: &[Vec<f64>]) -> Option<usize> {
    (0..docs.len()).max_by(|&i, &j| coseno(consulta, &docs[i]).partial_cmp(&coseno(consulta, &docs[j])).unwrap())
}

fn main() {}""",
      """fn cerca(a: f64, b: f64) -> bool { (a - b).abs() < 1e-9 }
#[test] fn misma_direccion() { assert!(cerca(coseno(&[1.0, 2.0], &[2.0, 4.0]), 1.0)); }
#[test] fn ortogonal() { assert!(cerca(coseno(&[1.0, 0.0], &[0.0, 3.0]), 0.0)); }
#[test] fn cero() { assert_eq!(coseno(&[0.0, 0.0], &[1.0, 1.0]), 0.0); }
#[test] fn busca() { assert_eq!(mejor(&[1.0, 0.1], &[vec![0.0, 1.0], vec![0.9, 0.2], vec![-1.0, 0.0]]), Some(1)); }
#[test] fn sin_docs() { assert_eq!(mejor(&[1.0], &[]), None); }""",
      ["Producto punto entre producto de normas.", "`mejor`: `max_by` comparando el coseno con `partial_cmp`."]),
    M("ia3_3", "JEFE: mini modelo de lenguaje (bigramas)",
      """Un LLM predice **la siguiente palabra**. El modelo más simple: contar qué palabra sigue a cuál (bigramas) y elegir la más
frecuente. GPT hace lo mismo pero con contexto largo y miles de millones de parámetros en lugar de un conteo.""",
      """`fn siguiente(corpus: &str, palabra: &str) -> Option<String>`: tokeniza (minúsculas, por espacios), cuenta qué palabras siguen a
`palabra` y devuelve la más común (empate → la menor alfabéticamente). Si nunca aparece seguida de algo → None.""",
      """use std::collections::HashMap;

fn siguiente(corpus: &str, palabra: &str) -> Option<String> {
    todo!()
}

fn main() {}""",
      """use std::collections::HashMap;

fn siguiente(corpus: &str, palabra: &str) -> Option<String> {
    let t: Vec<String> = corpus.split_whitespace().map(|w| w.to_lowercase()).collect();
    let objetivo = palabra.to_lowercase();
    let mut cuenta: HashMap<&str, usize> = HashMap::new();
    for par in t.windows(2) {
        if par[0] == objetivo {
            *cuenta.entry(par[1].as_str()).or_insert(0) += 1;
        }
    }
    cuenta.into_iter().max_by(|a, b| a.1.cmp(&b.1).then(b.0.cmp(a.0))).map(|(w, _)| w.to_string())
}

fn main() {}""",
      """const C: &str = "el atacante escanea el puerto y el atacante explota el servicio el puerto queda abierto";
#[test] fn mas_comun() { assert_eq!(siguiente(C, "el"), Some("atacante".to_string())); }
#[test] fn mayusculas() { assert_eq!(siguiente("Ping al Router, ping al switch", "PING"), Some("al".to_string())); }
#[test] fn empate_alfabetico() { assert_eq!(siguiente("a x a b", "a"), Some("b".to_string())); }
#[test] fn ultima_palabra() { assert_eq!(siguiente("hola mundo", "mundo"), None); }""",
      ["`t.windows(2)` te da cada par de palabras seguidas.", "Elige con `max_by(|a, b| a.1.cmp(&b.1).then(b.0.cmp(a.0)))`."], jefe=True),
  ]},
]

# =============================================================================
#  🔧 PROCESADORES — de los bits a un emulador RISC-V
# =============================================================================
CPU = [
  {"nombre": "Bits y números", "cap": "Representación de datos", "misiones": [
    M("cpu0_1", "Binario",
      """La CPU solo entiende bits. `format!("{:08b}", n)` imprime 8 bits; `u8::from_str_radix(s, 2)` lee binario.
Repasa: 192 = 11000000, la base del subneteo.""",
      """1. `fn a_binario(n: u8) -> String` (siempre 8 dígitos).
2. `fn de_binario(s: &str) -> Option<u8>`: None si no es binario válido de 8 bits o menos.""",
      """fn a_binario(n: u8) -> String {
    todo!()
}

fn de_binario(s: &str) -> Option<u8> {
    todo!()
}

fn main() {}""",
      """fn a_binario(n: u8) -> String {
    format!("{:08b}", n)
}

fn de_binario(s: &str) -> Option<u8> {
    if s.is_empty() || s.len() > 8 {
        return None;
    }
    u8::from_str_radix(s, 2).ok()
}

fn main() {}""",
      """#[test] fn mascara() { assert_eq!(a_binario(192), "11000000"); assert_eq!(a_binario(5), "00000101"); }
#[test] fn lee() { assert_eq!(de_binario("11111111"), Some(255)); assert_eq!(de_binario("101"), Some(5)); }
#[test] fn invalido() { assert_eq!(de_binario("102"), None); assert_eq!(de_binario("111111111"), None); assert_eq!(de_binario(""), None); }""",
      ["`format!(\"{:08b}\", n)`", "`u8::from_str_radix(s, 2).ok()` y revisa el largo."]),
    M("cpu0_2", "Complemento a dos",
      """Los negativos se guardan en **complemento a dos**: el mismo byte `11111111` es 255 como `u8` y −1 como `i8`.
Para negar: invierte los bits y suma 1. Confundir con/sin signo es un bug clásico de seguridad (longitudes negativas).""",
      """1. `fn como_i8(b: u8) -> i8`: interpreta el byte con signo **sin usar `as i8`** (si el bit 7 está prendido, vale `b − 256`).
2. `fn negar(b: u8) -> u8`: complemento a dos usando `!` y `wrapping_add`.""",
      """fn como_i8(b: u8) -> i8 {
    todo!()
}

fn negar(b: u8) -> u8 {
    todo!()
}

fn main() {}""",
      """fn como_i8(b: u8) -> i8 {
    if b & 0x80 != 0 {
        (b as i16 - 256) as i8
    } else {
        b as i16 as i8
    }
}

fn negar(b: u8) -> u8 {
    (!b).wrapping_add(1)
}

fn main() {}""",
      """#[test] fn menos_uno() { assert_eq!(como_i8(0xff), -1); }
#[test] fn minimo() { assert_eq!(como_i8(0x80), -128); }
#[test] fn positivo() { assert_eq!(como_i8(0x7f), 127); }
#[test] fn negacion() { assert_eq!(negar(1), 0xff); assert_eq!(negar(0), 0); assert_eq!(negar(0x80), 0x80); }""",
      ["Revisa el bit 7 con `b & 0x80`.", "`(!b).wrapping_add(1)`"]),
    M("cpu0_3", "JEFE: magia de bits",
      """Los trucos de bits están en todos lados: máscaras de red, permisos de Linux (rwx = 3 bits), flags TCP (SYN=0x02, ACK=0x10).
`n & (n − 1)` apaga el bit más bajo.""",
      """1. `fn contar_unos(n: u32) -> u32` sin `count_ones` (pista: `n & (n-1)`).
2. `fn bit(n: u32, i: u32) -> bool`
3. `fn flags_tcp(f: u8) -> Vec<&'static str>`: nombres de los flags prendidos en orden FIN(0x01), SYN(0x02), RST(0x04), PSH(0x08), ACK(0x10).""",
      """fn contar_unos(n: u32) -> u32 {
    todo!()
}

fn bit(n: u32, i: u32) -> bool {
    todo!()
}

fn flags_tcp(f: u8) -> Vec<&'static str> {
    todo!()
}

fn main() {}""",
      """fn contar_unos(mut n: u32) -> u32 {
    let mut c = 0;
    while n != 0 {
        n &= n - 1;
        c += 1;
    }
    c
}

fn bit(n: u32, i: u32) -> bool {
    (n >> i) & 1 == 1
}

fn flags_tcp(f: u8) -> Vec<&'static str> {
    [(0x01, "FIN"), (0x02, "SYN"), (0x04, "RST"), (0x08, "PSH"), (0x10, "ACK")]
        .iter()
        .filter(|(m, _)| f & m != 0)
        .map(|(_, n)| *n)
        .collect()
}

fn main() {}""",
      """#[test] fn unos_mascara() { assert_eq!(contar_unos(0xFFFFFF00), 24); assert_eq!(contar_unos(0), 0); }
#[test] fn bits() { assert!(bit(0b100, 2)); assert!(!bit(0b100, 1)); }
#[test] fn syn_ack() { assert_eq!(flags_tcp(0x12), vec!["SYN", "ACK"]); }
#[test] fn xmas_parcial() { assert_eq!(flags_tcp(0x09), vec!["FIN", "PSH"]); }""",
      ["`while n != 0 { n &= n - 1; c += 1; }`", "`flags_tcp`: un arreglo de (máscara, nombre) filtrado con `f & m != 0`."],
      prohibido=[(r"count_ones", "Sin `count_ones`")], jefe=True),
  ]},
  {"nombre": "Lógica y ALU", "cap": "Compuertas → sumador → ALU", "misiones": [
    M("cpu1_1", "Sumador completo con compuertas",
      """Toda la aritmética de la CPU sale de compuertas AND, OR, XOR. Un sumador completo suma 3 bits:
`suma = a ⊕ b ⊕ cin`, `cout = (a ∧ b) ∨ (cin ∧ (a ⊕ b))`. Encadenando 8 tienes un sumador de 8 bits (*ripple carry*).""",
      """1. `fn sumador_completo(a: bool, b: bool, cin: bool) -> (bool, bool)` → (suma, acarreo)
2. `fn sumar8(a: u8, b: u8) -> (u8, bool)` usando 8 sumadores completos (sin usar `+` entre a y b). Devuelve (resultado, acarreo final).""",
      """fn sumador_completo(a: bool, b: bool, cin: bool) -> (bool, bool) {
    todo!()
}

fn sumar8(a: u8, b: u8) -> (u8, bool) {
    todo!()
}

fn main() {}""",
      """fn sumador_completo(a: bool, b: bool, cin: bool) -> (bool, bool) {
    (a ^ b ^ cin, (a && b) || (cin && (a ^ b)))
}

fn sumar8(a: u8, b: u8) -> (u8, bool) {
    let mut res = 0u8;
    let mut c = false;
    for i in 0..8 {
        let (s, co) = sumador_completo((a >> i) & 1 == 1, (b >> i) & 1 == 1, c);
        if s {
            res |= 1 << i;
        }
        c = co;
    }
    (res, c)
}

fn main() {}""",
      """#[test] fn tabla_verdad() { assert_eq!(sumador_completo(true, true, true), (true, true)); assert_eq!(sumador_completo(true, false, false), (true, false)); assert_eq!(sumador_completo(true, true, false), (false, true)); }
#[test] fn suma() { assert_eq!(sumar8(100, 55), (155, false)); }
#[test] fn acarreo() { assert_eq!(sumar8(200, 100), (44, true)); }
#[test] fn todas() { for a in (0..=255u8).step_by(17) { for b in (0..=255u8).step_by(13) { assert_eq!(sumar8(a, b), a.overflowing_add(b)); } } }""",
      ["XOR en Rust para bool es `^`.", "Recorre i de 0 a 7 sacando cada bit con `(a >> i) & 1`."], requiere=[(r"sumador_completo\(", "Usa tu `sumador_completo` dentro de `sumar8`")],
      prohibido=[(r"\ba\s*\+\s*b\b|overflowing_add|wrapping_add|checked_add", "Suma con tus compuertas, no con `+`")]),
    M("cpu1_2", "ALU con banderas",
      """La ALU hace la operación y prende **banderas** (flags) que luego usan los saltos condicionales: Z (resultado 0),
C (acarreo/préstamo), N (bit 7 prendido = negativo). Así se implementa un `if a == b` en ensamblador: `SUB` y mirar Z.""",
      """`fn alu(op: Op, a: u8, b: u8) -> (u8, Banderas)` para Add, Sub, And, Or, Xor. En Sub, `c` = hubo préstamo (a < b).
En And/Or/Xor, `c = false`.""",
      """#[derive(Debug, PartialEq, Clone, Copy)]
enum Op { Add, Sub, And, Or, Xor }

#[derive(Debug, PartialEq)]
struct Banderas { z: bool, c: bool, n: bool }

fn alu(op: Op, a: u8, b: u8) -> (u8, Banderas) {
    todo!()
}

fn main() {}""",
      """#[derive(Debug, PartialEq, Clone, Copy)]
enum Op { Add, Sub, And, Or, Xor }

#[derive(Debug, PartialEq)]
struct Banderas { z: bool, c: bool, n: bool }

fn alu(op: Op, a: u8, b: u8) -> (u8, Banderas) {
    let (r, c) = match op {
        Op::Add => a.overflowing_add(b),
        Op::Sub => a.overflowing_sub(b),
        Op::And => (a & b, false),
        Op::Or => (a | b, false),
        Op::Xor => (a ^ b, false),
    };
    (r, Banderas { z: r == 0, c, n: r & 0x80 != 0 })
}

fn main() {}""",
      """#[test] fn add_carry() { assert_eq!(alu(Op::Add, 200, 56), (0, Banderas { z: true, c: true, n: false })); }
#[test] fn sub_igual_es_cero() { assert_eq!(alu(Op::Sub, 7, 7).1.z, true); }
#[test] fn sub_prestamo() { assert_eq!(alu(Op::Sub, 3, 5), (254, Banderas { z: false, c: true, n: true })); }
#[test] fn xor_consigo_mismo() { assert_eq!(alu(Op::Xor, 0x5a, 0x5a), (0, Banderas { z: true, c: false, n: false })); }
#[test] fn or_and() { assert_eq!(alu(Op::Or, 0xf0, 0x0f).0, 0xff); assert_eq!(alu(Op::And, 0xf0, 0x0f).0, 0); }""",
      ["`overflowing_add` y `overflowing_sub` te dan (resultado, ¿se pasó?).", "`n` = `r & 0x80 != 0`, `z` = `r == 0`."]),
    M("cpu1_3", "JEFE: endianness",
      """¿En qué orden se guardan los bytes de un número? x86 y RISC-V son **little endian** (byte bajo primero); las redes usan
**big endian** (*network byte order*). Confundirlo da puertos e IPs al revés al parsear paquetes.""",
      """1. `fn a_red(n: u32) -> [u8; 4]` (big endian) y `fn a_little(n: u32) -> [u8; 4]`, a mano con shifts (sin `to_be_bytes` / `to_le_bytes`).
2. `fn puerto_de_cabecera(b: [u8; 2]) -> u16`: lee un puerto TCP como viene en el paquete.""",
      """fn a_red(n: u32) -> [u8; 4] {
    todo!()
}

fn a_little(n: u32) -> [u8; 4] {
    todo!()
}

fn puerto_de_cabecera(b: [u8; 2]) -> u16 {
    todo!()
}

fn main() {}""",
      """fn a_red(n: u32) -> [u8; 4] {
    [(n >> 24) as u8, (n >> 16) as u8, (n >> 8) as u8, n as u8]
}

fn a_little(n: u32) -> [u8; 4] {
    let r = a_red(n);
    [r[3], r[2], r[1], r[0]]
}

fn puerto_de_cabecera(b: [u8; 2]) -> u16 {
    (b[0] as u16) << 8 | b[1] as u16
}

fn main() {}""",
      """#[test] fn red() { assert_eq!(a_red(0xC0A80001), [192, 168, 0, 1]); }
#[test] fn little() { assert_eq!(a_little(0x12345678), [0x78, 0x56, 0x34, 0x12]); }
#[test] fn puerto_https() { assert_eq!(puerto_de_cabecera([0x01, 0xbb]), 443); }""",
      ["`(n >> 24) as u8` es el byte más alto.", "El puerto: `(b[0] as u16) << 8 | b[1] as u16`."],
      prohibido=[(r"to_(be|le)_bytes|from_be_bytes", "Hazlo a mano con shifts")], jefe=True),
  ]},
  {"nombre": "RISC-V", "cap": "RISC-V Unprivileged Spec, cap. 2", "misiones": [
    M("cpu2_1", "Decodificar una instrucción",
      """Cada instrucción RISC-V mide 32 bits. Formato R: `funct7[31:25] rs2[24:20] rs1[19:15] funct3[14:12] rd[11:7] opcode[6:0]`.
Para sacar un campo: desplaza y aplica máscara: `(inst >> 7) & 0x1f`.""",
      """`fn campos(inst: u32) -> (u32, u32, u32, u32, u32, u32)` → (opcode, rd, funct3, rs1, rs2, funct7).
`add x3, x1, x2` = `0x002081B3`.""",
      """fn campos(inst: u32) -> (u32, u32, u32, u32, u32, u32) {
    todo!()
}

fn main() {}""",
      """fn campos(inst: u32) -> (u32, u32, u32, u32, u32, u32) {
    (inst & 0x7f, (inst >> 7) & 0x1f, (inst >> 12) & 0x7, (inst >> 15) & 0x1f, (inst >> 20) & 0x1f, inst >> 25)
}

fn main() {}""",
      """#[test] fn add() { assert_eq!(campos(0x002081B3), (0x33, 3, 0, 1, 2, 0)); }
#[test] fn sub() { assert_eq!(campos(0x40110233), (0x33, 4, 0, 2, 1, 0x20)); }""",
      ["opcode = `inst & 0x7f`; rd = `(inst >> 7) & 0x1f`.", "funct3 = `(inst >> 12) & 7`, rs1 `>> 15`, rs2 `>> 20`, funct7 `>> 25`."]),
    M("cpu2_2", "Inmediatos con signo",
      """Las instrucciones tipo I (como `addi`) traen un inmediato de 12 bits en `[31:20]` **con signo**: hay que extender el signo
a 32 bits. Truco: `(inst as i32) >> 20` (el shift aritmético copia el bit de signo).""",
      """`fn imm_i(inst: u32) -> i32`. `addi x1, x0, 5` = `0x00500093` → 5; `addi x1, x1, -1` = `0xFFF08093` → −1.""",
      """fn imm_i(inst: u32) -> i32 {
    todo!()
}

fn main() {}""",
      """fn imm_i(inst: u32) -> i32 {
    (inst as i32) >> 20
}

fn main() {}""",
      """#[test] fn cinco() { assert_eq!(imm_i(0x00500093), 5); }
#[test] fn menos_uno() { assert_eq!(imm_i(0xFFF08093), -1); }
#[test] fn maximo() { assert_eq!(imm_i(0x7FF00093), 2047); }
#[test] fn minimo() { assert_eq!(imm_i(0x80000093), -2048); }""",
      ["Convierte a `i32` antes de desplazar.", "`(inst as i32) >> 20`"]),
    M("cpu2_3", "JEFE: emulador RISC-V",
      """Un emulador hace el ciclo **fetch → decode → execute**: lee la instrucción, saca sus campos y ejecuta. En RISC-V el
registro `x0` **siempre vale 0** aunque le escribas. Opcodes: `0x13` = OP-IMM (addi si funct3=0), `0x33` = OP (add si funct7=0,
sub si funct7=0x20). La aritmética es *wrapping* (sin trap por overflow).""",
      """Completa `fn paso(&mut self, inst: u32)` para ADDI, ADD y SUB, y avanza `pc` en 4. Instrucciones desconocidas solo avanzan el pc.""",
      """struct Cpu {
    x: [i32; 32],
    pc: u32,
}

impl Cpu {
    fn nueva() -> Self {
        Cpu { x: [0; 32], pc: 0 }
    }

    fn paso(&mut self, inst: u32) {
        todo!()
    }
}

fn main() {}""",
      """struct Cpu {
    x: [i32; 32],
    pc: u32,
}

impl Cpu {
    fn nueva() -> Self {
        Cpu { x: [0; 32], pc: 0 }
    }

    fn paso(&mut self, inst: u32) {
        let opcode = inst & 0x7f;
        let rd = ((inst >> 7) & 0x1f) as usize;
        let f3 = (inst >> 12) & 7;
        let rs1 = ((inst >> 15) & 0x1f) as usize;
        let rs2 = ((inst >> 20) & 0x1f) as usize;
        let f7 = inst >> 25;
        match (opcode, f3, f7) {
            (0x13, 0, _) => self.x[rd] = self.x[rs1].wrapping_add((inst as i32) >> 20),
            (0x33, 0, 0) => self.x[rd] = self.x[rs1].wrapping_add(self.x[rs2]),
            (0x33, 0, 0x20) => self.x[rd] = self.x[rs1].wrapping_sub(self.x[rs2]),
            _ => {}
        }
        self.x[0] = 0;
        self.pc += 4;
    }
}

fn main() {}""",
      """#[test] fn programa() { let mut c = Cpu::nueva(); for i in [0x00500093u32, 0x00700113, 0x002081B3, 0x40110233] { c.paso(i); } assert_eq!(c.x[1], 5); assert_eq!(c.x[2], 7); assert_eq!(c.x[3], 12); assert_eq!(c.x[4], 2); assert_eq!(c.pc, 16); }
#[test] fn x0_siempre_cero() { let mut c = Cpu::nueva(); c.paso(0x00500013); assert_eq!(c.x[0], 0); }
#[test] fn negativos() { let mut c = Cpu::nueva(); c.paso(0xFFF08093); assert_eq!(c.x[1], -1); }
#[test] fn desconocida() { let mut c = Cpu::nueva(); c.paso(0xFFFFFFFF); assert_eq!(c.pc, 4); assert!(c.x.iter().all(|&v| v == 0)); }""",
      ["Decodifica todos los campos primero y luego haz `match (opcode, funct3, funct7)`.", "Al final: `self.x[0] = 0; self.pc += 4;`"], jefe=True),
  ]},
  {"nombre": "Memoria y explotación", "cap": "Caché, pila y overflow", "misiones": [
    M("cpu3_1", "Caché de mapeo directo",
      """La caché guarda bloques de memoria cerca de la CPU. En mapeo directo: `bloque = dir / tam_bloque`, `línea = bloque % lineas`,
`etiqueta = bloque / lineas`. Si la línea tiene esa etiqueta: **acierto**; si no: **fallo** y se reemplaza. (Ataques como Spectre
y Flush+Reload miden justo estos tiempos de acierto/fallo.)""",
      """`fn simular(dirs: &[u32], lineas: usize, tam_bloque: u32) -> (u32, u32)` → (aciertos, fallos), caché vacía al inicio.""",
      """fn simular(dirs: &[u32], lineas: usize, tam_bloque: u32) -> (u32, u32) {
    todo!()
}

fn main() {}""",
      """fn simular(dirs: &[u32], lineas: usize, tam_bloque: u32) -> (u32, u32) {
    let mut cache: Vec<Option<u32>> = vec![None; lineas];
    let (mut a, mut f) = (0, 0);
    for &d in dirs {
        let bloque = d / tam_bloque;
        let linea = (bloque as usize) % lineas;
        let etiqueta = bloque / lineas as u32;
        if cache[linea] == Some(etiqueta) {
            a += 1;
        } else {
            f += 1;
            cache[linea] = Some(etiqueta);
        }
    }
    (a, f)
}

fn main() {}""",
      """#[test] fn secuencial() { let d: Vec<u32> = (0..64).collect(); assert_eq!(simular(&d, 4, 16), (60, 4)); }
#[test] fn conflicto() { assert_eq!(simular(&[0, 64, 0, 64], 4, 16), (0, 4)); }
#[test] fn repetido() { assert_eq!(simular(&[8, 8, 8], 2, 8), (2, 1)); }""",
      ["Usa `Vec<Option<u32>>` con una etiqueta por línea.", "bloque = d / tam; línea = bloque % lineas; etiqueta = bloque / lineas."]),
    M("cpu3_2", "La pila y el stack overflow",
      """La pila guarda las llamadas a funciones (dirección de regreso, variables locales). Tiene tamaño fijo: si una recursión no
termina, se desborda. Un buen diseño devuelve error en vez de pisar memoria.""",
      """Completa `Pila`: `apilar(v) -> Result<(), String>` (Err si ya está llena), `desapilar() -> Option<u32>` y `tope() -> Option<u32>`.""",
      """struct Pila {
    datos: Vec<u32>,
    max: usize,
}

impl Pila {
    fn nueva(max: usize) -> Self {
        Pila { datos: Vec::new(), max }
    }
    // apilar, desapilar, tope
}

fn main() {}""",
      """struct Pila {
    datos: Vec<u32>,
    max: usize,
}

impl Pila {
    fn nueva(max: usize) -> Self {
        Pila { datos: Vec::new(), max }
    }

    fn apilar(&mut self, v: u32) -> Result<(), String> {
        if self.datos.len() >= self.max {
            return Err("stack overflow".into());
        }
        self.datos.push(v);
        Ok(())
    }

    fn desapilar(&mut self) -> Option<u32> {
        self.datos.pop()
    }

    fn tope(&self) -> Option<u32> {
        self.datos.last().copied()
    }
}

fn main() {}""",
      """#[test] fn lifo() { let mut p = Pila::nueva(3); p.apilar(1).unwrap(); p.apilar(2).unwrap(); assert_eq!(p.tope(), Some(2)); assert_eq!(p.desapilar(), Some(2)); assert_eq!(p.desapilar(), Some(1)); assert_eq!(p.desapilar(), None); }
#[test] fn overflow() { let mut p = Pila::nueva(2); assert!(p.apilar(1).is_ok()); assert!(p.apilar(2).is_ok()); assert!(p.apilar(3).is_err()); assert_eq!(p.tope(), Some(2)); }""",
      ["`apilar`: revisa `self.datos.len() >= self.max`.", "`pop()` y `last().copied()` ya te dan Option."]),
    M("cpu3_3", "JEFE: anatomía de un buffer overflow",
      """En C, un `char buf[8]` en la pila queda justo antes de la **dirección de regreso**. Si `strcpy` copia 12 bytes, los últimos 4
pisan esa dirección y el atacante controla a dónde salta la CPU. Aquí lo **simulas** en un arreglo de 16 bytes:
`mem[0..8]` = buffer, `mem[8..12]` = dirección de regreso (little endian).""",
      """1. `fn strcpy_c(mem: &mut [u8; 16], entrada: &[u8])`: copia como C, **sin revisar** el buffer (pero sin salirte de los 16 bytes).
2. `fn regreso(mem: &[u8; 16]) -> u32`: lee `mem[8..12]` en little endian.
3. `fn strcpy_seguro(mem: &mut [u8; 16], entrada: &[u8]) -> bool`: copia solo si cabe en 8 bytes; devuelve si copió.""",
      """fn strcpy_c(mem: &mut [u8; 16], entrada: &[u8]) {
    todo!()
}

fn regreso(mem: &[u8; 16]) -> u32 {
    todo!()
}

fn strcpy_seguro(mem: &mut [u8; 16], entrada: &[u8]) -> bool {
    todo!()
}

fn main() {}""",
      """fn strcpy_c(mem: &mut [u8; 16], entrada: &[u8]) {
    let n = entrada.len().min(16);
    mem[..n].copy_from_slice(&entrada[..n]);
}

fn regreso(mem: &[u8; 16]) -> u32 {
    u32::from_le_bytes([mem[8], mem[9], mem[10], mem[11]])
}

fn strcpy_seguro(mem: &mut [u8; 16], entrada: &[u8]) -> bool {
    if entrada.len() > 8 {
        return false;
    }
    mem[..entrada.len()].copy_from_slice(entrada);
    true
}

fn main() {}""",
      """fn pila() -> [u8; 16] { let mut m = [0u8; 16]; m[8..12].copy_from_slice(&0x0040_1000u32.to_le_bytes()); m }
#[test] fn normal_no_pisa() { let mut m = pila(); strcpy_c(&mut m, b"hola"); assert_eq!(regreso(&m), 0x0040_1000); }
#[test] fn exploit_controla_regreso() { let mut m = pila(); let mut p = b"AAAAAAAA".to_vec(); p.extend_from_slice(&0xdeadbeefu32.to_le_bytes()); strcpy_c(&mut m, &p); assert_eq!(regreso(&m), 0xdeadbeef); }
#[test] fn seguro_rechaza() { let mut m = pila(); assert!(!strcpy_seguro(&mut m, &[b'A'; 12])); assert_eq!(regreso(&m), 0x0040_1000); }
#[test] fn seguro_copia() { let mut m = pila(); assert!(strcpy_seguro(&mut m, b"12345678")); assert_eq!(&m[..8], b"12345678"); }""",
      ["`strcpy_c`: copia `min(entrada.len(), 16)` bytes.", "`u32::from_le_bytes([mem[8], mem[9], mem[10], mem[11]])`."], jefe=True),
  ]},
]

CURSOS = {
    "rust": {"nombre": "Rust", "icono": "🦀", "lema": "El Rust Book por niveles, con retos de ciberseguridad", "niveles": RUST},
    "ia": {"nombre": "Inteligencia Artificial", "icono": "🧠", "lema": "De vectores a un mini modelo de lenguaje, programado en Rust", "niveles": IA},
    "cpu": {"nombre": "Procesadores", "icono": "🔧", "lema": "De bits y compuertas a un emulador RISC-V y un buffer overflow", "niveles": CPU},
}
from .pytorch_lab import NIVELES_TORCH  # noqa: E402
from .chisel_lab import NIVELES_CHISEL  # noqa: E402
CURSOS["chisel"] = {"nombre": "Chisel", "icono": "🔩", "lema": "Diseña hardware de verdad: compuertas, registros, una ALU y máquinas de estado, y mira el Verilog que generan",
                    "niveles": NIVELES_CHISEL}
CURSOS["torch"] = {"nombre": "PyTorch", "icono": "🔥", "lema": "IA de verdad en tu GPU: autograd, MNIST, CNN, detección de intrusiones y un mini GPT",
                   "niveles": NIVELES_TORCH}
from .rustproj import CURSO as _CURSO_RP  # noqa: E402
CURSOS["rustproj"] = _CURSO_RP


def todas() -> dict[str, dict]:
    out = {}
    for cid, c in CURSOS.items():
        for n, nivel in enumerate(c["niveles"]):
            for m in nivel["misiones"]:
                out[m["id"]] = {**m, "curso": cid, "nivel": n}
    return out


MISIONES = todas()


def para_ui() -> dict:
    """Todo menos las pruebas y la solución (esas se piden aparte)."""
    out = {}
    for cid, c in CURSOS.items():
        out[cid] = {**{k: v for k, v in c.items() if k != "niveles"},
                    "niveles": [{"nombre": n["nombre"], "cap": n["cap"],
                                 "misiones": [{k: m.get(k) for k in ("id", "titulo", "teoria", "enunciado", "inicial", "pistas", "jefe", "modo", "modulo")}
                                              for m in n["misiones"]]} for n in c["niveles"]]}
    return out


# =============================================================================
#  Compilar y calificar con el rustc de la PC
# =============================================================================
def buscar_rustc() -> str | None:
    r = shutil.which("rustc")
    if r:
        return r
    for base in (os.path.expanduser("~/.cargo/bin"), os.path.join(os.environ.get("USERPROFILE", ""), ".cargo", "bin")):
        for nombre in ("rustc.exe", "rustc"):
            p = os.path.join(base, nombre)
            if os.path.isfile(p):
                return p
    return None


def version() -> str:
    r = buscar_rustc()
    if not r:
        return ""
    try:
        return subprocess.run([r, "--version"], capture_output=True, text=True, timeout=15, **_sin_ventana()).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _sin_ventana() -> dict:
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def _limpiar_err(texto: str, ruta: str) -> str:
    texto = texto.replace(ruta, "main.rs").replace(ruta.replace("\\", "/"), "main.rs")
    return re.sub(r"note: run with `RUST_BACKTRACE=1`[^\n]*\n?", "", texto)


def compilar_y_correr(codigo: str, carpeta_tmp: str, *, pruebas: str = "", entrada: str = "", edicion: str = "2021",
                      modo_test: bool = False) -> dict:
    """Compila (si hay pruebas, en modo --test con un módulo oculto) y corre. Borra todo al terminar."""
    rustc = buscar_rustc()
    if not rustc:
        return {"ok": False, "fase": "rustc", "fallo": "No encontré rustc. Instala Rust con rustup (https://rustup.rs) y reinicia NetLab."}
    os.makedirs(carpeta_tmp, exist_ok=True)
    d = tempfile.mkdtemp(prefix="rust_", dir=carpeta_tmp)
    try:
        fuente = os.path.join(d, "main.rs")
        exe = os.path.join(d, "prog.exe" if os.name == "nt" else "prog")
        texto = codigo
        if pruebas:
            texto += ("\n\n#[cfg(test)]\n#[allow(unused)]\nmod pruebas_netlab {\n    use super::*;\n"
                      + pruebas + "\n}\n")
        with open(fuente, "w", encoding="utf-8") as f:
            f.write(texto)
        con_tests = bool(pruebas) or modo_test
        cmd = [rustc, "--edition", edicion, "-C", "debuginfo=0", "--color", "never", "-A", "dead_code", "-A", "unused",
               fuente, "-o", exe] + (["--test"] if con_tests else [])
        try:
            c = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90, cwd=d, **_sin_ventana())
        except subprocess.TimeoutExpired:
            return {"ok": False, "fase": "compilar", "fallo": "El compilador tardó demasiado (más de 90 s)."}
        avisos = _limpiar_err(c.stderr, fuente)
        if c.returncode != 0:
            return {"ok": False, "fase": "compilar", "fallo": avisos.strip()[-6000:]}
        args = [exe] + (["--test-threads", "1", "--color", "never"] if con_tests else [])
        entorno = {**os.environ, "RUST_BACKTRACE": "0"}
        try:
            r = subprocess.run(args, input=entrada, env=entorno, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=10, cwd=d, **_sin_ventana())
        except subprocess.TimeoutExpired:
            return {"ok": False, "fase": "correr", "fallo": "Tu programa tardó más de 10 s (¿un ciclo infinito o un deadlock?).", "avisos": avisos}
        return {"ok": True, "codigo_salida": r.returncode, "stdout": _limpiar_err(r.stdout, fuente)[-20000:], "stderr": _limpiar_err(r.stderr, fuente)[-6000:], "avisos": avisos[-3000:]}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _resultados_tests(stdout: str) -> list[dict]:
    res = []
    limpia = lambda n: n.replace("pruebas_netlab::", "").replace("tests::", "").replace("_", " ")  # noqa: E731
    for m in re.finditer(r"^test (\S+) \.\.\. (ok|FAILED)", stdout, re.M):
        res.append({"prueba": limpia(m.group(1)), "ok": m.group(2) == "ok"})
    fallos = {}
    for m in re.finditer(r"---- (\S+) stdout ----\n(.*?)(?=\n---- |\n\nfailures:|\Z)", stdout, re.S):
        fallos[limpia(m.group(1))] = m.group(2).strip()[:800]
    for r in res:
        if not r["ok"] and r["prueba"] in fallos:
            r["detalle"] = fallos[r["prueba"]]
    return res


def calificar(mid: str, codigo: str, carpeta_tmp: str) -> dict:
    m = MISIONES.get(mid)
    if not m:
        return {"error": "misión desconocida"}
    if m["modo"] == "cargo":
        from . import rustproj
        return rustproj.calificar_cargo(codigo, carpeta_tmp, pruebas=m["pruebas"])
    if m["modo"] == "chisel":
        from . import chisel_lab
        return chisel_lab.calificar(m, codigo)
    if m["modo"] == "python":
        from . import pytorch_lab
        return pytorch_lab.calificar(m, codigo, carpeta_tmp)
    reglas = []
    for patron, msg in m["requiere"]:
        if not re.search(patron, codigo, re.M):
            reglas.append(msg or f"Falta: {patron}")
    for patron, msg in m["prohibido"]:
        if msg and re.search(patron, codigo, re.M):
            reglas.append(msg)
    if "todo!()" in codigo:
        reglas.append("Todavía hay `todo!()` sin resolver")
    if m["modo"] == "salida":
        r = compilar_y_correr(codigo, carpeta_tmp, entrada=m["entrada"])
        if not r["ok"]:
            return {"aprobado": False, **r, "reglas": reglas}
        esperado = [l.rstrip() for l in m["salida"].strip().splitlines()]
        obtenido = [l.rstrip() for l in r["stdout"].strip().splitlines()]
        pruebas = [{"prueba": "la salida es exactamente la pedida", "ok": esperado == obtenido,
                    "detalle": "" if esperado == obtenido else f"Esperaba:\n{m['salida']}\n\nSalió:\n{r['stdout'].strip()}"}]
        if r["codigo_salida"] != 0:
            pruebas.append({"prueba": "el programa termina sin panic", "ok": False, "detalle": r["stderr"][-800:]})
        return {"aprobado": all(p["ok"] for p in pruebas) and not reglas, "pruebas": pruebas, "reglas": reglas,
                "stdout": r["stdout"], "avisos": r.get("avisos", "")}
    r = compilar_y_correr(codigo, carpeta_tmp, pruebas=m["pruebas"])
    if not r["ok"]:
        return {"aprobado": False, **r, "reglas": reglas}
    pruebas = _resultados_tests(r["stdout"])
    if not pruebas:
        return {"aprobado": False, "fase": "correr", "fallo": (r["stdout"] + "\n" + r["stderr"]).strip()[-3000:], "reglas": reglas}
    return {"aprobado": all(p["ok"] for p in pruebas) and not reglas, "pruebas": pruebas, "reglas": reglas, "avisos": r.get("avisos", "")}


# =============================================================================
#  Rustlings (los 90+ ejercicios oficiales, MIT) y retos generados por IA
# =============================================================================
def rustlings_desde_zip(zip_ruta: str) -> list[dict]:
    """Lee el .zip del repo de rustlings: ejercicio, solución y pista de cada uno (en el orden del curso)."""
    import tomllib
    import zipfile
    out = []
    with zipfile.ZipFile(zip_ruta) as z:
        nombres = z.namelist()
        info = next(n for n in nombres if n.endswith("rustlings-macros/info.toml"))
        raiz = info.split("rustlings-macros/")[0]
        datos = tomllib.loads(z.read(info).decode("utf-8"))
        for e in datos.get("exercises", []):
            d = e.get("dir", "")
            ej = f"{raiz}exercises/{d + '/' if d else ''}{e['name']}.rs"
            so = f"{raiz}solutions/{d + '/' if d else ''}{e['name']}.rs"
            if ej not in nombres:
                continue
            codigo = z.read(ej).decode("utf-8")
            if re.search(r"\b(tokio|extern crate)\b", codigo) or e.get("strict_clippy") or e.get("input_files"):
                continue  # necesitan crates o clippy: fuera del lab
            out.append({"nombre": e["name"], "tema": re.sub(r"^\d+_", "", d).replace("_", " ") or "quizzes",
                        "test": e.get("test", True), "pista": e.get("hint", "").strip(), "codigo": codigo,
                        "solucion": z.read(so).decode("utf-8") if so in nombres else ""})
    return out


def calificar_libre(codigo: str, carpeta_tmp: str, *, pruebas: str = "", con_tests: bool = True, edicion: str = "2021") -> dict:
    """Califica código suelto: con pruebas (ocultas o dentro del archivo) o, si no hay, que compile y corra sin panic."""
    if con_tests:
        r = compilar_y_correr(codigo, carpeta_tmp, pruebas=pruebas, edicion=edicion, modo_test=True)
        if not r["ok"]:
            return {"aprobado": False, **r, "reglas": []}
        pr = _resultados_tests(r["stdout"])
        if not pr:
            return {"aprobado": False, "fase": "correr", "fallo": (r["stdout"] + "\n" + r["stderr"]).strip()[-3000:] or "No hubo pruebas.", "reglas": []}
        return {"aprobado": all(p["ok"] for p in pr), "pruebas": pr, "reglas": [], "avisos": r.get("avisos", "")}
    r = compilar_y_correr(codigo, carpeta_tmp, edicion=edicion)
    if not r["ok"]:
        return {"aprobado": False, **r, "reglas": []}
    ok = r["codigo_salida"] == 0
    pr = [{"prueba": "compila y corre sin errores", "ok": ok, "detalle": "" if ok else r["stderr"][-800:]}]
    return {"aprobado": ok, "pruebas": pr, "reglas": [], "stdout": r["stdout"], "avisos": r.get("avisos", "")}


ESQUEMA_RETO = {"type": "object", "properties": {
    "titulo": {"type": "string"}, "teoria": {"type": "string"}, "enunciado": {"type": "string"},
    "inicial": {"type": "string"}, "solucion": {"type": "string"}, "pruebas": {"type": "string"},
    "pistas": {"type": "array", "items": {"type": "string"}}},
    "required": ["titulo", "teoria", "enunciado", "inicial", "solucion", "pruebas", "pistas"]}

ENFOQUE = {
    "rust": "Rust aplicado a ciberseguridad y redes (parsers de logs y paquetes, validación de entradas, criptografía didáctica, "
            "detección de ataques, manejo seguro de memoria)",
    "ia": "inteligencia artificial y machine learning programados desde cero en Rust (álgebra lineal, estadística, "
          "gradientes, redes neuronales, clasificadores, detección de anomalías en tráfico, NLP básico)",
    "cpu": "arquitectura de computadoras programada en Rust (bits, aritmética binaria, compuertas, ALU, codificación de "
           "instrucciones RISC-V, emuladores, memoria caché, pila y vulnerabilidades de memoria)",
}


def mensajes_reto(curso: str, nivel: int, dificultad: str, previos: list[str]) -> list[dict]:
    c = CURSOS[curso]
    n = c["niveles"][min(nivel, len(c["niveles"]) - 1)]
    temas = "; ".join(m["titulo"].replace("JEFE: ", "") for m in n["misiones"])
    return [
        {"role": "system", "content": "Eres un autor experto de ejercicios de programación tipo Rustlings/Exercism. Escribes en español "
         "de México. Generas UN ejercicio de Rust autocontenido (solo la librería estándar, edición 2021) con pruebas que lo califican. "
         "Reglas estrictas: 'inicial' es el código que recibe el alumno: mismas firmas que la solución pero con el cuerpo `todo!()` "
         "(debe compilar). Los campos de código van en texto plano, SIN bloques ``` de Markdown. 'solucion' es el código completo y correcto. Ambos incluyen `fn main() {}`. 'pruebas' contiene SOLO 4 a 6 "
         "funciones `#[test] fn nombre_descriptivo_en_espanol() { ... }` que usan las funciones del ejercicio (van dentro de un módulo "
         "con `use super::*;`, no lo escribas). Las pruebas deben ser deterministas, sin red, sin archivos, sin hilos que duerman, "
         "y cubrir casos borde. 'teoria' explica el concepto en 3-6 líneas Markdown; 'enunciado' dice exactamente qué implementar "
         "(firmas incluidas); 'pistas' son 2 pistas progresivas que no dan la solución completa."},
        {"role": "user", "content": f"Curso: {c['nombre']} — enfoque: {ENFOQUE[curso]}.\nNivel: {n['nombre']} ({n['cap']}); temas del nivel: {temas}.\n"
         f"Dificultad: {dificultad}.\nNo repitas estos ejercicios ya hechos: {', '.join(previos[-15:]) or 'ninguno'}.\n"
         "Inventa un ejercicio nuevo, realista y útil. Devuelve solo el JSON."},
    ]


def _sin_cercas(t: str) -> str:
    """Los modelos a veces envuelven el código en ```rust … ```: se lo quitamos."""
    t = (t or "").strip()
    m = re.search(r"```[a-zA-Z]*\s*\n(.*?)```", t, re.S)
    if m:
        t = m.group(1)
    return t.replace("```rust", "").replace("```", "").strip() + "\n"


def validar_reto(r: dict, carpeta_tmp: str) -> tuple[bool, str]:
    """El reto solo sirve si su solución pasa sus pruebas y el código inicial NO."""
    for k in ("inicial", "solucion", "pruebas"):
        if isinstance(r.get(k), str):
            r[k] = _sin_cercas(r[k])
    if not all(isinstance(r.get(k), str) and r[k].strip() for k in ("inicial", "solucion", "pruebas", "enunciado")):
        return False, "faltan campos"
    if len(re.findall(r"#\[test\]", r["pruebas"])) < 3:
        return False, "pocas pruebas (mínimo 3 #[test])"
    if re.search(r"mod\s+tests|use\s+super", r["pruebas"]):
        r["pruebas"] = re.sub(r"\}\s*$", "", re.sub(r"(?s)^.*?use\s+super::\*;\s*", "", r["pruebas"]).rstrip(), count=1)
    s = calificar_libre(r["solucion"], carpeta_tmp, pruebas=r["pruebas"])
    if not s["aprobado"]:
        return False, "la solución no pasa sus pruebas: " + (s.get("fallo") or str([p for p in s.get("pruebas", []) if not p["ok"]]))[:1500]
    i = calificar_libre(r["inicial"], carpeta_tmp, pruebas=r["pruebas"])
    if i["aprobado"]:
        return False, "el código inicial ya pasa las pruebas (no hay nada que hacer)"
    if i.get("fase") == "compilar":
        return False, "el código inicial no compila: " + i.get("fallo", "")[:1200]
    return True, ""
