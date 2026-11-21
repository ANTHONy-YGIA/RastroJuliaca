# Resultados obtenidos

Solo se reportan resultados **ejecutados y verificables**. Los archivos de evidencia están en
`docs/evidencias/` y se regeneran con `.\scripts\test.ps1`.

## 1. Pruebas automatizadas (ejecución del 2026-11-20, Windows 11, Python 3.12.14, Node 26.13.0)

| Suite | Resultado | Duración | Evidencia |
|---|---|---|---|
| Backend (pytest) | **61 aprobadas, 0 fallidas, 0 omitidas** (última ejecución, tras la auditoría) | 43,9 s | `pytest-junit.xml`, `pytest-salida.txt` |
| Frontend: tipos + compilación (`tsc -b && vite build`) | Sin errores | < 1 s (build) | `frontend-build.txt` |
| Extremo a extremo + móvil (Playwright, Chromium) | **7 aprobadas, 0 fallidas, 0 inestables** | 92 s | `playwright-results.json`, `playwright-salida.txt` |

Las pruebas `test_real_tools.py` usaron **Microsoft Defender (MpCmdRun) y FFmpeg 9.0.2 reales** del
equipo. El resto de pruebas de backend usa, cuando necesita archivos disponibles, un doble de prueba
de antivirus declarado explícitamente en `tests/conftest.py`; la aplicación nunca lo usa.

### Cobertura de las pruebas obligatorias

| Prueba obligatoria | Casos que la verifican |
|---|---|
| Registro | `test_registro_y_sesion`, `test_registro_rechaza_duplicado_y_password_debil`, `test_no_se_puede_autoregistrar_personal`, E2E |
| Autenticación | `test_login_credenciales_invalidas_y_bloqueo`, `test_logout_invalida_sesion`, `test_endpoints_requieren_autenticacion`, `test_csrf_obligatorio_en_operaciones_de_escritura`, `test_rate_limit_login` |
| Creación de distintas categorías | `test_creacion_de_distintas_categorias`, `test_catalogo_de_categorias_y_subcategorias` |
| Campos dinámicos | `test_validacion_de_campos_dinamicos`, `test_backend_rechaza_campos_de_otra_categoria`, `test_subcategoria_hereda_campos_y_agrega_propios`, `test_admin_edita_esquema_validado`, E2E (validación Zod) |
| Revisión documental | `test_envio_exige_documentacion_segun_politica`, `test_revisor_aprueba_rechaza_y_solicita_correccion`, `test_documentos_no_aceptados_si_no_superan_validacion` |
| Publicación moderada | `test_ficha_publica_solo_muestra_datos_autorizados`, `test_minimizacion_rechaza_datos_personales_en_ficha`, `test_restringido_requiere_doble_aprobacion_y_ficha_minima` |
| Aportaciones | `test_aportacion_pasa_por_cuarentena_y_validacion`, `test_aportaciones_solo_a_expedientes_habilitados`, `test_duplicado_exacto_detectado` |
| Cuarentena | `test_sin_antivirus_el_archivo_queda_bloqueado`, `test_archivo_infectado_se_elimina`, `test_validacion_de_formato_y_contenido`, `test_limite_de_tamano`, `test_microsoft_defender_real`, `test_video_*` |
| Permisos | `test_roles_no_cruzan_permisos`, `test_revisor_no_asignado_no_accede`, `test_revisor_sin_habilitacion_no_accede_a_restringido`, `test_acceso_a_archivos_autorizado_y_registrado`, E2E roles |
| Aislamiento entre expedientes | `test_aislamiento_entre_expedientes`, `test_denunciante_no_accede_a_expedientes_ajenos`, `test_idor_en_notificaciones_y_solicitudes`, E2E aislamiento |
| Clasificación | `test_clasificacion_y_observaciones`, E2E |
| Filtros | `test_ordenamiento_por_proximidad_y_datos_insuficientes`, `test_filtro_por_radio_no_descarta_sin_datos`, `test_haversine` |
| Línea de tiempo | `test_linea_de_tiempo_y_correcciones_sin_sobrescribir`, E2E |
| Exportación | `test_informe_json_con_integridad_y_auditoria` (JSON + PDF + hash + auditoría), E2E (descarga JSON) |
| Restricciones de incidentes sensibles | `test_institucional_no_publica_ni_abre_aportaciones`, `test_marcadores_protegidos_fuerzan_institucional_y_no_se_eliminan`, `test_admin_no_puede_reducir_protecciones`, `test_elevar_sensibilidad_retira_publicacion_existente` |
| Interfaz móvil | `e2e/movil.spec.ts` (3 pruebas, Pixel 7 emulado: sin desplazamiento horizontal, menú móvil, paneles) |
| Flujo E2E completo | `e2e/flujo-completo.spec.ts › recorrido completo del MVP` (puntos 1–13 del objetivo) |

### Verificación manual adicional

- **Persistencia tras reinicio real del servidor** (2026-11-20): se registró una cuenta vía API, se
  detuvo el proceso uvicorn, se volvió a iniciar y se inició sesión con esa cuenta; las estadísticas
  públicas (2 fichas, 11 categorías) se mantuvieron. Además `test_persistencia_tras_reinicio` lo verifica
  con un motor nuevo sobre el mismo archivo SQLite.
- **Instalación desde cero** con `scripts\setup.ps1 -Reset`: completada sin errores; los 16 archivos
  ficticios de demostración quedaron *Validados* tras el análisis real de Microsoft Defender.
- Revisión visual en el navegador integrado: portada, inicio de sesión, panel del revisor, evidencias
  y visor de video (copia segura reproducible).

Auditoría de preparación (instalación, GitHub, seguridad): ver [`auditoria.md`](auditoria.md).

## 2. Criterios de aceptación

| # | Criterio | Estado | Evidencia |
|---|---|---|---|
| 1 | Expedientes de diferentes categorías | Cumplido | `test_creacion_de_distintas_categorias` |
| 2 | Cada categoría muestra sus campos correctos | Cumplido | `test_catalogo_…`, E2E (campos de "Objetos extraviados") |
| 3 | Los documentos permanecen privados | Cumplido | `test_acceso_a_archivos_autorizado_y_registrado`, `test_ficha_publica_solo_muestra_datos_autorizados` |
| 4 | Un revisor puede aprobar o rechazar | Cumplido | `test_revisor_aprueba_rechaza_y_solicita_correccion` |
| 5 | Fichas públicas solo con datos autorizados | Cumplido | `test_ficha_publica_solo_muestra_datos_autorizados`, E2E |
| 6 | Un colaborador aporta a un caso habilitado | Cumplido | `test_aportaciones_solo_a_expedientes_habilitados`, E2E |
| 7 | Archivos validados antes de estar disponibles | Cumplido | `test_sin_antivirus_…`, `test_microsoft_defender_real` |
| 8 | Los revisores clasifican evidencias | Cumplido | `test_clasificacion_y_observaciones`, E2E |
| 9 | Nadie accede a expedientes privados ajenos | Cumplido | `test_permissions_isolation.py`, E2E |
| 10 | Filtros y línea de tiempo funcionan | Cumplido | `test_review_tools.py`, E2E |
| 11 | Se genera un informe real | Cumplido | `test_informe_json_con_integridad_y_auditoria`, E2E |
| 12 | Persistencia tras reinicio | Cumplido | prueba manual + `test_persistencia_tras_reinicio` |
| 13 | Interfaz en escritorio y móvil | Cumplido (emulación Chromium) | `e2e/movil.spec.ts`; no probado en dispositivos físicos ni en Firefox/Safari |
| 14 | Las pruebas principales se ejecutan correctamente | Cumplido | sección 1 |

## 3. Experimento con participantes

**Pendiente.** No se han realizado sesiones con participantes; por lo tanto **no existen** resultados
de tiempo, errores de asociación, tareas completadas ni usabilidad, y no se reporta ningún porcentaje de
mejora. Las herramientas están listas y probadas en vacío:

- `experiment/generar_conjuntos.py` generó los conjuntos C1 y C2 (18 evidencias sintéticas cada uno).
- `experiment/servidor_escenario_b.py --conjunto C1 --solo-cargar` cargó el conjunto C1 con análisis
  antivirus real.
- `experiment/analizar_resultados.py` informa "Sin datos" mientras no exista `resultados/sesiones.csv`.

Cuando se ejecuten las sesiones, esta sección debe completarse con el contenido de
`experiment/resultados/resumen.json` y las observaciones cualitativas.
