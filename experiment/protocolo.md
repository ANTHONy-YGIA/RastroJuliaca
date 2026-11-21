# Protocolo experimental reproducible — RastroJuliaca

> Este protocolo describe cómo **medir** si RastroJuliaca mejora la gestión de evidencias frente a la
> práctica habitual. **No contiene resultados**: los resultados solo existen cuando se ejecutan sesiones
> reales y se registran con `registrar_sesion.py`. No se deben inventar ni estimar valores.

## 1. Pregunta y variables

**Pregunta:** ¿Organizar evidencias ciudadanas con RastroJuliaca reduce el tiempo y los errores de un
operador al localizar evidencias relevantes y preparar un informe, frente a carpetas desorganizadas?

| Tipo | Variable | Medición |
|---|---|---|
| Independiente | Escenario | **A**: carpetas desorganizadas · **B**: RastroJuliaca |
| Dependiente | Tiempo para localizar evidencias relevantes | segundos (T1–T4) |
| Dependiente | Errores de asociación | n.º de evidencias asignadas al expediente equivocado |
| Dependiente | Tiempo para generar un informe | segundos (T5) |
| Dependiente | Tareas completadas | sí/no por tarea |
| Dependiente | Exactitud | evidencias relevantes identificadas / esperadas |
| Dependiente | Incidencias de usabilidad | n.º observadas por el facilitador |

## 2. Materiales (ficticios y equivalentes)

`generar_conjuntos.py` crea dos conjuntos **C1** y **C2** con la misma estructura (3 expedientes,
18 evidencias sintéticas, 9 relevantes (3 por expediente), 2 duplicados exactos, 3 con ubicación u hora faltante, mismas
distancias y desfases temporales). Solo cambian detalles superficiales (títulos, zonas, imágenes).

- Escenario A: carpeta `conjuntos/<C>/escenario_a/` (nombres tipo mensajería, expedientes mezclados,
  un `.txt` por imagen con lo que "dijo" quien la envió).
- Escenario B: `servidor_escenario_b.py --conjunto <C>` carga el **mismo** conjunto en una instancia
  aislada de RastroJuliaca (pipeline real de cuarentena, antivirus y hash) en `http://127.0.0.1:8010`.
- Clave de respuestas: `conjuntos/<C>/clave_respuestas.json` (solo para el facilitador).

Ninguna imagen ni dato corresponde a personas, víctimas o hechos reales.

## 3. Participantes

- Voluntarios mayores de edad (p. ej. estudiantes), con consentimiento informado verbal o escrito.
- Se registran solo códigos (P01, P02…); no se registran nombres en los archivos de resultados.
- Tamaño sugerido: al menos 8–12 participantes; con menos de 5 pares completos el análisis se reporta
  solo como descriptivo (el script lo indica).

## 4. Diseño contrabalanceado

Diseño intra-sujeto (cada participante realiza ambos escenarios) con cuadrado latino 2×2 para controlar
efectos de orden y de conjunto:

| Grupo | 1.ª sesión | 2.ª sesión |
|---|---|---|
| G1 | A con C1 | B con C2 |
| G2 | B con C1 | A con C2 |
| G3 | A con C2 | B con C1 |
| G4 | B con C2 | A con C1 |

Asigne participantes a los grupos de forma rotativa (P01→G1, P02→G2, …).

## 5. Tareas (iguales en ambos escenarios)

| Código | Tarea | Esperado |
|---|---|---|
| T1 | Localizar todas las evidencias relevantes del expediente E1 | 3 |
| T2 | Localizar todas las evidencias relevantes del expediente E2 | 3 |
| T3 | Identificar la evidencia más cercana en tiempo al incidente E3 | 1 |
| T4 | Detectar evidencias duplicadas en todo el conjunto | 2 |
| T5 | Preparar un informe de E1 con evidencias, horas y un identificador por evidencia | 3 |

En el escenario A el informe se redacta en un procesador de texto; en el B con la función de informes.
"Relevante" se define por la clave (distancia ≤ 1,5 km y desfase ≤ 90 min, no duplicada).

## 6. Procedimiento por sesión

1. Explicar el objetivo y obtener consentimiento. Aclarar que se evalúa el sistema, no a la persona.
2. Entrenamiento breve idéntico en ambos escenarios (5 min, con un expediente de ejemplo distinto).
3. Iniciar `registrar_sesion.py --participante Pxx --escenario A|B --conjunto C1|C2 --orden AB|BA`.
4. Leer cada tarea en voz alta; cronometrar con Enter al iniciar y al terminar (límite sugerido: 10 min).
5. Puntuar contra la clave: aciertos, errores de asociación e incidencias de usabilidad observadas.
6. Pausa de 5 minutos y repetir con el otro escenario y el otro conjunto.
7. Opcional: cuestionario SUS (System Usability Scale) solo si se aplica su versión validada.

## 7. Registro y análisis

- Los datos se guardan automáticamente en `experiment/resultados/sesiones.csv` (ver
  `plantilla_resultados.csv` para el formato).
- `analizar_resultados.py` calcula estadísticos descriptivos por escenario/tarea y diferencias pareadas
  A−B. Con ≥ 5 pares se sugiere la prueba de Wilcoxon de rangos con signo (no paramétrica).
- Reporte siempre n, medias/medianas, dispersión, tareas no completadas y limitaciones.

## 8. Amenazas a la validez

- Efecto de aprendizaje (mitigado con contrabalanceo y conjuntos equivalentes).
- Muestra pequeña y no aleatoria (voluntarios); resultados no generalizables a operadores reales.
- Conjuntos sintéticos más simples que la realidad.
- El facilitador conoce la hipótesis: usar guion idéntico y puntuar con la clave objetiva.

## 9. Ética

Datos ficticios, participación voluntaria, posibilidad de retirarse sin consecuencias, sin registro de
datos personales de los participantes en los resultados.
