"""final_eval.py: configuraciones válidas contra params.py y tasa de falsos positivos de la huella leída de los logs."""

import json

import final_eval as FE
from params import _mezclar, cargar_params


def test_todas_las_configuraciones_son_claves_validas_de_params_py():
    for cid, cfg in FE.configuraciones().items():
        p = cargar_params()
        _mezclar(p, json.loads(json.dumps(cfg["variante"])))              # una clave mal escrita lanzaría KeyError
        assert cfg["id"] == cid


def test_la_huella_corregida_cambia_umbral_minimo_y_evidencia_sin_pisar_la_tabla_p3():
    p = cargar_params()
    _mezclar(p, FE.configuraciones()["huella"]["variante"])
    h = p["huella"]
    assert h["umbral"] == 0.97 and h["min_z"] == 8 and h["apertura_3bb"]["activa"] is True
    assert h["apertura_3bb"]["p3"]["base"] == 0.996 and set(h["tabla"]) == set(h["apertura_3bb"]["p3"])
    base = cargar_params()["huella"]
    assert base["umbral"] == 0.9 and base["min_z"] == 0 and base["apertura_3bb"]["activa"] is False        # la base no cambia
    q = cargar_params()
    _mezclar(q, FE.configuraciones()["sin_contra"]["variante"])
    assert q["explotacion"]["contra_bots"] is False and cargar_params()["explotacion"]["contra_bots"] is True


def test_c05_con_correccion_conserva_los_parametros_de_c05_y_agrega_la_correccion():
    p = cargar_params()
    _mezclar(p, FE.configuraciones()["c05_huella"]["variante"])
    assert p["riesgo"]["K"] == 6251 and p["huella"]["min_z"] == 8 and p["apertura"]["tamano_bb"] == 2.278


class Falso:
    def __init__(self, base):
        self.base = base

    def dir_cfg(self, cfg, bloque):
        return str(self.base)


def decision(id_mano, rivales):
    return {"tipo": "decision", "id_mano": id_mano, "info": {"rivales": rivales}}


def test_el_reconocimiento_cuenta_pares_mano_rival_y_los_falsos_positivos(tmp_path):
    d = tmp_path / "t1"
    d.mkdir()
    (d / "torneo.json").write_text(json.dumps({"participantes": [{"id": "r1", "tipo": "bender_v1"}, {"id": "r2", "tipo": "allin_siempre"},
                                                                 {"id": "r3", "tipo": "aleatorio"}]}))
    filas = [decision("m1", {"r1": {"bot": None}, "r2": {"bot": None}, "r3": {"bot": ["aleatorio", 0.99]}}),
             decision("m1", {"r1": {"bot": ["espia", 0.95]}, "r2": {"bot": None}, "r3": {"bot": ["aleatorio", 0.99]}}),   # r1 se reconoce en la 2.ª decisión
             decision("m2", {"r1": {"bot": None}, "r2": {"bot": None}, "r3": {"bot": None}})]
    (d / "bender.jsonl").write_text("\n".join(json.dumps(f, separators=(",", ":")) for f in filas) + "\n")
    rec = FE.reconocimiento(Falso(tmp_path), {}, "n", [1])
    assert rec["bender_v1"] == {"pares": 2, "reconocidos": {"espia": 1}}                 # 1 de 2 manos
    assert rec["allin_siempre"] == {"pares": 2, "reconocidos": {}}
    assert rec["aleatorio"] == {"pares": 2, "reconocidos": {"aleatorio": 1}}
    assert FE.fp_total(rec) == 100.0 * 1 / 4                                              # solo cuentan los que NO son del kit
