# Auditoría de preparación — RastroJuliaca

Fecha: 2026-11-20 · Alcance: funcional, seguridad, instalación, preparación para GitHub/ZIP.
Solo se reportan resultados ejecutados en este equipo (Windows 11, Windows PowerShell 5.1).

## 1. Funcionalidades terminadas

Verificadas por pruebas automatizadas (backend y navegador) y por las pruebas manuales del equipo:

- Registro, inicio/cierre de sesión, bloqueo por intentos fallidos, CSRF, rate limiting.
- 11 categorías con subcategorías y formularios dinámicos validados en frontend (Zod) y backend.
- Expedientes privados con documentación de respaldo y política documental por categoría.
- Revisión documental: aceptar/observar documentos; aprobar, rechazar, solicitar corrección, cerrar.
- Publicación moderada con minimización, segunda aprobación para RESTRINGIDO y bloqueo para INSTITUCIONAL.
- Aportaciones (video, foto, documento, texto), seguimiento privado y correcciones sin sobrescritura.
- Pipeline de archivos: cuarentena, Microsoft Defender real, validación por firma, SHA-256, duplicados, copias seguras (Pillow/FFmpeg), acceso auditado.
- Panel del revisor: clasificación, observaciones, filtros, cercanía Haversine/temporal, línea de tiempo.
- Informes JSON y PDF con hash de integridad y exportación auditada.
- Administración: usuarios, permisos sensibles, asignaciones, categorías/esquemas, auditoría, conservación, derechos del titular.
- Interfaz responsive (escritorio y móvil emulado).

## 2. Problemas detectados

| # | Severidad | Problema |
|---|---|---|
| P1 | **Crítica (instalación)** | `backend\.venv\Scripts\python.exe` (creado con `uv venv`) está bloqueado por Windows; `setup.ps1`, `start.ps1`, `test.ps1` y `playwright.config.ts` tenían la ruta `.venv` fija, por lo que no se podía instalar ni ejecutar con los scripts. |
| P2 | **Alta (GitHub)** | `.gitignore` no excluía `backend/.venv_alt/` (≈2.700 archivos), `.claude/` (rutas locales) ni `*.egg-info`. |
| P3 | **Alta (despliegue)** | Sin límite global del cuerpo de la solicitud: un archivo enorme se escribía en disco temporal antes de rechazarse (riesgo de llenar el disco). |
| P4 | **Alta (despliegue)** | Nada impedía arrancar en `RJ_ENV=production` con modo demostración (contraseña pública de las cuentas demo), cookies sin `Secure` o con el secreto de ejemplo. |
| P5 | Media | Un archivo cuyo procesamiento se interrumpía (p. ej. al reiniciar el servidor) quedaba en cuarentena sin forma de reanalizarlo. |
| P6 | Media (instalación) | `setup.ps1 -Reset` borraba la base de datos sin pedir confirmación. |
| P7 | Baja | Instrucciones de uso de los scripts del experimento y el README del frontend apuntaban a rutas/plantillas obsoletas. |
| P8 | Baja | `.venv_alt` no tenía las dependencias de prueba (pytest/httpx). |
| P9 | Media (pruebas) | En Windows PowerShell 5.1, `test.ps1` abortaba Playwright: con `ErrorActionPreference=Stop`, cualquier línea en stderr se trataba como error fatal. |

No se encontraron fallos en los flujos funcionales ni en las restricciones de acceso del backend.

## 3. Problemas corregidos

| # | Corrección | Verificación |
|---|---|---|
| P1 | Nuevo `scripts/_entorno.ps1`: prueba cada entorno (`.venv`, `.venv_alt`, `.venv-rj`, o cualquiera con `pyvenv.cfg`, o `RJ_VENV`) ejecutándolo de verdad y usa el primero funcional. `setup.ps1` crea entornos con `python -m venv` en un nombre libre, nunca borra uno existente, y admite `-VenvDir`. `start.ps1`/`test.ps1` usan la misma detección; Playwright usa `RJ_PYTHON` o la misma detección. Nuevo `scripts/py.ps1`. Sin rutas de este equipo. | `setup.ps1` y `test.ps1` ejecutados en Windows PowerShell 5.1 con `RemoteSigned`; instalación desde cero en una copia limpia (ver §4). |
| P2 | `.gitignore` reescrito: entornos `.venv*/`, `venv*/`, `.env*` (salvo `.env.example`), BD (`*.db`, WAL/SHM), `data/`, almacenamiento/cuarentena, `*.log`, `node_modules`, `dist`, resultados de pruebas, `.claude/`, `*.egg-info`, conjuntos y resultados del experimento. | `git add --dry-run`: 105 archivos (antes 2.792); ninguno contiene secretos, correos reales ni rutas de usuario. |
| P3 | Middleware que rechaza con 413 cuerpos con `Content-Length` mayor al máximo permitido y con 411 subidas *chunked* sin longitud. | `test_cuerpo_excesivo_rechazado_antes_de_procesar` |
| P4 | Con `RJ_ENV=production` el servidor no arranca si el secreto es el de ejemplo o corto, si `RJ_DEMO_MODE=true` o si `RJ_COOKIE_SECURE=false`. | `test_guardas_de_produccion` |
| P5 | El administrador puede reanalizar archivos detenidos en cuarentena más de 10 min. | `test_reanalisis_de_cuarentena_detenida` |
| P6 | `-Reset` exige escribir `SI`. | Revisión del script |
| P7 | Docstrings del experimento usan `.\scripts\py.ps1`; README del frontend reemplazado; README principal con instrucciones de Windows, solución al bloqueo de `python.exe` e instalación manual. | Revisión |
| P8 | Dependencias de desarrollo instaladas en `.venv_alt` (sin borrar nada). | pytest ejecutado |
| P9 | `test.ps1` usa `Continue` para las herramientas externas, evalúa su código de salida y guarda su salida como texto plano. | `test.ps1` ejecutado completo en PowerShell 5.1 (ver §4) |

Además, los cinco scripts `.ps1` se guardan en UTF-8 con BOM para que Windows PowerShell 5.1 muestre bien las tildes.

## 4. Pruebas ejecutadas y resultados

Todas ejecutadas en este equipo el 2026-11-20 con `.\scripts\test.ps1` desde **Windows PowerShell 5.1**
(`RemoteSigned`, intérprete detectado automáticamente: `backend\.venv_alt`). Evidencia en `docs/evidencias/`.

| Prueba | Resultado |
|---|---|
| Backend (pytest), incluidas 3 nuevas de esta auditoría | **61 aprobadas, 0 fallidas** (43,9 s) |
| Tipos y compilación del frontend (`tsc -b && vite build`) | Sin errores |
| Playwright: recorrido completo de 13 pasos, aislamiento, roles, persistencia (escritorio) | **4/4 aprobadas** |
| Playwright: portada/menú, ficha pública/ingreso, paneles (móvil Pixel 7 emulado) | **3/3 aprobadas** (91,6 s en total) |
| Integración real con Microsoft Defender y FFmpeg | Incluida en pytest (aprobada) |
| `setup.ps1` sobre el proyecto existente (PS 5.1) | Correcto: reutilizó `.venv_alt`, conservó la BD |
| Instalación desde cero en una copia con solo los 104 archivos versionables (PS 5.1) | Correcta: creó `backend\.venv` con `python -m venv`, generó `.env` con secreto aleatorio, sembró 9 expedientes y 16 archivos validados por Defender |
| `start.ps1` en la copia limpia (puerto 8012) | `/api/health` OK, portada 200, estadísticas públicas correctas |
| Restricciones de acceso en el backend (no solo React) | Verificadas por pruebas de API directas: revisor no asignado → 404, colaborador → 403 en revisión/administración, administrador → sin acceso a evidencias, aislamiento entre expedientes |
| BD local del equipo (solo lectura) | 16 archivos DISPONIBLES, 0 errores; estados coherentes con las pruebas manuales |

## 5. Riesgos pendientes (no corregidos)

| Riesgo | Impacto | Recomendación |
|---|---|---|
| No existe cambio ni recuperación de contraseña | El personal creado por el administrador conserva su contraseña inicial | Añadir antes de cualquier uso real |
| Contraseña demo pública (`Demo-Juliaca-2026`) | Cualquiera entra como administrador si la demo es accesible desde la red | Mantener la demo en `127.0.0.1`; en producción el servidor ya se niega a arrancar en modo demo |
| Rate limiting en memoria | No protege varios procesos/servidores | Almacén compartido (Redis) o proxy inverso |
| Enumeración de cuentas | Registro (409) y bloqueo (423) revelan si un correo existe | Respuestas uniformes |
| Sin cifrado en reposo propio | Archivos y BD legibles con acceso al disco | BitLocker o cifrado de la aplicación |
| PDF: solo se rechaza contenido activo | No es un saneamiento completo | Saneador dedicado |
| Sin 2FA para el personal | Riesgo ante robo de credenciales | Añadir TOTP |
| Sin pruebas de carga ni pentest externo | Comportamiento desconocido bajo ataque o carga | Antes de cualquier despliegue público |
| PostgreSQL no probado | Posibles diferencias con SQLite | Probar migraciones y pruebas sobre PostgreSQL |
| Experimento con participantes sin ejecutar | No hay evidencia de mejora medida | Ejecutar `experiment/protocolo.md` antes de afirmar mejoras |
| `backend\.venv` dañado/bloqueado sigue en disco | Solo ocupa espacio; los scripts lo ignoran | Eliminarlo manualmente si se desea (no se borró sin autorización) |

## 6. Preparación para GitHub

**Lista con observaciones.** `.gitignore` excluye entornos, `.env`, BD, archivos subidos, cuarentena,
registros y configuración local. Los 105 archivos a versionar (incluido este informe) no contienen secretos ni datos personales;
las cuentas y medios de demostración son ficticios y se generan localmente. Aún no hay commits ni
repositorio remoto (no se publicó nada). Antes de publicar: elegir licencia, revisar `docs/evidencias/`
(contiene rutas absolutas de la carpeta del proyecto en el JSON de Playwright, sin datos personales) y
confirmar que el repositorio se cree como privado o público según decida el equipo.

## 7. Preparación para entregar en ZIP

**Lista**, siempre que el ZIP se genere solo con los archivos versionables (por ejemplo, con
`git archive` tras el primer commit). **No** comprima la carpeta completa: incluiría `.env` (secreto local),
`data/` (BD y archivos), `node_modules` y los entornos virtuales. Quien lo reciba debe ejecutar
`Get-ChildItem .\scripts\*.ps1 | Unblock-File` tras revisar el origen, y luego `.\scripts\setup.ps1`.

## 8. Viabilidad de una demo pública

**No recomendada en el estado actual.** El sistema está diseñado y probado para demostraciones locales
(`127.0.0.1`). Para exponerlo en internet faltan: HTTPS con proxy inverso y límites de tamaño, desactivar
el modo demostración y crear cuentas reales con contraseñas propias, cambio de contraseña, rate limiting
compartido, copias de respaldo, revisión legal (Ley N.° 29733 y su Reglamento) y una prueba de seguridad
externa. Las nuevas guardas impiden arrancar en `production` con la configuración insegura más obvia,
pero no sustituyen esas medidas.

## 9. Veredicto

**LISTO CON OBSERVACIONES** para presentarse en el concurso universitario (demostración local),
subirse a GitHub y entregarse en ZIP a otro integrante.

Observaciones: (1) no hay cambio de contraseña; (2) el experimento con participantes está pendiente,
por lo que no debe afirmarse una mejora medida; (3) **no** está listo para una demo pública en internet
(ver §8); (4) aún no existe ningún commit: el primer commit y la publicación quedan a decisión del equipo.
