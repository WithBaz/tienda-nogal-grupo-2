"""Pruebas para la herramienta consultar_pedido."""
import json

from agente import herramientas  # noqa: F401
from agente.herramientas.registro import ejecutar
from agente.sesion import Sesion


def test_consultar_pedido_propio():
    """Un cliente puede consultar exitosamente sus propios pedidos."""
    resultado = ejecutar("consultar_pedido", json.dumps({"numero": "P-1001"}), Sesion(cliente_id="C-01"))
    assert "error" not in resultado
    assert resultado["numero"] == "P-1001"
    assert resultado["estado"] == "pagado"
    assert resultado["total"] == 180000
    assert len(resultado["productos"]) == 1


def test_consultar_pedido_inexistente():
    """Si el pedido no existe, devuelve error informativo sin excepciones."""
    resultado = ejecutar("consultar_pedido", json.dumps({"numero": "P-9999"}), Sesion(cliente_id="C-01"))
    assert "error" in resultado
    assert "No se encontró" in resultado["error"]


def test_no_ver_pedido_ajeno():
    """Un cliente no puede acceder a pedidos pertenecientes a otros clientes."""
    # P-1004 pertenece al cliente C-02
    resultado = ejecutar("consultar_pedido", json.dumps({"numero": "P-1004"}), Sesion(cliente_id="C-01"))
    assert "error" in resultado
    assert "No se encontró" in resultado["error"]


def test_nota_inyeccion_no_expuesta():
    """La nota del cliente (potencial vector de prompt injection) no se expone al modelo."""
    # P-1011 pertenece a C-04 y contiene una nota maliciosa
    resultado = ejecutar("consultar_pedido", json.dumps({"numero": "P-1011"}), Sesion(cliente_id="C-04"))
    assert "error" not in resultado
    assert "nota_cliente" not in resultado
