import re

from app.config import settings


def extract_service_number(text: str) -> tuple[str, str | None]:
    raw = str(text or "").strip()

    if not raw:
        return "", "Envía únicamente el número de servicio CFE."

    min_len = settings.CFE_SERVICE_NUMBER_MIN_LEN
    max_len = settings.CFE_SERVICE_NUMBER_MAX_LEN

    # Detecta secuencias numéricas independientes antes de normalizar.
    # Esto evita unir dos números distintos separados por espacios.
    number_groups = re.findall(r"\d+", raw)

    valid_values: list[str] = []

    for group in number_groups:
        if min_len <= len(group) <= max_len:
            valid_values.append(group)

    unique_values = list(dict.fromkeys(valid_values))

    if not unique_values:
        return "", "Envía únicamente el número de servicio CFE."

    if len(unique_values) > 1:
        return (
            "",
            "Detecté más de un número. Envía solo un número de servicio CFE.",
        )

    candidate = unique_values[0]

    # Después de retirar el único número válido, solo permitimos
    # separadores simples. Si quedan letras u otros números, se rechaza.
    remainder = raw.replace(candidate, "", 1)
    remainder = re.sub(r"[\s\-._]", "", remainder)

    if remainder:
        return "", "Envía únicamente el número de servicio CFE."

    return candidate, None


def text_is_no_record(text: str) -> bool:
    upper = str(text or "").upper()

    return any(
        phrase in upper
        for phrase in settings.cfe_no_record_phrases
    )
