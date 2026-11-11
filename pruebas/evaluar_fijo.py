#!/usr/bin/env python3
"""Corre una evaluación (evaluar.py, campana.py, throughput.py...) desde un git worktree de un COMMIT FIJO.

Regla de higiene: ninguna medición se corre desde la carpeta donde se edita. Cada proceso de Bender importa
el código al arrancar, así que editar a mitad de una corrida la contamina (pasó con capa1-v4). Aquí el
código evaluado es una copia inmutable del commit: se puede seguir editando mientras corre.

  python bender/pruebas/evaluar_fijo.py [--commit HASH] [--sucio] [--script evaluar.py] -- <argumentos del script>

  - Sin --commit usa HEAD de bender/. Si hay cambios sin commitear en bender/ (fuera de lo ignorado), se niega:
    primero se hace commit (--sucio lo permite, avisando, pero entonces NO es reproducible).
  - El worktree vive FUERA del kit y de su repo: <carpeta del kit>/../bender_eval/<hash>/bender, con
    `bin/` y `bots/` enlazados (junction) al kit.
  - Las salidas van a la carpeta de siempre (bender/pruebas/salidas) y el JSON de la evaluación guarda el commit.
"""

import argparse
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # raíz del kit
BENDER = os.path.join(RAIZ, "bender")


def git(*args, cwd=BENDER):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(args)} falló: {r.stderr.strip()}")
    return r.stdout.strip()


def enlazar(link, destino):
    """Junction de Windows (no pide permisos de administrador); en otros sistemas, symlink."""
    if os.path.exists(link):
        return
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", link, destino], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"no se pudo enlazar {link}: {r.stdout} {r.stderr}")
    else:
        os.symlink(destino, link)


def preparar_worktree(commit):
    base = os.path.join(os.path.dirname(RAIZ), "bender_eval", commit[:8])
    destino = os.path.join(base, "bender")
    if not os.path.isdir(destino):
        os.makedirs(base, exist_ok=True)
        git("worktree", "add", "--detach", destino, commit)
    enlazar(os.path.join(base, "bin"), os.path.join(RAIZ, "bin"))
    enlazar(os.path.join(base, "bots"), os.path.join(RAIZ, "bots"))
    return base


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--commit", default=None)
    ap.add_argument("--sucio", action="store_true", help="permite cambios sin commitear (NO reproducible)")
    ap.add_argument("--script", default="evaluar.py")
    ap.add_argument("-h", "--help", action="store_true")
    args, resto = ap.parse_known_args()
    if args.help:
        print(__doc__)
        return 0
    if resto and resto[0] == "--":
        resto = resto[1:]

    # Solo importan los cambios en código/parámetros: la documentación (docs/, *.md) no afecta una medición.
    sucio = "\n".join(l for l in git("status", "--porcelain").splitlines()
                      if not l[3:].startswith("docs/") and not l.endswith(".md"))
    if sucio and not args.sucio:
        sys.exit("hay cambios sin commitear en bender/ (haz commit primero, o usa --sucio):\n" + sucio)
    if sucio:
        print("AVISO: se evalúa el último commit, NO los cambios sin commitear.", file=sys.stderr)
    commit = git("rev-parse", args.commit or "HEAD")
    base = preparar_worktree(commit)
    print(f"[evaluar_fijo] commit {commit[:8]} en {base}", flush=True)

    env = dict(os.environ, BENDER_SALIDAS=os.path.join(BENDER, "pruebas", "salidas"), BENDER_COMMIT=commit[:8])
    script = os.path.join(base, "bender", "pruebas", args.script)
    return subprocess.run([sys.executable, script, *resto], cwd=base, env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
