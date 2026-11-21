#!/usr/bin/env python3
"""Bender · bot de PokerFight (Python 3.11+).

Uso (lo mismo que hace la arena cuando lo lanza, agregando -addr y -token):

    python bender/main.py -addr localhost:9000 -token <token>

El token se lee de -token o de la variable de entorno BENDER_TOKEN. Nunca está
escrito en el código ni se sube al repositorio.
"""

import argparse
import os
import sys

# Los módulos de Bender son hermanos de este archivo (como en bots/novato).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot import Bender            # noqa: E402
from conexion import Cliente      # noqa: E402
from params import cargar_params  # noqa: E402
from registro import Registro     # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Bender: bot de PokerFight")
    parser.add_argument("-addr", default="localhost:9000", help="dirección de la mesa (host:puerto)")
    parser.add_argument("-token", default=None, help="token de sesión (o variable BENDER_TOKEN)")
    parser.add_argument("-params", default=None, help="JSON con parámetros que sobreescriben los de params.py")

    # Sin ese argumento de logs con normalidad lo guarda en bender/logs
    parser.add_argument("-log", default=None, help="ruta del JSONL de la sesión (por defecto bender/logs/)")
    parser.add_argument("-silencioso", action="store_true", help="no imprime nada en stderr")
    args = parser.parse_args()

    token = args.token or os.environ.get("BENDER_TOKEN")
    if not token:
        print("bender: falta el token (-token o variable BENDER_TOKEN)", file=sys.stderr)
        return 2

    try:
        params = cargar_params(args.params)
    except (OSError, ValueError, KeyError) as error:
        print(f"bender: no se pudieron cargar los parámetros: {error}", file=sys.stderr)
        return 2

    registro = Registro(args.log, eco_stderr=not args.silencioso)
    registro.log(f"Bender arrancando (log: {registro.ruta})")
    bot = Bender(params, registro)
    cliente = Cliente(args.addr, token, bot, params, registro)
    try:
        return cliente.correr()
    except KeyboardInterrupt:
        registro.log("interrumpido por el usuario")
        return 130
    finally:
        registro.cerrar()


if __name__ == "__main__":
    sys.exit(main())
