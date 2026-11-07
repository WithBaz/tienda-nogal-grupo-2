"""Herramientas para escalamiento de casos a asesores humanos."""
from pydantic import BaseModel, Field

from agente.herramientas.registro import ErrorDeHerramienta, herramienta
from agente.sesion import Sesion
from tienda import repositorio


class ArgsEscalarCaso(BaseModel):
    motivo: str = Field(description="Razón por la cual se escala el caso a un asesor humano.")
    resumen: str = Field(
        description="Resumen breve y claro de la situación, antecedentes del cliente y motivo de consulta, para que el asesor no repita preguntas."
    )
    numero_pedido: str | None = Field(
        default=None,
        description="Número de pedido relacionado si la consulta está asociada a uno específico.",
    )


@herramienta
def escalar_caso(sesion: Sesion, args: ArgsEscalarCaso) -> dict:
    """Escala la conversación a un asesor humano cuando la política lo requiere o el cliente lo solicita."""
    motivo_limpio = args.motivo.strip() if args.motivo else ""
    resumen_limpio = args.resumen.strip() if args.resumen else ""

    if not motivo_limpio:
        raise ErrorDeHerramienta("Se requiere indicar el motivo del escalamiento.")
    if not resumen_limpio:
        raise ErrorDeHerramienta("Se requiere generar un resumen breve del caso para el asesor humano.")

    # Validar pedido si se proporcionó
    numero_pedido = None
    if args.numero_pedido:
        pedidos = repositorio.leer_pedidos()
        pedido = next((p for p in pedidos if p.numero == args.numero_pedido), None)
        if pedido and pedido.cliente_id == sesion.cliente_id:
            numero_pedido = pedido.numero

    escalamientos = repositorio.leer_escalamientos()
    ids_existentes = {e.id for e in escalamientos}
    idx = len(escalamientos) + 1
    while f"E-{idx:03d}" in ids_existentes:
        idx += 1
    nuevo_id = f"E-{idx:03d}"

    nuevo_escalamiento = repositorio.Escalamiento(
        id=nuevo_id,
        cliente_id=sesion.cliente_id,
        numero_pedido=numero_pedido,
        fecha=repositorio.HOY,
        motivo=motivo_limpio,
        resumen=resumen_limpio,
    )
    escalamientos.append(nuevo_escalamiento)
    repositorio.guardar_escalamientos(escalamientos)

    return {
        "escalamiento_id": nuevo_id,
        "cliente_id": sesion.cliente_id,
        "numero_pedido": numero_pedido,
        "mensaje": (
            f"El caso ha sido escalado exitosamente a un asesor humano (ticket {nuevo_id}). "
            "Se le informa al cliente que un asesor lo contactará en un plazo máximo de un día hábil."
        ),
    }
