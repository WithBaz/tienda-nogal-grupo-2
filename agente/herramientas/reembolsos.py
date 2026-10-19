"""Herramientas para solicitud de reembolsos."""
from pydantic import BaseModel, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


class ArgsSolicitarReembolso(BaseModel):
    numero_pedido: str = Field(description="Número del pedido sobre el que se solicita el reembolso.")
    monto: int | None = Field(default=None, description="Monto en pesos colombianos a reembolsar. Si no se indica, se asume el total del pedido.")
    motivo: str = Field(default="Solicitud de reembolso por cliente", description="Motivo por el cual se solicita el reembolso.")
    confirmado_por_cliente: bool = Field(
        default=False,
        description="Debe ser True ÚNICAMENTE si el cliente confirmó explícitamente en el chat que desea este reembolso.",
    )


@herramienta
def solicitar_reembolso(sesion: Sesion, args: ArgsSolicitarReembolso) -> dict:
    """Solicita un reembolso para un pedido que ha sido cancelado o que tiene un reclamo abierto."""
    pedidos = repositorio.leer_pedidos()
    pedido = next((p for p in pedidos if p.numero == args.numero_pedido), None)

    # 1. Pertenencia
    if not pedido or pedido.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta(f"No se encontró el pedido '{args.numero_pedido}'.")

    # 2. Procedencia: debe estar cancelado o tener un reclamo abierto
    reclamos = repositorio.leer_reclamos()
    tiene_reclamo_abierto = any(r.numero_pedido == args.numero_pedido and r.estado == "abierto" for r in reclamos)
    if pedido.estado != "cancelado" and not tiene_reclamo_abierto:
        raise ErrorDeHerramienta(
            f"No procede reembolso para el pedido '{args.numero_pedido}'. "
            "La política exige que el pedido haya sido cancelado o cuente con un reclamo abierto."
        )

    # 3. Validación de monto
    monto = args.monto if args.monto is not None else pedido.total
    if monto <= 0:
        raise ErrorDeHerramienta("El monto a reembolsar debe ser mayor a cero.")

    if monto > pedido.total:
        raise ErrorDeHerramienta(
            f"El monto a reembolsar (${monto:,}) nunca puede superar el valor total pagado por el pedido (${pedido.total:,})."
        )

    # Revisar si ya hay reembolsos aprobados previos que agoten el total
    reembolsos_existentes = repositorio.leer_reembolsos()
    total_reembolsado_previo = sum(r.monto for r in reembolsos_existentes if r.numero_pedido == args.numero_pedido)
    if total_reembolsado_previo + monto > pedido.total:
        raise ErrorDeHerramienta(
            f"El pedido ya tiene reembolsos por ${total_reembolsado_previo:,}. "
            f"El nuevo reembolso de ${monto:,} superaría el valor total de la compra (${pedido.total:,})."
        )

    # 4. Confirmación explícita obligatoria
    if not args.confirmado_por_cliente:
        return {
            "requiere_confirmacion": True,
            "numero_pedido": pedido.numero,
            "monto": monto,
            "mensaje": (
                f"Para solicitar el reembolso de ${monto:,} correspondiente al pedido {pedido.numero}, "
                "es OBLIGATORIO pedir confirmación explícita al cliente. "
                "Solo cuando confirme afirmativamente, vuelve a llamar a solicitar_reembolso con confirmado_por_cliente=True."
            ),
        }

    # 5. Evaluación de tope autónomo ($300.000)
    ids_reembolsos = {r.id for r in reembolsos_existentes}
    idx = len(reembolsos_existentes) + 1
    while f"M-{idx:03d}" in ids_reembolsos:
        idx += 1
    reembolso_id = f"M-{idx:03d}"

    escalado = False
    if monto <= 300000:
        estado_reembolso = "aprobado"
        mensaje = f"Reembolso {reembolso_id} por ${monto:,} aprobado directamente."
    else:
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
            motivo="Aprobación de reembolso superior a $300.000",
            resumen=(
                f"El cliente solicita reembolso de ${monto:,} para el pedido {pedido.numero}. "
                "Por superar el límite autónomo de $300.000, requiere autorización de un asesor humano."
            ),
        )
        escalamientos.append(nuevo_esc)
        repositorio.guardar_escalamientos(escalamientos)
        mensaje = (
            f"El monto a reembolsar (${monto:,}) supera el tope autónomo de $300.000. "
            f"La solicitud {reembolso_id} quedó en estado 'solicitado' y fue escalada a un asesor."
        )

    nuevo_reembolso = repositorio.Reembolso(
        id=reembolso_id,
        numero_pedido=pedido.numero,
        cliente_id=sesion.cliente_id,
        fecha=repositorio.HOY,
        monto=monto,
        motivo=args.motivo.strip() if args.motivo else "Reembolso solicitado",
        estado=estado_reembolso,
    )
    reembolsos_existentes.append(nuevo_reembolso)
    repositorio.guardar_reembolsos(reembolsos_existentes)

    return {
        "reembolso_id": reembolso_id,
        "numero_pedido": pedido.numero,
        "monto": monto,
        "estado": estado_reembolso,
        "escalado": escalado,
        "mensaje": mensaje,
    }
