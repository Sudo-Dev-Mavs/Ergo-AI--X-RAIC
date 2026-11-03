from ergoai.config import cargar_configuracion
from ergoai.recomendaciones import generar_recomendaciones, hay_ingenieria_en_riesgo_alto
from ergoai.reba import calcular_reba
from ergoai.residual import recalcular_residual
from ergoai.bitacora import actualizar_estado_recomendacion, leer
from ergoai.informe import construir_markdown
from pathlib import Path


def _mediciones_alto() -> dict[str, float | None]:
    return {
        "tronco_flexion": 45.0,
        "cuello_flexion": 30.0,
        "tronco_torsion": 0.0,
        "tronco_inclinacion_lateral": 0.0,
        "cuello_inclinacion_rotacion": 0.0,
        "apoyo_piernas_unilateral": 0.0,
        "rodilla_flexion_L": 10.0,
        "rodilla_flexion_R": 10.0,
        "brazo_flexion_L": 70.0,
        "brazo_flexion_R": 70.0,
        "codo_flexion_L": 50.0,
        "codo_flexion_R": 50.0,
        "muneca_flexion_extension_L": 20.0,
        "muneca_flexion_extension_R": 20.0,
        "brazo_abduccion_L": 0.0,
        "brazo_abduccion_R": 0.0,
    }


def _contexto() -> dict:
    return {
        "postura": "de_pie",
        "carga_kg": 12,
        "agarre": "malo",
        "actividad": {"estatica_mas_1min": True, "repetitiva_mas_4_por_min": False, "cambios_bruscos_o_base_inestable": False},
        "hombro_elevado": {"izquierdo": False, "derecho": False},
        "brazo_apoyado": {"izquierdo": False, "derecho": False},
        "muneca_desviada_o_torcida": {"izquierdo": False, "derecho": False},
    }


def test_recomendaciones_priorizan_ingenieria_en_riesgo_alto(tmp_path: Path):
    config = cargar_configuracion(Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml")
    mediciones = _mediciones_alto()
    contexto = _contexto()
    reba = calcular_reba(mediciones, contexto, config.reba)
    assert reba.nivel_riesgo in {"Alto", "Muy alto", "Medio"}
    recs = generar_recomendaciones(reba.a_diccionario(), mediciones, contexto)
    assert recs
    assert hay_ingenieria_en_riesgo_alto(recs, reba.nivel_riesgo)
    assert any(item.tipo_control == "ingenieria" for item in recs)
    # Si hay administrativo, no puede ser la única en alto
    if reba.nivel_riesgo in {"Alto", "Muy alto"}:
        assert any(item.tipo_control in {"ingenieria", "eliminacion"} for item in recs)


def test_residual_recalcula_con_mismo_motor():
    config = cargar_configuracion(Path(__file__).resolve().parents[1] / "config" / "umbrales.yaml")
    mediciones = _mediciones_alto()
    contexto = _contexto()
    reba = calcular_reba(mediciones, contexto, config.reba)
    recs = generar_recomendaciones(reba.a_diccionario(), mediciones, contexto)
    residual = recalcular_residual(mediciones, contexto, config.reba, recs, inicial=reba)
    assert residual["puntaje_inicial"] == (reba.final or {}).get("reportado")
    assert residual["supuestos"]
    assert "cambios_aplicados" in residual


def test_bitacora_append_only(tmp_path: Path):
    recs = [
        {
            "id": "REC-01",
            "identificador": "A",
            "segmento": "tronco",
            "problema": "x",
            "solucion": "y",
            "tipo_control": "ingenieria",
            "prioridad": 1,
            "fuente": "NOM",
            "estado": "propuesta",
            "historial": [],
            "cambio_esperado": {},
            "responsable": "IE",
            "riesgo_origen": "Alto",
        }
    ]
    actualizadas = actualizar_estado_recomendacion(
        recs, "REC-01", "aprobada", usuario="ana", motivo="ok en piso", carpeta_salida=tmp_path
    )
    assert actualizadas[0]["estado"] == "aprobada"
    eventos = leer(tmp_path)
    assert len(eventos) == 1
    assert eventos[0]["usuario"] == "ana"
    assert eventos[0]["valor_anterior"] == "propuesta"
    assert eventos[0]["valor_nuevo"] == "aprobada"


def test_informe_incluye_residual_y_validacion():
    texto = construir_markdown(
        {
            "caso_id": "demo",
            "reba": {"final": {"reportado": 8, "lado": "R"}, "nivel_riesgo": "Alto", "nivel_accion": 3, "grupo_a": {}, "grupo_b": {}},
            "angulos": [{"medida": "tronco_flexion", "lado": None, "valor_deg": 40, "banda_reba": 3, "vista": "costado", "confianza": 0.9, "banderas": []}],
            "recomendaciones": [
                {
                    "id": "REC-01",
                    "identificador": "A",
                    "segmento": "tronco",
                    "tipo_control": "ingenieria",
                    "estado": "propuesta",
                    "problema": "tronco alto",
                    "solucion": "ajustar altura",
                    "fuente": "NOM-036-1",
                }
            ],
            "riesgo_residual": {
                "puntaje_inicial": 8,
                "nivel_inicial": "Alto",
                "puntaje_residual": 5,
                "nivel_residual": "Medio",
                "delta": -3,
                "supuestos": ["tronco_flexion → 10.0"],
            },
            "pendientes_manuales": [],
        },
        tiempo_evaluacion_s=3.2,
        tiempo_redaccion_s=0.01,
    )
    assert "Riesgo residual" in texto
    assert "aprobada" in texto
    assert "NOM-036" in texto or "NOM-036-1" in texto
