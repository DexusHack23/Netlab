# NetLab

Prácticas de Packet Tracer, exámenes CCNA y ejercicios de Wireshark generados con tus modelos de Ollama, con
revisión automática. (Antes se llamaba "Lab CCNA"; la carpeta conserva ese nombre para no romper PTBuilder
ni la asociación de los `.pkt`.)

## Instalar (una vez)

```powershell
cd "$env:USERPROFILE\MIS CARPETAS\Lab CCNA"
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

Crea el acceso directo en el Escritorio y en el menú Inicio (**Ctrl+Alt+L**) y descarga PTBuilder.
Luego, en Packet Tracer: **Extensions → Scripting → Configure PT Script Modules → Add…** y elige
`extension\Builder.pts`.

## Packet Tracer siempre al mismo tamaño

Packet Tracer 9.0.1 no guarda el tamaño de letra, así que se agranda todo con una escala (por defecto
1.25 = 125%; se cambia en Ajustes). Para que tus accesos directos y el doble clic en `.pkt`/`.pka`
también la usen, corre una vez:

```powershell
powershell -ExecutionPolicy Bypass -File .\asociar_pkt.ps1
```

Para deshacerlo: el mismo comando con `-Quitar`.

## Laboratorios JITL

La sección "Laboratorios JITL" lista los `.pkt` de `MIS CARPETAS\1-JITL`, los abre con tu escala y te
arma un examen o una práctica extra del tema de cada día.

## Constructor de topologías

Describe la red ("3 routers en triángulo con OSPF…") y te da el diagrama, el direccionamiento, la
configuración y el script de PTBuilder: solo cables o ya configurada. Antes de mostrártela revisa que
los puertos existan en cada modelo, que no se repitan IPs ni puertos, que cada cable una equipos de la
misma subred y que la configuración coincida con el direccionamiento.

## Construir la práctica dentro de Packet Tracer

En cada práctica, "Construir en Packet Tracer" te da un script (se copia solo). En Packet Tracer:
**Extensions → Builder Code Editor**, pega y **Run**. Hay tres niveles: solo topología, topología +
config inicial, o la práctica completa ya resuelta.

Se abre en su propia ventana. Al cerrarla (o con Ajustes → Cerrar la app) se apaga sola y descarga
los modelos de la GPU. No usa librerías externas: solo Python y Ollama.

## Cómo funciona

| Parte | Quién decide |
|---|---|
| Qué temas hay y en qué orden | Ruta fija (temario CCNA 200-301 + extras) |
| Escribir la práctica / examen | Modelo pesado (`gpt-oss:20b` por defecto) |
| Comprobar que la práctica es coherente | Código: su solución debe pasar sus verificaciones y las subredes deben cuadrar; si no, se la regresa al modelo (máx. 2 veces) |
| Comprobar la clave del examen | El modelo contesta sus propias preguntas sin ver la clave; las que no coinciden se descartan |
| Calificar tu práctica | Código determinista (lee tu running-config, `show vlan brief`, `ping`, `ipconfig`) |
| Explicarte los errores | Modelo ligero (`qwen3:4b-instruct`), sin poder contradecir al verificador |

Para revisar: en cada router/switch, `show running-config` y copia la salida (o pega los comandos que
tecleaste, abreviados o no). En las PCs: `ipconfig` y los `ping` que pida la práctica.

## Capturas en vez de copiar y pegar

En "Revisar mi práctica" puedes pegar (Ctrl+V) una captura de la CLI o usar el botón 📷. El modelo de
visión (`qwen3-vl:8b`, se cambia en Ajustes) la convierte en texto y la pone en la caja; revísalo antes de
calificar. Si no lo tienes: `ollama pull qwen3-vl:8b`.

## Teoría

Lecciones de cada tema del CCNA y de Wireshark (WCA-101), en español o en inglés. Las escribe el modelo pesado
con tus guías como referencia cuando hay algo del tema. Se pueden escuchar con las voces de Windows (▶ Escuchar,
pausa, velocidad, voz; clic en un párrafo para leer desde ahí) y puedes preguntarle al tutor escribiendo o
dictando con el micrófono 🎤. Si no aparece una voz en inglés o español, agrégala en Windows: Configuración →
Hora e idioma → Voz → Agregar voces.

## Wireshark

Dieciséis tipos de captura en 4 niveles con estrellas y candados (de handshake + HTTP hasta TLS/SNI, ventana TCP
en cero, SYN flood, VLANs 802.1Q, traceroute/ICMP, HTTP Basic, exfiltración por DNS y DHCP starvation). Además:
captura en vivo de tu tráfico real con preguntas exactas (se borra al cerrar), ejercicios de filtros de captura
BPF (se compilan con dumpcap y se comparan) y examen tipo WCA-101. Cada `.pcap` lo arma el código con una semilla, así que la clave sale de los propios
paquetes, no de la IA. Al generarla, tshark comprueba cada filtro de referencia y cada conteo; lo que no cuadra
se descarta. Tus filtros se califican corriéndolos con tshark: deben mostrar exactamente los mismos paquetes.
"Analizar mi captura" pasa tu archivo por tshark (protocolos, conversaciones, info experta) y el modelo te lo
explica; el archivo se borra al terminar.

## Linux

Misiones en una terminal de Ubuntu simulada dentro de la app (no toca tu PC): moverte, archivos, buscar en logs,
tuberías tipo SOC (sacar las IPs de un ataque de fuerza bruta), permisos, servicios, firewall y red. Cada misión
da hasta 3 ★ (pistas o ver la solución bajan estrellas) y los niveles se abren al completar la mitad del anterior.
Hay terminal libre (`help`, `man comando`, Tab para completar, ↑ para el historial), lecciones de Linux en Teoría y
examen de Linux. Debajo de la terminal te explica qué hizo cada comando, y puedes preguntarle al tutor.

## Arrastrar y soltar

Retos de clasificar, emparejar y ordenar como los del examen del CCNA (capas OSI, TCP/UDP, puertos, IPv4/IPv6,
cables, distancia administrativa, estados de OSPF y STP, DHCP, SSH…), más Wireshark y Linux. Respuestas
exactas, sin IA. Se arrastra con el mouse o tocando la tarjeta y luego la caja.

## Modo juego

En la Ruta de CCNA cada tema da ★ (6), ★★ (8) y ★★★ (9.5); cada nivel se abre al dominar la mitad del anterior o al
vencer a su **jefe final** (15 preguntas de todo el nivel, necesitas 8). En "Tu progreso" está el medidor
**¿Estoy listo?** para el CCNA (por dominio y con su peso real), el WCA-101 y Linux.

Todo da XP: prácticas, exámenes, subneteo, Wireshark, misiones y lecciones. Subes de nivel, mantienes una racha de
días estudiando y desbloqueas logros. Se calcula con tu historial, así que no guarda nada aparte. En los exámenes y
en Wireshark, cada respuesta mal tiene "🤖 Explícamelo" (el tutor usa tus guías).

## Red vs Blue

Un atacante (la IA elige sus jugadas y se adapta a lo que fallas) contra ti, con reloj y 3 dificultades:
- **Linux:** entra a tu servidor en vivo (fuerza bruta SSH, usuario con UID 0, cron, minero, llave SSH, borra huellas en
  Difícil). Lo ves en los logs y lo sacas con ufw, usermod -L, userdel, pkill, sed… El SIEM da alertas en Fácil/Normal.
- **Wireshark:** oleadas de tráfico; contestas quién/qué, la técnica y el filtro que lo aísla.
- **CCNA:** alertas de switches/routers que frenas tecleando la config de IOS (DHCP snooping, port-security, BPDU Guard,
  ACL en VTY, SSH, DAI…). El código revisa tu configuración.
Al final: cronología, lo que se te pasó con el comando correcto y un reporte de SOC del tutor.

## Cuaderno de errores y misión del día

Lo que fallas (exámenes, filtros de Wireshark, subneteo, arrastrar, misiones de Linux en las que viste la solución y
ataques de Red vs Blue) entra a **🧠 Repaso** y vuelve en 1, 2, 4, 8, 16, 32 y 60 días según lo aciertes (repaso
espaciado). La **misión del día** (arriba en la Ruta) te arma 4 tareas cortas y da +50 XP al completarla. Los exámenes
contestados se pueden repetir; se queda tu mejor nota.

## Guías (tu material de consulta)

Echa PDFs, `.txt` o `.md` en la carpeta `guias` y en la sección Guías dale "Indexar lo nuevo". La app los
parte en fragmentos y los vectoriza con un modelo de embeddings de Ollama (`qwen3-embedding:0.6b` si lo
tienes; si no, `bge-m3` o `nomic-embed-text`). Al generar prácticas, exámenes o analizar capturas busca lo
del tema y se lo pasa al modelo como referencia. `wireshark-campos-filtros.txt` (salida de
`tshark -G fields`) no se vectoriza: sirve para sugerirte el nombre correcto cuando un filtro trae un campo
que no existe. Los filtros que sugiere el modelo al analizar tu captura se prueban con tshark y se marcan si
no son válidos. Para leer PDFs hace falta `pypdf` en el Python de NetLab.

## Qué guarda

Solo `datos\historial.db` (prácticas, intentos, exámenes y ejercicios de Wireshark), `datos\guias.db`
(los vectores de tus guías; se rehacen solos si cambian) y `datos\config.json`.
Los `.pcap` que abre en Wireshark van a `datos\tmp` y se borran al cerrar la app (y al abrirla, por si se
cerró de golpe). Nada de `__pycache__`.

## Pruebas

`python -B -m pruebas.test_checker` comprueba el verificador con configuraciones de ejemplo.
