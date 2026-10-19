"""Herramientas para gestión de reclamos."""
from pydantic import BaseModel, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio

PLAZOS_BASE = {
    "perecedero": 3,
    "ropa": 30,
    "electronica": 90,
    "hogar": 15,
}


class ArgsRegistrarReclamo(BaseModel):
    numero_pedido: str = Field(description="Número del pedido sobre el que se presenta el reclamo (ejemplo: 'P-1002').")
    motivo: str = Field(description="Motivo detallado del reclamo descrito por el cliente (producto defectuoso, incompleto o distinto).")
    producto_nombre: str | None = Field(
        default=None,
        description="Opcional. Nombre específico del producto que presentó el problema, si el pedido contiene varios.",
    )


@herramienta
def registrar_reclamo(sesion: Sesion, args: ArgsRegistrarReclamo) -> dict:
    """Registra un reclamo para un pedido entregado si se encuentra dentro de los plazos y no existe reclamo abierto."""
    pedidos = repositorio.leer_pedidos()
    pedido = next((p for p in pedidos if p.numero == args.numero_pedido), None)

    # 1. Validación de pertenencia al cliente
    if not pedido or pedido.cliente_id != sesion.cliente_id:
        raise ErrorDeHerramienta(f"No se encontró el pedido '{args.numero_pedido}'.")

    # 2. Validación de estado entregado
    if pedido.estado != "entregado":
        raise ErrorDeHerramienta(
            f"Solo se puede presentar un reclamo cuando el pedido figura como entregado. "
            f"El pedido '{args.numero_pedido}' se encuentra en estado '{pedido.estado}'."
        )

    # 3. Validación de motivo
    motivo_limpio = args.motivo.strip() if args.motivo else ""
    if not motivo_limpio:
        raise ErrorDeHerramienta("Es obligatorio registrar el motivo descrito por el cliente para abrir un reclamo.")

    # 4. Validación de unicidad de reclamo abierto
    reclamos = repositorio.leer_reclamos()
    abierto = next((r for r in reclamos if r.numero_pedido == args.numero_pedido and r.estado == "abierto"), None)
    if abierto:
        raise ErrorDeHerramienta(
            f"El pedido '{args.numero_pedido}' ya tiene un reclamo abierto ({abierto.id}) "
            f"registrado el {abierto.fecha}. Estado actual: {abierto.estado}."
        )

    # 5. Validación de plazos por categoría y cliente preferente
    cliente = next((c for c in repositorio.leer_clientes() if c.id == sesion.cliente_id), None)
    dias_extra = 15 if cliente and cliente.categoria == "preferente" else 0

    if args.producto_nombre:
        prod = next((p for p in pedido.productos if args.producto_nombre.lower() in p.nombre.lower()), None)
        plazo_base = PLAZOS_BASE.get(prod.categoria, 15) if prod else max(PLAZOS_BASE.get(p.categoria, 15) for p in pedido.productos)
    else:
        plazo_base = max(PLAZOS_BASE.get(p.categoria, 15) for p in pedido.productos)

    plazo_total = plazo_base + dias_extra
    dias_transcurridos = (repositorio.HOY - pedido.fecha_entrega).days

    if dias_transcurridos > plazo_total:
        raise ErrorDeHerramienta(
            f"El plazo para reclamar ha vencido. Han transcurrido {dias_transcurridos} días desde la entrega "
            f"y el plazo máximo permitido según las políticas es de {plazo_total} días."
        )

    # 6. Creación del reclamo
    ids_existentes = {r.id for r in reclamos}
    idx = len(reclamos) + 1
    while f"R-{idx:03d}" in ids_existentes:
        idx += 1
    nuevo_id = f"R-{idx:03d}"

    nuevo_reclamo = repositorio.Reclamo(
        id=nuevo_id,
        numero_pedido=args.numero_pedido,
        cliente_id=sesion.cliente_id,
        fecha=repositorio.HOY,
        motivo=motivo_limpio,
        estado="abierto",
    )
    reclamos.append(nuevo_reclamo)
    repositorio.guardar_reclamos(reclamos)

    return {
        "reclamo_id": nuevo_id,
        "estado": "abierto",
        "numero_pedido": args.numero_pedido,
        "mensaje": f"Reclamo {nuevo_id} registrado exitosamente.",
    }
