from ergoai.gui import _primera_imagen, _ruta_soltada
from ergoai.presentacion import (
    aviso_vistas_faltantes,
    clave_desde_etiqueta,
    color_riesgo,
    ETIQUETAS_AGARRE,
    filas_angulos,
    formatear_angulo,
    formatear_confianza,
    texto_tiempo,
)


def test_aviso_si_falta_una_vista():
    aviso = aviso_vistas_faltantes(["frente", "costado"])
    assert aviso is not None
    assert "Aérea" in aviso
    assert "no se inventa" in aviso


def test_aviso_desaparece_con_tres_vistas():
    assert aviso_vistas_faltantes(["frente", "costado", "aerea"]) is None


def test_color_riesgo_alto_usa_rojo_jabil():
    paleta = color_riesgo("Alto")
    assert paleta["barra"] == "#C62828"


def test_color_riesgo_ausente_es_pendiente():
    assert color_riesgo(None) == color_riesgo("Pendiente")


def test_etiqueta_agarre_vuelve_al_valor_del_motor():
    assert clave_desde_etiqueta(ETIQUETAS_AGARRE, "Bueno") == "bueno"


def test_filas_angulos_exponen_rango_y_confianza():
    filas = filas_angulos(
        [
            {
                "medida": "tronco_flexion",
                "lado": None,
                "valor_deg": 32.4,
                "banda_reba": 3,
                "vista": "costado",
                "confianza": 0.81,
                "banderas": [],
            }
        ]
    )
    assert filas[0][0] == "Tronco"
    assert filas[0][2] == "32.4°"
    assert filas[0][3] == "3"
    assert filas[0][4] == "Costado"
    assert filas[0][5] == "81%"


def test_angulo_ausente_no_se_inventa():
    assert formatear_angulo(None) == "—"
    assert "revisar" in formatear_confianza(0.4, ["baja_visibilidad"])


def test_tiempo_de_evaluacion_es_legible():
    assert texto_tiempo(8.21) == "8.2 s"
    assert texto_tiempo(14.7) == "15 s"


def test_ruta_soltada_limpia_comillas_de_windows(tmp_path):
    imagen = tmp_path / "frente.jpg"
    imagen.write_bytes(b"fake")
    assert _ruta_soltada(f'"{imagen}"') == imagen
    assert _ruta_soltada(str(imagen).encode("utf-8")) == imagen
    assert _primera_imagen([str(tmp_path / "notas.txt"), str(imagen)]) == imagen
