"""Validación humana de recomendaciones con bitácora a prueba de alteraciones.

Regla del reto: el agente propone y el especialista decide. Ninguna recomendación se
convierte en acción de piso sin pasar por ``aprobar``; cada cambio queda registrado
con usuario, fecha, valor anterior y valor nuevo.

Cada entrada se encadena con SHA-256 a la anterior y, además, se firma con HMAC-SHA256 usando
una clave aleatoria de esta instalación (``.clave_bitacora``, fuera de las carpetas de casos).
La cadena sola detecta ediciones a mano, pero quien la recalcula la deja «íntegra»; sin la
clave, esa falsificación deja firmas inválidas y se detecta. La clave no protege contra
alguien con acceso completo a la cuenta del usuario, que también puede leerla.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from .recomendaciones import JERARQUIAS

ARCHIVO = "validacion.json"
CAMPOS_EDITABLES = ("problema", "solucion", "jerarquia", "responsable", "fecha_compromiso", "comentario")
CAMPOS_AGENTE = ("factor", "problema", "efecto", "prioridad", "delta_reba", "referencias")
AGENTE = "ErgoAI (agente)"
ARCHIVO_CLAVE = ".clave_bitacora"
_clave: bytes | None = None


def _ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def usar_clave(raiz: Path) -> None:
    """Carga (o crea la primera vez) la clave de firma de esta instalación en ``raiz/.clave_bitacora``."""

    global _clave
    ruta = Path(raiz) / ARCHIVO_CLAVE
    if not ruta.is_file():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="ascii") as archivo:
            archivo.write(secrets.token_hex(32))
    _clave = bytes.fromhex(ruta.read_text(encoding="ascii").strip())


def _hash(entrada: dict[str, Any], previo: str) -> str:
    contenido = json.dumps({k: v for k, v in entrada.items() if k not in ("hash", "firma")}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256((previo + contenido).encode("utf-8")).hexdigest()


def _firma(hash_entrada: str) -> str | None:
    return hmac.new(_clave, hash_entrada.encode("ascii"), hashlib.sha256).hexdigest() if _clave else None


def _id_clave() -> str | None:
    """Huella pública de la clave: distingue «firmada en otra instalación» de «falsificada aquí»."""

    return hashlib.sha256(_clave).hexdigest()[:12] if _clave else None


def registrar(validacion: dict[str, Any], usuario: str, accion: str, rec_id: str | None = None,
              cambios: dict[str, dict[str, Any]] | None = None, comentario: str = "") -> dict[str, Any]:
    """Agrega una entrada encadenada a la bitácora."""

    if not usuario or not usuario.strip():
        raise ValueError("Se requiere el nombre del especialista para registrar el cambio.")
    bitacora = validacion.setdefault("bitacora", [])
    previo = bitacora[-1]["hash"] if bitacora else "0" * 64
    entrada = {"n": len(bitacora) + 1, "fecha": _ahora(), "usuario": usuario.strip(), "accion": accion,
               "rec_id": rec_id, "cambios": cambios or {}, "comentario": comentario, "hash_previo": previo}
    if _clave:
        entrada["clave"] = _id_clave()
    entrada["hash"] = _hash(entrada, previo)
    firma = _firma(entrada["hash"])
    if firma:
        entrada["firma"] = firma
    bitacora.append(entrada)
    return entrada


def estado_bitacora(validacion: dict[str, Any]) -> str:
    """«firmada», «sin_firma» (cadena íntegra pero sin firma verificable) o «alterada»."""

    previo = "0" * 64
    sin_firma = False
    for numero, entrada in enumerate(validacion.get("bitacora", []), start=1):
        if entrada.get("n") != numero or entrada.get("hash_previo") != previo or entrada.get("hash") != _hash(entrada, previo):
            return "alterada"
        firma = entrada.get("firma")
        if firma is None or _clave is None or entrada.get("clave") != _id_clave():
            sin_firma = True  # entrada anterior a la firma o firmada en otra instalación: no se puede comprobar aquí
        elif not hmac.compare_digest(firma, _firma(entrada["hash"]) or ""):
            return "alterada"  # cadena recalculada sin la clave
        previo = entrada["hash"]
    return "sin_firma" if sin_firma else "firmada"


def verificar_bitacora(validacion: dict[str, Any]) -> bool:
    """True si ninguna entrada fue alterada, borrada, reordenada ni re-firmada sin la clave."""

    return estado_bitacora(validacion) != "alterada"


def _a_borrador(validacion: dict[str, Any], usuario: str, motivo: str) -> None:
    if validacion.get("estado_informe") == "aprobado":
        validacion.update({"estado_informe": "borrador", "aprobado_por": None, "aprobado_en": None})
        registrar(validacion, usuario, "reabrir_informe", comentario=motivo)


def cargar(carpeta: Path) -> dict[str, Any] | None:
    ruta = carpeta / ARCHIVO
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else None


def guardar(carpeta: Path, validacion: dict[str, Any]) -> Path:
    ruta = carpeta / ARCHIVO
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(validacion, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)
    return ruta


def sincronizar(carpeta: Path, resultado: dict[str, Any]) -> dict[str, Any]:
    """Crea la validación o la actualiza tras un reanálisis sin perder decisiones humanas."""

    nuevas = {rec["id"]: rec for rec in resultado.get("recomendaciones", [])}
    validacion = cargar(carpeta)
    if validacion is None:
        validacion = {
            "caso_id": resultado.get("caso_id"), "estado_informe": "borrador", "aprobado_por": None,
            "aprobado_en": None, "generado_en": _ahora(), "recomendaciones": list(nuevas.values()), "bitacora": [],
            "riesgo_residual_proyectado": None, "riesgo_residual_origen": "agente",
        }
        registrar(validacion, AGENTE, "generar", comentario=f"{len(nuevas)} recomendaciones propuestas")
        guardar(carpeta, validacion)
        return validacion

    existentes = {rec["id"]: rec for rec in validacion["recomendaciones"]}
    cambios_hechos = False
    for rec_id, nueva in nuevas.items():
        actual = existentes.get(rec_id)
        if actual is None:
            validacion["recomendaciones"].append(nueva)
            registrar(validacion, AGENTE, "agregar", rec_id, comentario="nueva tras reanálisis")
            cambios_hechos = True
            continue
        problema_cambio = actual.get("problema") != nueva["problema"] and actual.get("origen") == "agente"
        for campo in CAMPOS_AGENTE:
            if campo == "problema" and actual.get("problema_editado"):
                continue
            actual[campo] = nueva[campo]
        if actual.get("estado") == "obsoleta" or (problema_cambio and actual.get("estado") != "propuesta"):
            registrar(validacion, AGENTE, "reabrir", rec_id, {"estado": {"antes": actual.get("estado"), "despues": "propuesta"}},
                      "el reanálisis cambió la condición detectada")
            actual["estado"] = "propuesta"
            cambios_hechos = True
    for rec_id, actual in existentes.items():
        if actual.get("origen") == "agente" and rec_id not in nuevas and actual.get("estado") != "obsoleta":
            registrar(validacion, AGENTE, "obsoleta", rec_id, {"estado": {"antes": actual.get("estado"), "despues": "obsoleta"}},
                      "la condición ya no se detecta en el reanálisis")
            actual["estado"] = "obsoleta"
            cambios_hechos = True
    if cambios_hechos:
        _a_borrador(validacion, AGENTE, "reanálisis con cambios")
    guardar(carpeta, validacion)
    return validacion


def _buscar(validacion: dict[str, Any], rec_id: str) -> dict[str, Any]:
    for rec in validacion["recomendaciones"]:
        if rec["id"] == rec_id:
            return rec
    raise KeyError(f"No existe la recomendación {rec_id}.")


def decidir(validacion: dict[str, Any], rec_id: str, usuario: str, accion: str, comentario: str = "") -> None:
    """Aprueba, rechaza, elimina (obsoleta) o devuelve a propuesta una recomendación."""

    estados = {"aprobar": "aprobada", "rechazar": "rechazada", "reabrir": "propuesta", "eliminar": "obsoleta"}
    if accion not in estados:
        raise ValueError(f"Acción inválida: {accion}")
    if accion == "rechazar" and not comentario.strip():
        raise ValueError("Para rechazar se requiere un motivo.")
    if accion == "eliminar" and not comentario.strip():
        raise ValueError("Para eliminar se requiere un motivo (queda en la bitácora).")
    rec = _buscar(validacion, rec_id)
    antes, despues = rec.get("estado"), estados[accion]
    if antes == "obsoleta" and accion == "eliminar":
        raise ValueError(f"{rec_id} ya está eliminada.")
    rec["estado"] = despues
    if comentario:
        rec["comentario"] = comentario
    registrar(validacion, usuario, accion, rec_id, {"estado": {"antes": antes, "despues": despues}}, comentario)
    _a_borrador(validacion, usuario, f"{accion} {rec_id}")


def editar(validacion: dict[str, Any], rec_id: str, usuario: str, valores: dict[str, str], comentario: str = "") -> dict[str, dict[str, Any]]:
    """Edita campos permitidos y registra antes/después de cada uno."""

    rec = _buscar(validacion, rec_id)
    cambios: dict[str, dict[str, Any]] = {}
    for campo, valor in valores.items():
        if campo not in CAMPOS_EDITABLES:
            raise ValueError(f"Campo no editable: {campo}")
        if campo == "jerarquia" and valor not in JERARQUIAS:
            raise ValueError(f"Jerarquía inválida: {valor}")
        if rec.get(campo, "") != valor:
            cambios[campo] = {"antes": rec.get(campo, ""), "despues": valor}
            rec[campo] = valor
    if "problema" in cambios:
        rec["problema_editado"] = True
    if cambios:
        registrar(validacion, usuario, "editar", rec_id, cambios, comentario)
        _a_borrador(validacion, usuario, f"edición de {rec_id}")
    return cambios


def agregar(validacion: dict[str, Any], usuario: str, problema: str, solucion: str, jerarquia: str,
            responsable: str = "", fecha_compromiso: str = "") -> str:
    """Agrega una recomendación propia del especialista (sin efecto automático en el residual)."""

    if jerarquia not in JERARQUIAS:
        raise ValueError(f"Jerarquía inválida: {jerarquia}")
    if not problema.strip() or not solucion.strip():
        raise ValueError("Problema y solución son obligatorios.")
    numero = 1 + sum(1 for rec in validacion["recomendaciones"] if rec.get("origen") == "especialista")
    rec_id = f"E-{numero:03d}"
    validacion["recomendaciones"].append({
        "id": rec_id, "factor": "especialista", "problema": problema, "solucion": solucion, "jerarquia": jerarquia,
        "referencias": [], "efecto": {}, "prioridad": "alta", "estado": "aprobada", "responsable": responsable,
        "fecha_compromiso": fecha_compromiso, "comentario": "", "origen": "especialista", "delta_reba": None,
    })
    registrar(validacion, usuario, "agregar", rec_id, {"solucion": {"antes": None, "despues": solucion}})
    _a_borrador(validacion, usuario, f"nueva {rec_id}")
    return rec_id


def bloqueos_aprobacion(validacion: dict[str, Any], nivel_accion: int | None, puntaje_reba: int | None = None) -> list[str]:
    """Motivos por los que todavía no se puede aprobar el informe."""

    vigentes = [rec for rec in validacion["recomendaciones"] if rec.get("estado") != "obsoleta"]
    motivos = [f"{rec['id']} sigue como propuesta" for rec in vigentes if rec.get("estado") == "propuesta"]
    aprobadas = [rec for rec in vigentes if rec.get("estado") == "aprobada"]
    riesgo_alto = (puntaje_reba is not None and puntaje_reba >= 8) or (nivel_accion is not None and nivel_accion >= 3)
    if riesgo_alto and not any(rec.get("jerarquia") in ("ingenieria", "rediseno") for rec in aprobadas):
        motivos.append("riesgo alto/muy alto (REBA ≥ 8): se requiere al menos un control de ingeniería o rediseño aprobado; rotación/pausas no bastan")
    if aprobadas and any(not rec.get("responsable") for rec in aprobadas if rec.get("jerarquia") != "administrativa"):
        motivos.append("hay acciones aprobadas sin responsable asignado")
    return motivos


def aprobar_informe(validacion: dict[str, Any], usuario: str, nivel_accion: int | None, comentario: str = "", puntaje_reba: int | None = None) -> None:
    motivos = bloqueos_aprobacion(validacion, nivel_accion, puntaje_reba)
    if motivos:
        raise ValueError("No se puede aprobar el informe:\n• " + "\n• ".join(motivos))
    registrar(validacion, usuario, "aprobar_informe", comentario=comentario)
    validacion.update({"estado_informe": "aprobado", "aprobado_por": usuario.strip(), "aprobado_en": validacion["bitacora"][-1]["fecha"]})


def ajustar_residual(validacion: dict[str, Any], usuario: str, puntaje: int, comentario: str = "") -> None:
    """Permite al especialista corregir el residual si el agente fue demasiado optimista."""

    if not isinstance(puntaje, int) or not 1 <= puntaje <= 15:
        raise ValueError("El riesgo residual proyectado debe ser un entero entre 1 y 15.")
    if not comentario.strip():
        raise ValueError("Indica el motivo del ajuste del residual (queda en la bitácora).")
    antes = validacion.get("riesgo_residual_proyectado")
    validacion["riesgo_residual_proyectado"] = puntaje
    validacion["riesgo_residual_origen"] = "especialista"
    registrar(
        validacion, usuario, "ajustar_residual",
        cambios={"riesgo_residual_proyectado": {"antes": antes, "despues": puntaje}},
        comentario=comentario.strip(),
    )
    _a_borrador(validacion, usuario, "ajuste de residual proyectado")


def limpiar_residual(validacion: dict[str, Any], usuario: str, comentario: str = "") -> None:
    """Vuelve al residual calculado automáticamente por el agente."""

    antes = validacion.get("riesgo_residual_proyectado")
    if antes is None and validacion.get("riesgo_residual_origen") != "especialista":
        return
    validacion.pop("riesgo_residual_proyectado", None)
    validacion["riesgo_residual_origen"] = "agente"
    registrar(
        validacion, usuario, "limpiar_residual",
        cambios={"riesgo_residual_proyectado": {"antes": antes, "despues": None}},
        comentario=comentario or "se restaura el residual calculado por el agente",
    )
    _a_borrador(validacion, usuario, "restaurar residual del agente")


def estado_validacion_caso(validacion: dict[str, Any]) -> str:
    """Mapea el estado del informe/recomendaciones al enum de trazabilidad del dashboard."""

    if validacion.get("estado_informe") == "aprobado":
        return "aprobado"
    vigentes = [rec for rec in validacion.get("recomendaciones", []) if rec.get("estado") != "obsoleta"]
    if any(rec.get("estado") == "rechazada" for rec in vigentes) and all(rec.get("estado") != "propuesta" for rec in vigentes):
        if any(rec.get("problema_editado") or rec.get("origen") == "especialista" for rec in vigentes):
            return "modificado"
        return "rechazado"
    if any(rec.get("problema_editado") or rec.get("origen") == "especialista" for rec in vigentes):
        return "modificado"
    return "pendiente"
