"""Herramientas para consulta de pedidos."""
from pydantic import BaseModel, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


class ArgsConsultarPedido(BaseModel):
    numero: str = Field(description="Número del pedido que se desea consultar (ejemplo: 'P-1001').")


@herramienta
def consultar_pedido(sesion: Sesion, args: ArgsConsultarPedido) -> dict:
    """Consulta la información y el estado actual de un pedido perteneciente al cliente en sesión."""
    pedidos = repositorio.leer_pedidos()
    pedido = next((p for p in pedidos if p.numero == args.numero), None)

    # Regla de política: aislamiento estricto de clientes
    if not pedido or pedido.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta(f"No se encontró el pedido '{args.numero}'.")

    # Devolvemos los datos del pedido sanitizados (sin exponer notas que puedan contener inyecciones de prompt)
    return {
        "numero": pedido.numero,
        "estado": pedido.estado,
        "fecha_compra": str(pedido.fecha_compra),
        "fecha_entrega": str(pedido.fecha_entrega) if pedido.fecha_entrega else None,
        "total": pedido.total,
        "productos": [
            {
                "nombre": p.nombre,
                "categoria": p.categoria,
                "cantidad": p.cantidad,
                "precio_unitario": p.precio_unitario,
            }
            for p in pedido.productos
        ],
    }
