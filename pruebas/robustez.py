#!/usr/bin/env python3
"""Robustez con la mesa REAL (pendientes 2 y 3).

Escenario `proxy` (pendiente 2): un proxy TCP local entre Bender y bin/mesa corta la conexión a mitad de
mano, de forma brusca (shutdown + close, sin avisar), justo en la N-ésima `solicitar_accion` que la mesa le
manda a Bender. Dos modos de corte:
    tras   : el proxy REENVÍA la solicitud y luego corta (Bender la recibe, y se cae al responder / al leer)
    antes  : el proxy corta SIN reenviarla (Bender nunca se entera; la mesa espera su plazo y juega la acción segura)
Se comprueba que Bender (el MISMO proceso) reconecta solo con el mismo token, que la mesa le devuelve su silla
y su saldo, que sigue jugando y que la mesa termina todas sus rondas.

Escenario `relanzar` (pendiente 3): se mata el proceso de Bender cuando tiene una decisión PENDIENTE (recibió
`solicitar_accion` y todavía no respondió; se alarga con un retardo artificial para poder atraparla) y se
lo relanza con el mismo token. El proceso nuevo no vio el `mano_inicio` de esa mano: debe jugar la acción
segura ("sin cartas de esta mano") hasta la mano siguiente y retomar su silla.

Uso: bender/.venv/Scripts/python.exe bender/pruebas/robustez.py [--escenario ambos] [--rondas 60]
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluar as E  # noqa: E402

SALIDA = os.path.join(E.SALIDAS, "robustez")
RIVALES = ["base", "conservador", "bandido", "espia"]


def leer_jsonl(ruta):
    out = []
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                try:
                    out.append(json.loads(linea))
                except ValueError:
                    pass
    return out


class Proxy:
    """Proxy TCP que corta la conexión en las `cortes` (números globales de solicitar_accion)."""

    def __init__(self, puerto, puerto_mesa, cortes, modo):
        self.puerto, self.puerto_mesa, self.cortes, self.modo = puerto, puerto_mesa, set(cortes), modo
        self.n = 0
        self.eventos = []                 # (instante, N de la solicitud, id_mano)
        self.conexiones = 0
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", puerto))
        self.srv.listen(8)
        self.vivo = True
        threading.Thread(target=self._aceptar, daemon=True).start()

    def _aceptar(self):
        while self.vivo:
            try:
                cli, _ = self.srv.accept()
            except OSError:
                return
            self.conexiones += 1
            try:
                up = socket.create_connection(("127.0.0.1", self.puerto_mesa), timeout=5)
            except OSError:
                cli.close()
                continue
            up.settimeout(None)
            threading.Thread(target=self._bot_a_mesa, args=(cli, up), daemon=True).start()
            threading.Thread(target=self._mesa_a_bot, args=(cli, up), daemon=True).start()

    @staticmethod
    def _cortar(*socks):
        for s in socks:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass

    def _bot_a_mesa(self, cli, up):
        try:
            while True:
                d = cli.recv(65536)
                if not d:
                    break
                up.sendall(d)
        except OSError:
            pass
        self._cortar(cli, up)

    def _mesa_a_bot(self, cli, up):
        buf = b""
        try:
            while True:
                d = up.recv(65536)
                if not d:
                    break
                buf += d
                while b"\n" in buf:
                    linea, buf = buf.split(b"\n", 1)
                    linea += b"\n"
                    if b'"solicitar_accion"' in linea:
                        self.n += 1
                        if self.n in self.cortes:
                            try:
                                id_mano = json.loads(linea)["estado"]["id_mano"]
                            except (ValueError, KeyError):
                                id_mano = "?"
                            self.eventos.append((time.time(), self.n, id_mano))
                            if self.modo == "tras":
                                cli.sendall(linea)
                            self._cortar(cli, up)               # corte brusco
                            return
                    cli.sendall(linea)
        except OSError:
            pass
        self._cortar(cli, up)

    def cerrar(self):
        self.vivo = False
        self._cortar(self.srv)


def levantar_mesa(puerto, rondas, dir_run, timeout_ms=3000):
    os.makedirs(dir_run, exist_ok=True)
    abiertos, procesos = [], []

    def lanzar(cmd, nombre, env=None):
        out = open(os.path.join(dir_run, nombre + ".out"), "w", encoding="utf-8")
        abiertos.append(out)
        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, cwd=E.RAIZ, env=env)
        procesos.append(p)
        return p

    mesa = lanzar([os.path.join(E.BIN, "mesa" + E.EXE), "-addr", f"127.0.0.1:{puerto}", "-jugadores", "6", "-min-jugadores", "5",
                   "-rondas", str(rondas), "-stack", "10000", "-ciega-chica", "50", "-ciega-grande", "100",
                   "-timeout-ms", str(timeout_ms), "-id", "robustez"], "mesa")
    ruta = os.path.join(dir_run, "mesa.out")
    for _ in range(100):
        time.sleep(0.1)
        if "escuchando" in open(ruta, encoding="utf-8", errors="replace").read():
            break
    return mesa, lanzar, procesos, abiertos


def lanzar_bender(lanzar, puerto, dir_run, nombre, token, retardo_s=0.0):
    ruta_params = os.path.join(dir_run, f"params-{nombre}.json")
    with open(ruta_params, "w", encoding="utf-8") as f:
        json.dump({"debug": {"retardo_s": retardo_s}, "rivales": {"persistir": False}}, f)
    env = dict(os.environ, BENDER_TOKEN=token)
    return lanzar([sys.executable, E.BENDER_MAIN, "-addr", f"127.0.0.1:{puerto}", "-silencioso",
                   "-log", os.path.join(dir_run, nombre + ".jsonl"), "-params", ruta_params], nombre, env)


def terminar(mesa, procesos, abiertos, espera=240):
    try:
        mesa.wait(timeout=espera)
        terminado = True
    except subprocess.TimeoutExpired:
        terminado = False
    for p in procesos:
        if p.poll() is None:
            p.kill()
    for a in abiertos:
        a.close()
    return terminado


def resumen_mesa(dir_run):
    texto = open(os.path.join(dir_run, "mesa.out"), encoding="utf-8", errors="replace").read()
    rondas, fichas = 0, {}
    for l in texto.splitlines():
        if "partida terminada" in l:
            rondas = int(l.split(",")[1].split()[0])
        if l.strip().startswith("#"):
            p = l.split()
            fichas[p[1]] = int(p[2])
    return rondas, fichas


def escenario_proxy(modo, cortes, rondas, puerto):
    dir_run = os.path.join(SALIDA, f"proxy-{modo}")
    mesa, lanzar, procesos, abiertos = levantar_mesa(puerto, rondas, dir_run)
    proxy = Proxy(puerto + 1, puerto, cortes, modo)
    for b in RIVALES:
        lanzar(E.comando_rival(b, puerto, f"k-{b}"), b)
        time.sleep(0.2)
    bender = lanzar_bender(lanzar, puerto + 1, dir_run, "bender", "bender-robustez")
    terminado = terminar(mesa, procesos, abiertos)
    vivo_al_final = bender.poll() is None or bender.returncode in (0, None)
    proxy.cerrar()
    regs = leer_jsonl(os.path.join(dir_run, "bender.jsonl"))
    conex = [r for r in regs if r["tipo"] == "conexion"]
    decis = [r for r in regs if r["tipo"] == "decision"]
    redes = [r for r in regs if r["tipo"] == "red"]
    errores = [r for r in regs if r["tipo"] in ("error", "accion_invalida")]
    rondas_j, fichas = resumen_mesa(dir_run)
    # decisiones después de cada reconexión
    t_reconex = [c["t"] for c in conex if c.get("reconexion")]
    despues = [sum(1 for d in decis if d["t"] > t) for t in t_reconex]
    sin_cartas = sum(1 for d in decis if "sin cartas" in d.get("motivo", ""))
    return {"escenario": f"proxy / corte {modo} en las solicitudes {sorted(cortes)}", "mesa terminó": terminado,
            "rondas jugadas": rondas_j, "cortes hechos": len(proxy.eventos), "conexiones al proxy": proxy.conexiones,
            "reconexiones de Bender": len(t_reconex), "silla antes/después": sorted({c["silla"] for c in conex}),
            "decisiones totales": len(decis), "decisiones tras cada reconexión": despues, "decisiones 'sin cartas'": sin_cartas,
            "errores/inválidas": len(errores), "errores de red anotados": len(redes), "fichas finales de Bender": fichas.get("bender-robustez")}


def escenario_relanzar(kills, rondas, puerto):
    dir_run = os.path.join(SALIDA, "relanzar")
    mesa, lanzar, procesos, abiertos = levantar_mesa(puerto, rondas, dir_run, timeout_ms=5000)
    for b in RIVALES:
        lanzar(E.comando_rival(b, puerto, f"k-{b}"), b)
        time.sleep(0.2)
    token = "bender-robustez"
    nombre = "bender-1"
    bender = lanzar_bender(lanzar, puerto, dir_run, nombre, token, retardo_s=0.6)
    registros = []
    hechos = 0
    objetivo = 8                                              # primer kill tras ~8 solicitudes respondidas; luego cada ~10
    limite = time.time() + 240
    while mesa.poll() is None and time.time() < limite and hechos < kills:
        time.sleep(0.05)
        regs = leer_jsonl(os.path.join(dir_run, nombre + ".jsonl"))
        resp = sum(1 for r in regs if r["tipo"] == "respuesta")
        # ¿hay una solicitud pendiente? (más `msg` solicitar_accion que `respuesta`)
        sol = sum(1 for r in regs if r["tipo"] == "msg" and r["msg"].get("tipo") == "solicitar_accion")
        if resp >= objetivo and sol > resp:
            bender.kill()
            bender.wait()
            registros.append({"kill": hechos + 1, "tras_respuestas": resp, "id_mano_pendiente": next(
                (r["msg"]["estado"]["id_mano"] for r in reversed(regs) if r["tipo"] == "msg" and r["msg"].get("tipo") == "solicitar_accion"), "?")})
            hechos += 1
            time.sleep(0.8)
            nombre = f"bender-{hechos + 1}"
            bender = lanzar_bender(lanzar, puerto, dir_run, nombre, token, retardo_s=0.6)
            objetivo = 10
    terminado = terminar(mesa, procesos, abiertos)
    rondas_j, fichas = resumen_mesa(dir_run)
    sesiones = []
    for i in range(1, hechos + 2):
        regs = leer_jsonl(os.path.join(dir_run, f"bender-{i}.jsonl"))
        conex = [r for r in regs if r["tipo"] == "conexion"]
        decis = [r for r in regs if r["tipo"] == "decision"]
        sesiones.append({"sesion": i, "silla": conex[0]["silla"] if conex else None, "decisiones": len(decis),
                         "sin_cartas": sum(1 for d in decis if "sin cartas" in d.get("motivo", "")),
                         "errores": sum(1 for r in regs if r["tipo"] in ("error", "accion_invalida"))})
    return {"escenario": f"relanzar con decisión pendiente ({hechos} veces)", "mesa terminó": terminado, "rondas jugadas": rondas_j,
            "kills": registros, "sesiones": sesiones, "fichas finales de Bender": fichas.get(token)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--escenario", choices=["proxy", "relanzar", "ambos"], default="ambos")
    ap.add_argument("--rondas", type=int, default=60)
    ap.add_argument("--puerto", type=int, default=9900)
    args = ap.parse_args()
    os.makedirs(SALIDA, exist_ok=True)
    resultados = []
    if args.escenario in ("proxy", "ambos"):
        resultados.append(escenario_proxy("tras", [6, 15, 29], args.rondas, args.puerto))
        resultados.append(escenario_proxy("antes", [8, 20], args.rondas, args.puerto + 10))
    if args.escenario in ("relanzar", "ambos"):
        resultados.append(escenario_relanzar(3, args.rondas, args.puerto + 20))
    for r in resultados:
        print("\n== " + r.pop("escenario"))
        for k, v in r.items():
            print(f"   {k}: {v}")
    with open(os.path.join(SALIDA, "resultado.json"), "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=1, default=str)


if __name__ == "__main__":
    main()
