import json
from pathlib import Path

import pytest
from PIL import Image

from ergoai import validacion as val
from ergoai.cli import ejecutar_evaluar, ejecutar_validacion
from ergoai.reba import calcular_reba
from ergoai.recomendaciones import generar_recomendaciones
from ergoai.residual import calcular_residual
from ergoai.modelos import PoseResult
from test_pipeline import _landmarks_sinteticos

MEDICIONES = {
    "tronco_flexion": 45.0, "cuello_flexion": 25.0, "tronco_torsion": 25.0, "tronco_inclinacion_lateral": 0.0,
    "cuello_inclinacion_rotacion": 0.0, "apoyo_piernas_unilateral": 0.0,
    **{f"{medida}_{lado}": valor for lado in ("L", "R") for medida, valor in (
        ("rodilla_flexion", 40.0), ("brazo_flexion", 60.0), ("codo_flexion", 50.0),
        ("muneca_flexion_extension", 20.0), ("brazo_abduccion", 0.0))},
}
CONTEXTO = {
    "postura": "de_pie", "tipo_tarea": "levantamiento", "carga_kg": 18, "agarre": "malo",
    "actividad": {"estatica_mas_1min": True, "repetitiva_mas_4_por_min": False, "cambios_bruscos_o_base_inestable": False},
    "hombro_elevado": {"izquierdo": False, "derecho": False}, "brazo_apoyado": {"izquierdo": False, "derecho": False},
    "muneca_desviada_o_torcida": {"izquierdo": False, "derecho": False},
}


def _recs(configuracion):
    reba = calcular_reba(MEDICIONES, CONTEXTO, configuracion.reba).a_diccionario()
    return reba, [rec.a_diccionario() for rec in generar_recomendaciones(MEDICIONES, CONTEXTO, reba, configuracion.reba)]


def test_recomendaciones_priorizan_ingenieria_y_citan_norma(configuracion) -> None:
    reba, recs = _recs(configuracion)
    assert reba["nivel_accion"] >= 3
    ids = [rec["id"] for rec in recs]
    for esperado in ("R-CARGA-ING", "R-TRONCO-ING", "R-MUNECA-ING", "R-TORSION-RED", "R-AGARRE-RED", "R-CARGA-ADM"):
        assert esperado in ids
    jerarquias = [rec["jerarquia"] for rec in recs]
    assert jerarquias == sorted(jerarquias, key=("ingenieria", "rediseno", "administrativa").index)
    assert all(rec["estado"] == "propuesta" and rec["prioridad"] == "urgente" for rec in recs)
    carga = next(rec for rec in recs if rec["id"] == "R-CARGA-ING")
    assert any("14 kg" in ref for ref in carga["referencias"])
    assert all(rec["referencias"] for rec in recs)


def test_residual_recalcula_reba_y_excluye_administrativas_y_rechazadas(configuracion) -> None:
    _, recs = _recs(configuracion)
    residual = calcular_residual(MEDICIONES, CONTEXTO, recs, configuracion.reba)
    assert residual["residual"]["reba"] < residual["inicial"]["reba"]
    assert residual["reduccion_puntos"] > 0
    assert "R-CARGA-ADM" not in residual["recomendaciones_aplicadas"]
    for rec in recs:
        rec["estado"] = "rechazada"
    sin_cambios = calcular_residual(MEDICIONES, CONTEXTO, recs, configuracion.reba)
    assert sin_cambios["residual"]["reba"] == sin_cambios["inicial"]["reba"]
    assert sin_cambios["recomendaciones_aplicadas"] == []


def test_bitacora_detecta_alteraciones(tmp_path: Path, configuracion) -> None:
    _, recs = _recs(configuracion)
    validacion = val.sincronizar(tmp_path, {"caso_id": "x", "recomendaciones": recs})
    val.decidir(validacion, "R-TRONCO-ING", "Ing. Pérez", "aprobar")
    val.editar(validacion, "R-TRONCO-ING", "Ing. Pérez", {"responsable": "IE celda 3", "fecha_compromiso": "2026-12-01"})
    assert val.verificar_bitacora(validacion)
    ultima = validacion["bitacora"][-1]
    assert ultima["cambios"]["responsable"] == {"antes": "", "despues": "IE celda 3"}
    ultima["usuario"] = "otra persona"
    assert not val.verificar_bitacora(validacion)


def test_aprobacion_exige_decisiones_control_de_ingenieria_y_responsable(tmp_path: Path, configuracion) -> None:
    reba, recs = _recs(configuracion)
    validacion = val.sincronizar(tmp_path, {"caso_id": "x", "recomendaciones": recs})
    with pytest.raises(ValueError, match="propuesta"):
        val.aprobar_informe(validacion, "Ing. Pérez", reba["nivel_accion"])
    with pytest.raises(ValueError, match="motivo"):
        val.decidir(validacion, "R-CARGA-ING", "Ing. Pérez", "rechazar")
    for rec in validacion["recomendaciones"]:
        accion = "aprobar" if rec["jerarquia"] == "administrativa" else "rechazar"
        val.decidir(validacion, rec["id"], "Ing. Pérez", accion, "solo administrativas")
    with pytest.raises(ValueError, match="ingeniería o rediseño"):
        val.aprobar_informe(validacion, "Ing. Pérez", reba["nivel_accion"])
    val.decidir(validacion, "R-TRONCO-ING", "Ing. Pérez", "aprobar")
    with pytest.raises(ValueError, match="responsable"):
        val.aprobar_informe(validacion, "Ing. Pérez", reba["nivel_accion"])
    val.editar(validacion, "R-TRONCO-ING", "Ing. Pérez", {"responsable": "IE"})
    val.aprobar_informe(validacion, "Ing. Pérez", reba["nivel_accion"])
    assert validacion["estado_informe"] == "aprobado"
    val.editar(validacion, "R-TRONCO-ING", "Ing. López", {"solucion": "Mesa elevadora neumática"})
    assert validacion["estado_informe"] == "borrador"
    assert validacion["bitacora"][-1]["accion"] == "reabrir_informe"
    with pytest.raises(ValueError, match="especialista"):
        val.decidir(validacion, "R-TRONCO-ING", "  ", "aprobar")


def _caso(tmp_path: Path) -> tuple[Path, Path]:
    raiz = tmp_path / "proyecto"
    (raiz / "config").mkdir(parents=True)
    (raiz / "config" / "umbrales.yaml").write_text((Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    caso = tmp_path / "caso"
    caso.mkdir()
    for vista in ("frente", "costado", "aerea"):
        Image.new("RGB", (300, 400)).save(caso / f"{vista}.png")
    contexto = {**CONTEXTO, "caso_id": "e2e", "orientacion_costado": "derecha", "overrides": MEDICIONES}
    (caso / "contexto.json").write_text(json.dumps(contexto), encoding="utf-8")
    return raiz, caso


class _Backend:
    def detect(self, image):
        return [PoseResult(_landmarks_sinteticos(), [])]


def test_pipeline_genera_informe_y_flujo_de_validacion(tmp_path: Path) -> None:
    raiz, caso = _caso(tmp_path)
    salida = ejecutar_evaluar(caso, raiz, _Backend())
    carpeta = salida.parent
    resultado = json.loads(salida.read_text(encoding="utf-8"))
    assert resultado["recomendaciones"] and resultado["riesgo_residual"]["reduccion_puntos"] > 0
    assert resultado["tiempos_s"]["analisis_total"] >= 0
    informe = (carpeta / "informe.html").read_text(encoding="utf-8")
    assert "BORRADOR" in informe and "R-TRONCO-ING" in informe and "NOM-036-1-STPS-2018" in informe
    assert (carpeta / "acciones_00014.csv").is_file()

    for rec in resultado["recomendaciones"]:
        if rec["jerarquia"] != "administrativa":
            ejecutar_validacion(carpeta, raiz, "Ing. Pérez", "editar", rec["id"], {"responsable": "IE celda 3"})
        ejecutar_validacion(carpeta, raiz, "Ing. Pérez", "aprobar", rec["id"])
    ejecutar_validacion(carpeta, raiz, "Ing. Pérez", "aprobar_informe")
    assert "APROBADO por Ing. Pérez" in (carpeta / "informe.html").read_text(encoding="utf-8")

    ejecutar_evaluar(caso, raiz, _Backend())  # reanálisis idéntico: conserva decisiones y aprobación
    validacion = val.cargar(carpeta)
    assert validacion["estado_informe"] == "aprobado"
    assert all(rec["estado"] == "aprobada" for rec in validacion["recomendaciones"])
    assert val.verificar_bitacora(validacion)
