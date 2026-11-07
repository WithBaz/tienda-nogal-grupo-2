"""Herramientas para cancelación de pedidos."""
from pydantic import BaseModel, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


class ArgsCancelarPedido(BaseModel):
    numero_pedido: str = Field(description="Número del pedido que el cliente desea cancelar (ejemplo: 'P-1001').")
    confirmado_por_cliente: bool = Field(
        default=False,
        description="Debe ser True ÚNICAMENTE si el cliente ya confirmó explícitamente en el chat que desea cancelar este pedido específico después de que se le preguntara.",
    )


@herramienta
def cancelar_pedido(sesion: Sesion, args: ArgsCancelarPedido) -> dict:
    """Cancela un pedido y genera su reembolso si cumple las políticas y el cliente lo ha confirmado."""
    pedidos = repositorio.leer_pedidos()
    pedido = next((p for p in pedidos if p.numero == args.numero_pedido), None)

    # 1. Pertenencia
    if not pedido or pedido.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta(f"No se encontró el pedido '{args.numero_pedido}'.")

    # 2. Validación de estado
    if pedido.estado == "cancelado":
        raise ErrorDeHerramienta(f"El pedido '{args.numero_pedido}' ya se encuentra cancelado.")

    if pedido.estado == "entregado":
        raise ErrorDeHerramienta(
            f"El pedido '{args.numero_pedido}' ya fue entregado; no aplica la cancelación. "
            "Si tienes algún problema con tus productos, puedes presentar un reclamo."
        )

    if pedido.estado == "enviado":
        raise ErrorDeHerramienta(
            f"El pedido '{args.numero_pedido}' ya fue enviado y no se puede cancelar. "
            "Puedes rechazar la entrega en la puerta o presentar un reclamo tras recibirlo."
        )

    if pedido.estado == "en_preparacion":
        dias_compra = (repositorio.HOY - pedido.fecha_compra).days
        if dias_compra > 1:
            raise ErrorDeHerramienta(
                f"El pedido '{args.numero_pedido}' está en preparación y han transcurrido más de 24 horas "
                "desde la compra, por lo que la política ya no permite cancelarlo."
            )

    # 3. Validación de confirmación explícita obligatoria
    if not args.confirmado_por_cliente:
        return {
            "requiere_confirmacion": True,
            "numero_pedido": pedido.numero,
            "total": pedido.total,
            "mensaje": (
                f"El pedido {pedido.numero} (total: ${pedido.total:,}) puede ser cancelado. "
                "Antes de proceder, es OBLIGATORIO que le pidas al cliente confirmación explícita advirtiéndole "
                "que la acción cancelará definitivamente el pedido. Cuando el cliente responda afirmativamente, "
                "vuelve a llamar a cancelar_pedido con confirmado_por_cliente=True."
            ),
        }

    # 4. Aplicar cancelación
    pedido.estado = "cancelado"
    repositorio.guardar_pedidos(pedidos)

    # 5. Generar reembolso automático ("Toda cancelación aprobada genera automáticamente el reembolso...")
    reembolsos = repositorio.leer_reembolsos()
    ids_reembolsos = {r.id for r in reembolsos}
    idx_r = len(reembolsos) + 1
    while f"M-{idx_r:03d}" in ids_reembolsos:
        idx_r += 1
    reembolso_id = f"M-{idx_r:03d}"

    monto = pedido.total
    escalado = False
    if monto <= 300000:
        estado_reembolso = "aprobado"
    else:
        # Supera el tope de $300.000 -> estado solicitado y escalar
        estado_reembolso = "solicitado"
        escalado = True

        escalamientos = repositorio.leer_escalamientos()
        ids_esc = {e.id for e in escalamientos}
        idx_e = len(escalamientos) + 1
        while f"E-{idx_e:03d}" in ids_esc:
            idx_e += 1
        esc_id = f"E-{idx_e:03d}"

        nuevo_esc = repositorio.Escalamiento(
            id=esc_id,
            cliente_id=sesion.cliente_id,
            numero_pedido=pedido.numero,
            fecha=repositorio.HOY,
            motivo="Reembolso superior a $300.000 por cancelación de pedido",
            resumen=(
                f"Cancelación del pedido {pedido.numero} por un total de ${monto:,}. "
                "Supera el tope autónomo de $300.000, por lo que requiere aprobación de un asesor."
            ),
        )
        escalamientos.append(nuevo_esc)
        repositorio.guardar_escalamientos(escalamientos)

    nuevo_reembolso = repositorio.Reembolso(
        id=reembolso_id,
        numero_pedido=pedido.numero,
        cliente_id=sesion.cliente_id,
        fecha=repositorio.HOY,
        monto=monto,
        motivo="Reembolso automático por cancelación de pedido",
        estado=estado_reembolso,
    )
    reembolsos.append(nuevo_reembolso)
    repositorio.guardar_reembolsos(reembolsos)

    if escalado:
        mensaje_final = (
            f"Pedido {pedido.numero} cancelado. Debido a que el monto (${monto:,}) supera el tope autónomo "
            "de $300.000, el reembolso fue registrado como 'solicitado' y el caso fue escalado a un asesor."
        )
    else:
        mensaje_final = f"Pedido {pedido.numero} cancelado y reembolso de ${monto:,} aprobado automáticamente."

    return {
        "pedido_cancelado": pedido.numero,
        "estado": "cancelado",
        "reembolso_id": reembolso_id,
        "estado_reembolso": estado_reembolso,
        "monto": monto,
        "escalado": escalado,
        "mensaje": mensaje_final,
    }
