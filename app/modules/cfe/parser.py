import re
from io import BytesIO

from pypdf import PdfReader

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


def extract_service_numbers(
    text: str,
) -> tuple[list[str], str | None]:
    """
    Extrae uno o varios números de servicio CFE.

    Admite:
    386060102151
    416130801830
    386070464948

    También admite separación por:
    espacios, comas, saltos de línea y guiones simples.
    """

    raw = str(
        text or ""
    ).strip()

    if not raw:
        return (
            [],
            "Envía uno o varios números de servicio CFE.",
        )

    min_len = (
        settings.CFE_SERVICE_NUMBER_MIN_LEN
    )

    max_len = (
        settings.CFE_SERVICE_NUMBER_MAX_LEN
    )

    number_groups = re.findall(
        r"\d+",
        raw,
    )

    valid_values: list[str] = []

    for group in number_groups:
        if (
            min_len
            <= len(group)
            <= max_len
        ):
            valid_values.append(
                group
            )

    # Elimina repetidos conservando el orden.
    unique_values = list(
        dict.fromkeys(
            valid_values
        )
    )

    if not unique_values:
        return (
            [],
            "No encontré números de servicio CFE válidos.",
        )

    # Retira todos los números válidos para revisar
    # que no haya texto extraño.
    remainder = raw

    for value in unique_values:
        remainder = remainder.replace(
            value,
            "",
            1,
        )

    # Separadores admitidos entre números:
    # espacios, saltos de línea, coma, punto y coma,
    # guion, punto, slash y numeración tipo "1)".
    remainder = re.sub(
        r"[\s,;:\-._/|()]+",
        "",
        remainder,
    )

    if remainder:
        return (
            [],
            (
                "Envía únicamente números de "
                "servicio CFE, uno por línea."
            ),
        )

    return unique_values, None


def text_is_no_record(text: str) -> bool:
    upper = str(text or "").upper()

    return any(
        phrase in upper
        for phrase in settings.cfe_no_record_phrases
    )


def extract_service_number_from_pdf(
    pdf_bytes: bytes,
) -> tuple[str, str | None]:
    """
    Extrae el número de servicio desde un recibo CFE PDF.

    Admite formatos como:
    NO. DE SERVICIO:386170901440
    NO DE SERVICIO 386170901440
    NUMERO DE SERVICIO: 386170901440
    """

    if not pdf_bytes.startswith(b"%PDF"):
        return "", "El documento recibido no es un PDF válido."

    try:
        reader = PdfReader(
            BytesIO(pdf_bytes)
        )

        pages_text: list[str] = []

        for page in reader.pages:
            text = page.extract_text() or ""

            if text:
                pages_text.append(text)

        full_text = "\n".join(
            pages_text
        )

    except Exception as exc:
        print(
            "CFE_PDF_TEXT_EXTRACTION_FAILED",
            {
                "error": str(exc),
            },
            flush=True,
        )

        return (
            "",
            "No fue posible leer el PDF recibido.",
        )

    # Búsqueda principal: etiqueta de CFE.
    patterns = (
        r"""
        NO\.?\s*
        (?:DE\s*)?
        SERVICIO
        \s*[:#\-]?\s*
        (\d{8,20})
        """,
        r"""
        N[ÚU]MERO\s*
        (?:DE\s*)?
        SERVICIO
        \s*[:#\-]?\s*
        (\d{8,20})
        """,
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            full_text,
            flags=re.IGNORECASE
            | re.VERBOSE,
        )

        if match:
            return match.group(1), None

    # Fallback específico de la línea inferior
    # de algunos recibos CFE:
    # 01 386170901440 260726 ...
    fallback = re.search(
        r"""
        (?:^|\n)
        \s*01\s+
        (\d{8,20})
        \s+
        \d{6}
        \s+
        \d+
        """,
        full_text,
        flags=re.VERBOSE,
    )

    if fallback:
        return fallback.group(1), None

    return (
        "",
        (
            "No encontré el número de servicio "
            "dentro del PDF."
        ),
    )
