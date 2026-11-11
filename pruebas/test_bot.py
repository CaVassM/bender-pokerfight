"""Pruebas de bot.py: el circuito de decisión de la Capa 0."""

from bot import Bender
from params import cargar_params
from registro import Registro
from test_conexion import ESTADO, solicitar


def hacer_bot(tmp_path):
    registro = Registro(str(tmp_path / "s.jsonl"), eco_stderr=False)
    bot = Bender(cargar_params(), registro)
    bot.al_conectar("yo", 0, False)
    return bot, registro


def mano_inicio():
    return {"tipo": "mano_inicio", "version": "1.0.0", "cartas": [{"rango": 14, "palo": 3}, {"rango": 13, "palo": 3}], "estado": ESTADO}


def test_con_cartas_juega_check_o_fold_y_registra_n_y_tiempo(tmp_path):
    bot, registro = hacer_bot(tmp_path)
    bot.al_mensaje(mano_inicio())
    assert bot.decidir(solicitar(["fold", "call", "raise"])) == {"tipo": "fold"}
    assert bot.decidir(solicitar(["fold", "check", "bet"])) == {"tipo": "check"}
    registro.cerrar()
    texto = (tmp_path / "s.jsonl").read_text(encoding="utf-8")
    assert '"tipo":"decision"' in texto and '"n_sim"' in texto and '"tiempo_s"' in texto
    assert "As Ks" in texto


def test_reconexion_a_mitad_de_mano_sin_cartas_juega_la_segura(tmp_path):
    bot, registro = hacer_bot(tmp_path)          # proceso nuevo: no vio el mano_inicio
    assert bot.decidir(solicitar(["fold", "check", "bet"])) == {"tipo": "check"}
    assert bot.decidir(solicitar(["fold", "call", "raise"])) == {"tipo": "fold"}
    registro.cerrar()
    assert "sin cartas" in (tmp_path / "s.jsonl").read_text(encoding="utf-8")


def test_cartas_de_otra_mano_no_se_usan(tmp_path):
    bot, registro = hacer_bot(tmp_path)
    bot.al_mensaje(mano_inicio())                # m-1
    msg = solicitar(["fold", "check"])
    msg["estado"] = dict(ESTADO, id_mano="m-2")  # la mesa ya pasó a otra mano
    bot.decidir(msg)
    registro.cerrar()
    assert "sin cartas" in (tmp_path / "s.jsonl").read_text(encoding="utf-8")
