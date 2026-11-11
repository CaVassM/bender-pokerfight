"""Registro de la sesión: un JSONL por sesión.

Cada línea es un objeto JSON con `t` (segundos desde el inicio de la sesión),
`n` (número de línea) y `tipo`. Sirve para entender *por qué* Bender hizo algo:
por cada decisión queda el estado, la equity, la tabla de EV y la acción.

El token NO se escribe nunca aquí: el saludo saliente no se registra, y el
registro enmascara cualquier campo llamado `token`.
"""

import json
import os
import sys
import time

DIR_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


class Registro:
    def __init__(self, ruta=None, eco_stderr=True):
        if ruta is None:
            os.makedirs(DIR_LOGS, exist_ok=True)
            marca = time.strftime("%Y%m%d-%H%M%S")
            ruta = os.path.join(DIR_LOGS, f"sesion-{marca}-{os.getpid()}.jsonl")
        else:
            carpeta = os.path.dirname(os.path.abspath(ruta))
            os.makedirs(carpeta, exist_ok=True)
        self.ruta = ruta
        self.eco_stderr = eco_stderr
        self._inicio = time.monotonic()
        self._n = 0
        # buffering=1 -> línea a línea; además se hace flush explícito para que
        # el log sobreviva si el proceso muere de golpe (kill en las pruebas).
        self._archivo = open(ruta, "a", encoding="utf-8", buffering=1)

    def escribir(self, tipo, **campos):
        self._n += 1
        if "token" in campos:
            campos["token"] = "***"
        registro = {"t": round(time.monotonic() - self._inicio, 4), "n": self._n, "tipo": tipo}
        registro.update(campos)
        try:
            self._archivo.write(json.dumps(registro, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")
            self._archivo.flush()
        except (OSError, ValueError):
            pass  # un fallo de log nunca debe tumbar una decisión

    def log(self, texto):
        """Mensaje de texto: va al JSONL y a stderr (la arena lo muestra con -verboso)."""
        self.escribir("log", texto=texto)
        if self.eco_stderr:
            print(f"[bender] {texto}", file=sys.stderr, flush=True)

    def cerrar(self):
        try:
            self._archivo.close()
        except OSError:
            pass
