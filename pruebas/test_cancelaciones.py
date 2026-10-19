"""Pruebas unitarias para cancelar_pedido."""
import json

from agente import herramientas  # noqa: F401
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion
from tienda import repositorio


def test_cancelar_pedido_sin_confirmacion_pide_confirmar():
    """Si no se ha confirmado, la herramienta advierte y no altera los datos."""
    # P-1001 (C-01): estado pagado
    resultado = ejecutar(
        "cancelar_pedido",
        json.dumps({"numero_pedido": "P-1001", "confirmado_por_cliente": False}),
        Sesion(cliente_id="C-01"),
    )
    assert resultado.get("requiere_confirmacion") is True
    # El pedido sigue pagado
    pedido = next(p for p in repositorio.leer_pedidos() if p.numero == "P-1001")
    assert pedido.estado == "pagado"


def test_cancelar_pedido_con_confirmacion_exitoso():
    """Con confirmación explícita, se cancela y se aprueba reembolso automático."""
    # P-1001 (C-01): pagado, total 180000 (<= 300000)
    resultado = ejecutar(
        "cancelar_pedido",
        json.dumps({"numero_pedido": "P-1001", "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-01"),
    )
    assert "error" not in resultado
    assert resultado["estado"] == "cancelado"
    assert resultado["estado_reembolso"] == "aprobado"
    assert resultado["monto"] == 180000

    # Verificar pedido cancelado en repositorio
    pedido = next(p for p in repositorio.leer_pedidos() if p.numero == "P-1001")
    assert pedido.estado == "cancelado"

    # Verificar reembolso automático creado en reembolsos.json
    reembolsos = repositorio.leer_reembolsos()
    assert any(r.numero_pedido == "P-1001" and r.estado == "aprobado" for r in reembolsos)


def test_cancelar_pedido_enviado_falla():
    """Un pedido enviado no se puede cancelar por política."""
    # P-1015 (C-01): estado enviado
    resultado = ejecutar(
        "cancelar_pedido",
        json.dumps({"numero_pedido": "P-1015", "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-01"),
    )
    assert "error" in resultado
    assert "ya fue enviado y no se puede cancelar" in resultado["error"]


def test_cancelar_pedido_en_preparacion_vencido_falla():
    """En preparación con más de 24 horas no se puede cancelar."""
    # P-1009 (C-03): en_preparacion, compra 2026-10-30. HOY=2026-11-02 (3 días de antigüedad)
    resultado = ejecutar(
        "cancelar_pedido",
        json.dumps({"numero_pedido": "P-1009", "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-03"),
    )
    assert "error" in resultado
    assert "más de 24 horas" in resultado["error"]


def test_cancelar_pedido_alto_valor_escala_reembolso():
    """Si el pedido cancelado supera $300.000, el reembolso queda en 'solicitado' y escala."""
    # P-1005 (C-02): en_preparacion, compra 2026-11-02 (hoy, <= 24h), total 420000 (> 300000)
    resultado = ejecutar(
        "cancelar_pedido",
        json.dumps({"numero_pedido": "P-1005", "confirmado_por_cliente": True}),
        Sesion(cliente_id="C-02"),
    )
    assert "error" not in resultado
    assert resultado["estado"] == "cancelado"
    assert resultado["estado_reembolso"] == "solicitado"
    assert resultado["escalado"] is True

    # Verificar escalamiento generado
    escalamientos = repositorio.leer_escalamientos()
    assert any(e.numero_pedido == "P-1005" for e in escalamientos)
