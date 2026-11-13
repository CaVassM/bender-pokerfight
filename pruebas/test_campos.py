"""Campo «desconocido» del paso 2 de la Capa 3: 28 participantes con copias de Bender de otro estilo y bots de estrés."""

import json
import os

import campeonato as CAMP
import bandido_eval as BE


def armar(tmp_path, campo=BE.CAMPO_DESC):
    ruta = tmp_path / "params.json"
    ruta.write_text("{}")
    return CAMP.armar(123, CAMP.campo_de(campo), str(ruta), str(tmp_path))


def test_el_campo_desconocido_tiene_28_participantes_con_la_composicion_pedida(tmp_path):
    partes = armar(tmp_path)
    cuenta = {}
    for p in partes:
        cuenta[p["tipo"]] = cuenta.get(p["tipo"], 0) + 1
    assert len(partes) == 28
    assert cuenta == {"bender_agresivo": 7, "bender_prudente": 7, "bender_v1": 4, "allin_siempre": 2, "iguala_siempre": 2,
                      "sube_min_siempre": 2, "aleatorio": 3, "bender": 1}
    assert len({p["id"] for p in partes}) == 28                                  # alias distintos
    assert not any(t in cuenta for t in ("darwin", "novato"))


def test_las_copias_agresiva_y_prudente_llevan_sus_parametros_y_su_propia_memoria(tmp_path):
    armar(tmp_path)
    agr = prud = v1 = 0
    for nombre in os.listdir(tmp_path):
        if not (nombre.startswith("params-j-") and nombre.endswith(".json")):
            continue
        p = json.load(open(tmp_path / nombre))
        assert p["registro"] == {"mensajes": False} and p["rivales"]["dir"].endswith(nombre[len("params-"):-len(".json")].join(["rivales-", ""]))
        if "riesgo" in p and p["riesgo"].get("K") == 40_000:
            agr += 1
            assert p["decision"] == {"allin_profundo_solo_valor": False, "solo_valor_sobre_apuesta": False}
            assert abs(p["apertura"]["top_pos"]["BTN"] - 49.795) < 0.011 and p["apertura"]["top_pos"]["BTN_SB_HU"] == 80.5   # 43,3 × 1,15 y 70 × 1,15
        elif "riesgo" in p and p["riesgo"].get("K") == 4_000:
            prud += 1
            assert abs(p["apertura"]["top_pos"]["BTN"] - 36.805) < 0.011 and "decision" not in p                                 # 43,3 × 0,85 = 36,805
        else:
            v1 += 1
            assert p["riesgo"] == {"utilidad": False} and p["apertura"] == {"limpers_menu": False}
    assert (agr, prud, v1) == (7, 7, 4)


def test_los_parametros_de_las_copias_son_claves_validas_de_params_py():
    from params import _mezclar, cargar_params
    for propios in CAMP.COPIAS_BENDER.values():
        _mezclar(cargar_params(), json.loads(json.dumps(propios)))          # una clave mal escrita lanzaría KeyError
    base = cargar_params()["apertura"]["top_pos"]
    assert base == CAMP.TOP_POS_BASE                                         # la tabla duplicada coincide con params.py


def test_el_campo_de_entrenamiento_no_cambia(tmp_path):
    partes = armar(tmp_path, BE.CAMPO_ENT)
    assert len(partes) == 28 and sum(p["tipo"] == "bender_v1" for p in partes) == 3
