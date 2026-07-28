# tramites-extras-bot

Servicio independiente para trámites adicionales. Incluye flujo CFE por WhatsApp/Evolution y una interfaz desactivada para futura integración RENAPO autorizada.

## Seguridad
El webhook exige `X-Webhook-Secret`. Configura Evolution o un proxy para enviar ese encabezado. Si tu versión no permite encabezados personalizados, usa una ruta secreta o valida una firma en nginx antes de producción.
