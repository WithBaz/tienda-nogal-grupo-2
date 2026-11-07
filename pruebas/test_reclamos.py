"""Pruebas unitarias para registrar_reclamo."""
import json

from agente import herramientas  # noqa: F401
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion
from tienda import repositorio


def test_reclamo_exitoso():
    """Un cliente puede radicar reclamo válido sobre su pedido entregado dentro del plazo."""
    # P-1002 de C-01: Audífonos (electrónica: 90 días), entregado 2026-10-20. HOY=2026-11-02 (13 días).
    payload = {"numero_pedido": "P-1002", "motivo": "El auricular izquierdo no carga."}
    resultado = ejecutar("registrar_reclamo", json.dumps(payload), Sesion(cliente_id="C-01"))

    assert "error" not in resultado
    assert resultado["estado"] == "abierto"
    assert "reclamo_id" in resultado

    # Verificar que quedó guardado en reclamos.json
    reclamos = repositorio.leer_reclamos()
    assert any(r.id == resultado["reclamo_id"] and r.numero_pedido == "P-1002" for r in reclamos)


def test_reclamo_sin_motivo_falla():
    """No se permite radicar reclamo sin motivo."""
    payload = {"numero_pedido": "P-1002", "motivo": "   "}
    resultado = ejecutar("registrar_reclamo", json.dumps(payload), Sesion(cliente_id="C-01"))
    assert "error" in resultado
    assert "obligatorio registrar el motivo" in resultado["error"]


def test_reclamo_pedido_no_entregado_falla():
    """No se permite radicar reclamo sobre pedido que no figura como entregado."""
    # P-1001 está en estado 'pagado'
    payload = {"numero_pedido": "P-1001", "motivo": "Quiero cambiarlo."}
    resultado = ejecutar("registrar_reclamo", json.dumps(payload), Sesion(cliente_id="C-01"))
    assert "error" in resultado
    assert "Solo se puede presentar un reclamo cuando el pedido figura como entregado" in resultado["error"]


def test_reclamo_duplicado_bloqueado():
    """No se permite radicar más de un reclamo abierto por pedido."""
    # P-1007 (de C-03) ya tiene el reclamo R-001 abierto
    payload = {"numero_pedido": "P-1007", "motivo": "Sigue roto el televisor."}
    resultado = ejecutar("registrar_reclamo", json.dumps(payload), Sesion(cliente_id="C-03"))
    assert "error" in resultado
    assert "ya tiene un reclamo abierto" in resultado["error"]


def test_reclamo_fuera_de_plazo_perecederos():
    """Se rechaza reclamo si ha vencido el plazo legal según el tipo de producto."""
    # P-1003 (C-01): Perecedero (3 días). Entregado 2026-10-25. HOY=2026-11-02 (8 días).
    payload = {"numero_pedido": "P-1003", "motivo": "Las frutas llegaron estropeadas."}
    resultado = ejecutar("registrar_reclamo", json.dumps(payload), Sesion(cliente_id="C-01"))
    assert "error" in resultado
    assert "plazo para reclamar ha vencido" in resultado["error"]


def test_reclamo_pedido_ajeno():
    """No se puede reclamar sobre un pedido ajeno."""
    # P-1004 es de C-02
    payload = {"numero_pedido": "P-1004", "motivo": "No me gustó."}
    resultado = ejecutar("registrar_reclamo", json.dumps(payload), Sesion(cliente_id="C-01"))
    assert "error" in resultado
