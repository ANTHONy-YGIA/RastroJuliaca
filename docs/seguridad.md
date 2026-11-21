# Seguridad y privacidad — controles implementados

Este documento describe controles **implementados y verificados por pruebas** en el MVP. No implica
seguridad absoluta ni certificación.

## Amenazas consideradas y controles

| Amenaza | Control | Dónde | Prueba |
|---|---|---|---|
| Robo de contraseñas | Argon2id; mensajes de error genéricos; tiempo constante con hash ficticio | `security.py`, `routers/auth.py` | `test_auth.py` |
| Fuerza bruta | Rate limiting por IP; bloqueo de 15 min tras 5 fallos | `ratelimit.py`, `auth.py` | `test_login_credenciales_invalidas_y_bloqueo`, `test_rate_limit_login` |
| Secuestro de sesión | Token aleatorio de 256 bits; en BD solo HMAC-SHA256; cookie HttpOnly + SameSite=Strict; expiración | `auth.py`, `deps.py` | `test_registro_y_sesion` |
| CSRF | Double submit: cabecera `X-CSRF-Token` comparada en tiempo constante con la sesión | `deps.py` | `test_csrf_obligatorio_en_operaciones_de_escritura` |
| IDOR / acceso horizontal | Toda consulta filtra por propietario o asignación; 404 para no revelar existencia | `deps.py`, routers | `test_permissions_isolation.py` |
| Escalada de privilegios | Roles verificados en backend; personal no se auto-registra; admin sin acceso a evidencias | `deps.py`, `admin.py` | `test_roles_no_cruzan_permisos`, `test_no_se_puede_autoregistrar_personal` |
| Mezcla de evidencias | Consultas por expediente; informes rechazan evidencias de otro expediente | `review.py`, `reports.py` | `test_aislamiento_entre_expedientes` |
| Malware | Cuarentena; antivirus real; sin motor → bloqueado; infectado → eliminado | `services/pipeline.py`, `antivirus.py` | `test_sin_antivirus_el_archivo_queda_bloqueado`, `test_archivo_infectado_se_elimina`, `test_microsoft_defender_real` |
| Archivos disfrazados | Detección por firma binaria; PDF con contenido activo rechazado; imágenes verificadas | `storage.py`, `media.py` | `test_validacion_de_formato_y_contenido` |
| Bombas de descompresión / DoS por archivos | Límites de tamaño por tipo durante la recepción; límite de píxeles; duración máxima de video; procesos FFmpeg con timeout, hilos limitados y prioridad baja | `storage.py`, `media.py` | `test_limite_de_tamano`, `test_video_falso_rechazado` |
| Path traversal | Nombres internos aleatorios validados por expresión regular; nombre original solo como metadato | `storage.py` | `test_nombres_internos_aleatorios_y_fuera_de_directorio_publico` |
| Fuga de metadatos (GPS/EXIF) | Copias de reproducción re-codificadas sin metadatos; originales nunca públicos | `media.py` | `test_video_genera_copia_segura_con_ffmpeg` |
| Exposición de datos en fichas | Campos publicables por esquema + autorización del revisor; detector de DNI, teléfono, correo, coordenadas, nombre y ubicación privada | `review.py` | `test_ficha_publica_solo_muestra_datos_autorizados`, `test_minimizacion_rechaza_datos_personales_en_ficha` |
| Desactivación de protecciones | Pisos de sensibilidad en código; marcadores no retirables; elevación propagada | `policies.py`, `admin.py` | `test_admin_no_puede_reducir_protecciones`, `test_marcadores_protegidos_fuerzan_institucional_y_no_se_eliminan` |
| Exposición del colaborador | Seudónimo `COL-XXXXXX` para revisores | `serializers.py` | `test_revisor_ve_seudonimo_no_identidad_del_colaborador` |
| Repudio / trazabilidad | Auditoría de accesos, descargas, decisiones, exportaciones y cambios | `audit.py` | `test_acceso_a_archivos_autorizado_y_registrado`, `test_informe_json_con_integridad_y_auditoria` |
| Clickjacking / XSS | CSP restrictiva, `frame-ancestors 'none'`, X-Frame-Options DENY, React escapa contenido | `main.py` | `test_cabeceras_de_seguridad` |
| Exposición en red | Servidor ligado a 127.0.0.1; TrustedHost | `start.ps1`, `main.py` | — |

## Privacidad (Ley N.° 29733 y D. S. N.° 016-2024-JUS — consideraciones, no certificación)

- **Finalidad y minimización:** fichas públicas generalizadas; ubicación privada opcional y nunca publicada.
- **Consentimiento informado:** aceptación del aviso al registrarse; declaración al aportar.
- **Derechos del titular:** exportación de datos propios (acceso) y solicitudes de acceso,
  rectificación, cancelación u oposición atendidas y auditadas por la administración, con
  anonimización de cuenta cuando procede.
- **Conservación:** plazos configurables (mínimos protegidos) y ejecución con simulación previa.
- **Videovigilancia:** los videos aportados no se publican; solo revisores asignados ven copias seguras.

## Pendientes conocidos

- Cifrado en reposo a nivel de aplicación.
- Rate limiting distribuido para despliegues multi-proceso.
- Saneamiento completo de PDF (actualmente se rechazan PDF con contenido activo).
- Autenticación de dos factores para el personal.
- Auditoría externa / pruebas de penetración.
