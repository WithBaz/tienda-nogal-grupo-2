"""Pruebas unitarias para solicitar_reembolso y escalar_caso."""
import json

from agente import herramientas  # noqa: F401
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion
from tienda import repositorio


def test_reembolso_sin_reclamo_ni_cancelacion_falla():
    """No procede reembolso si el pedido no está cancelado ni tiene reclamo abierto."""
    # P-1002 (C-01): entregado, sin reclamos
    resultado = ejecutar(
        "solicitar_reembolso",
        json.dumps({"numero_pedido": "P-1002", "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-01"),
    )
    assert "error" in resultado
    assert "cancelado o cuente con un reclamo abierto" in resultado["error"]


def test_reembolso_por_reclamo_abierto_exitoso():
    """Procede reembolso si el pedido tiene un reclamo abierto y se confirma."""
    # P-1007 (C-03): tiene el reclamo abierto R-001. Total: 1850000.
    # Pedimos reembolso parcial menor al tope: 200000
    resultado = ejecutar(
        "solicitar_reembolso",
        json.dumps({"numero_pedido": "P-1007", "monto": 200000, "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-03"),
    )
    assert "error" not in resultado
    assert resultado["estado"] == "aprobado"
    assert resultado["monto"] == 200000


def test_reembolso_sobre_tope_queda_solicitado_y_escala():
    """Un reembolso superior a $300.000 se registra como solicitado y se escala."""
    # P-1007 (C-03): reclamo abierto, solicitamos 500000 (> 300000)
    resultado = ejecutar(
        "solicitar_reembolso",
        json.dumps({"numero_pedido": "P-1007", "monto": 500000, "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-03"),
    )
    assert "error" not in resultado
    assert resultado["estado"] == "solicitado"
    assert resultado["escalado"] is True

    # Verificar registro en escalamientos
    escalamientos = repositorio.leer_escalamientos()
    assert any(e.numero_pedido == "P-1007" and "300.000" in e.motivo for e in escalamientos)


def test_escalar_caso_exitoso():
    """La herramienta de escalamiento registra el caso correctamente."""
    resultado = ejecutar(
        "escalar_caso",
        json.dumps({
            "motivo": "Cliente solicita hablar con supervisor",
            "resumen": "El cliente insiste en cambiar la dirección de entrega de su pedido.",
            "numero_pedido": "P-1001",
        }),
        Sesion(cliente_id="C-01"),
    )
    assert "error" not in resultado
    assert "escalamiento_id" in resultado
    assert "un día hábil" in resultado["mensaje"]

    escalamientos = repositorio.leer_escalamientos()
    assert any(e.id == resultado["escalamiento_id"] for e in escalamientos)
