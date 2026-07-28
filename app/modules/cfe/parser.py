import re
from app.config import settings


def extract_service_number(text: str) -> tuple[str, str | None]:
    normalized = re.sub(r'[\s\-._]', '', text or '')
    values = re.findall(r'(?<!\d)(\d{%d,%d})(?!\d)' % (settings.CFE_SERVICE_NUMBER_MIN_LEN, settings.CFE_SERVICE_NUMBER_MAX_LEN), normalized)
    unique = list(dict.fromkeys(values))
    if not unique:
        return '', 'Envía únicamente el número de servicio CFE.'
    if len(unique) > 1:
        return '', 'Detecté más de un número. Envía solo un número de servicio CFE.'
    return unique[0], None


def text_is_no_record(text: str) -> bool:
    upper = (text or '').upper()
    return any(phrase in upper for phrase in settings.cfe_no_record_phrases)
