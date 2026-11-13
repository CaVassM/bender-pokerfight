"""medir_sidepots.py: reparto del bote en principal y lateral con las pilas reales de los mensajes crudos."""

import json

import medir_sidepots as MS


def jug(id_, saldo, apuesta=0, activo=True, allin=False, en_mano=True):
    return {"id": id_, "saldo": saldo, "apuesta_ronda": apuesta, "activo": activo, "allin": allin, "en_mano": en_mano}


def escribir(ruta, decision, jugadores_inicio, jugadores_ahora):
    filas = [{"tipo": "conexion", "id_jugador": "yo", "silla": 0},
             {"tipo": "msg", "msg": {"tipo": "mano_inicio", "estado": {"jugadores": jugadores_inicio}}},
             {"tipo": "msg", "msg": {"tipo": "solicitar_accion", "estado": {"jugadores": jugadores_ahora}}},
             {"tipo": "decision", **decision}]
    ruta.write_text("\n".join(json.dumps(f, separators=(",", ":")) for f in filas) + "\n")      # como Registro.escribir


INICIO = [jug("yo", 10_000), jug("x", 2_000), jug("y", 10_000), jug("z", 10_000)]
AHORA = [jug("yo", 10_000), jug("x", 0, 2_000, allin=True), jug("y", 8_000, 2_000), jug("z", 10_000, 0, activo=False)]


def test_igualar_un_all_in_corto_con_un_pagador_no_crea_lateral(tmp_path):
    escribir(tmp_path / "a.jsonl", {"etapa": "flop", "saldo": 10_000, "P": 4_000, "C": 2_000, "accion": {"tipo": "call"},
                                    "info": {"tabla_ev": []}}, INICIO, AHORA)
    manos, filas = MS.decisiones_lateral(str(tmp_path / "a.jsonl"))
    assert manos == 1 and len(filas) == 1 and filas[0]["lateral"] == 0 and filas[0]["pot_final"] == 6_000


def test_subir_sobre_un_all_in_corto_con_pagador_grande_genera_bote_lateral(tmp_path):
    fila = {"accion": "x=1.0", "tipo": "raise", "monto": 8_000, "A": 8_000, "A_prima": 6_000, "descartada": None}
    escribir(tmp_path / "b.jsonl", {"etapa": "flop", "saldo": 10_000, "P": 4_000, "C": 2_000,
                                    "accion": {"tipo": "raise", "monto": 8_000}, "info": {"tabla_ev": [fila]}}, INICIO, AHORA)
    manos, filas = MS.decisiones_lateral(str(tmp_path / "b.jsonl"))
    f = filas[0]
    assert f["pot_final"] == 18_000 and f["lateral"] == 12_000          # (8 000 − 2 000) de Bender y de y: nadie más puede ganarlo
    assert f["n_disputan_lateral"] == 2 and f["n_allin"] == 1 and f["n_responden"] == 1


def test_sin_rival_all_in_o_retirandose_no_hay_registro(tmp_path):
    ahora = [jug("yo", 10_000), jug("x", 2_000, 2_000), jug("y", 8_000, 2_000)]
    escribir(tmp_path / "c.jsonl", {"etapa": "flop", "saldo": 10_000, "P": 4_000, "C": 2_000, "accion": {"tipo": "call"},
                                    "info": {"tabla_ev": []}}, INICIO, ahora)
    assert MS.decisiones_lateral(str(tmp_path / "c.jsonl"))[1] == []
    escribir(tmp_path / "d.jsonl", {"etapa": "flop", "saldo": 10_000, "P": 4_000, "C": 2_000, "accion": {"tipo": "fold"},
                                    "info": {"tabla_ev": []}}, INICIO, AHORA)
    assert MS.decisiones_lateral(str(tmp_path / "d.jsonl"))[1] == []


def test_el_informe_resume_frecuencia_y_ev_en_juego(tmp_path):
    fila = {"accion": "x=1.0", "tipo": "raise", "monto": 8_000, "A": 8_000, "A_prima": 6_000, "descartada": None}
    escribir(tmp_path / "e.jsonl", {"etapa": "flop", "saldo": 10_000, "P": 4_000, "C": 2_000,
                                    "accion": {"tipo": "raise", "monto": 8_000}, "info": {"tabla_ev": [fila]}}, INICIO, AHORA)
    manos, filas = MS.decisiones_lateral(str(tmp_path / "e.jsonl"))
    texto = MS.informe(manos, filas, 1)
    assert "1 manos de Bender" in texto and "media 120.0 bb por decisión" in texto and "67 % del bote final" in texto and "10 puntos" in texto
