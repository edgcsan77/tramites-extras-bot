from app.config import settings


def generate_curp_pdf(curp: str) -> bytes:
    """Adapter reservado para una integración autorizada.

    No incluye evasión de CAPTCHA, controles anti-bot ni acceso no autorizado.
    Implementa aquí una API oficial, convenio autorizado o automatización permitida
    por los términos del portal correspondiente.
    """
    if not settings.RENAPO_ENABLED or settings.RENAPO_MODE == 'disabled':
        raise RuntimeError('RENAPO_MODULE_DISABLED')
    raise NotImplementedError('CONFIGURE_AUTHORIZED_RENAPO_PROVIDER')
