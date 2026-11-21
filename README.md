# RastroJuliaca

**Sistema colaborativo de gestión y revisión de evidencias digitales para incidentes ciudadanos.**
Juliaca, Puno, Perú · Prototipo (MVP) para concurso universitario y demostraciones controladas.

> RastroJuliaca **no reemplaza** a la Policía Nacional del Perú, **no certifica** denuncias, **no determina**
> culpabilidad y **no garantiza** la resolución de incidentes. La publicación de una ficha no significa que
> los hechos hayan sido verificados por una autoridad. El MVP **no está autorizado** para procesar
> incidentes reales y no declara cumplimiento legal certificado. Todos los datos de demostración son ficticios.

## Qué hace

1. Un ciudadano se registra, crea un expediente (11 categorías con campos dinámicos) y adjunta documentación.
2. El expediente permanece **privado y pendiente**; se asigna automáticamente a un revisor habilitado.
3. El revisor examina la documentación y **aprueba, rechaza o solicita correcciones** con motivo.
4. Si la política lo permite, publica una **ficha generalizada** (minimizada) y habilita aportaciones.
5. Otro ciudadano aporta video, fotografía, documento o información escrita.
6. Cada archivo pasa por **cuarentena → antivirus real → validación de formato → hash SHA-256 → copia
   segura de reproducción**; si no hay antivirus, queda bloqueado.
7. El revisor clasifica, observa, ordena por **cercanía geográfica (Haversine) y temporal**, revisa la
   **línea de tiempo** y genera un **informe** exportable (JSON y PDF) con huella de integridad.

## Requisitos (Windows 11, sin Docker)

| Herramienta | Versión probada | Obligatoria |
|---|---|---|
| Python | 3.12.x | Sí — recomendado el instalador oficial de python.org (firmado). También sirve `uv python install 3.12` |
| Node.js / npm | 20+ (probado 26.13.0 / 11.20.0) | Sí |
| FFmpeg / FFprobe | probado 9.0.2 | Para videos (`winget install Gyan.FFmpeg`); sin ellos los videos quedan bloqueados |
| Microsoft Defender (MpCmdRun) | integrado en Windows | Para análisis antivirus; alternativa: ClamAV |
| PowerShell | Windows PowerShell 5.1 o PowerShell 7 | Sí |

## Instalación desde cero (Windows 11)

### 1. Permitir los scripts del proyecto (sin desactivar protecciones)

Windows bloquea por defecto todos los scripts `.ps1`. La configuración recomendada por Microsoft para
usuarios es `RemoteSigned`: permite scripts creados localmente y sigue exigiendo firma a los descargados.
Solo afecta a su usuario y no desactiva el antivirus ni el Control inteligente de aplicaciones.

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Si recibió el proyecto como **ZIP descargado de internet**, Windows marca sus archivos como
descargados y `RemoteSigned` los seguirá bloqueando. Tras **revisar** que el ZIP proviene de su equipo,
desbloquee solo los scripts del proyecto (en la carpeta del proyecto):

```powershell
Get-ChildItem .\scripts\*.ps1 | Unblock-File
```

Si prefiere no cambiar ninguna configuración, siga la [instalación manual](#instalación-manual-sin-scripts).

### 2. Instalar y ejecutar

```powershell
.\scripts\setup.ps1
```

```powershell
.\scripts\start.ps1
```

Abra **http://127.0.0.1:8000**. El servidor escucha solo en `127.0.0.1` (no se expone a la red).

`setup.ps1` es seguro de repetir: reutiliza el entorno Python que funcione, **no borra** entornos ni la
base de datos existente, y solo carga los datos ficticios si la base está vacía.

Opciones:

```powershell
.\scripts\setup.ps1 -WithE2E
```

```powershell
.\scripts\start.ps1 -Dev
```

- `-WithE2E`: descarga Chromium para las pruebas Playwright.
- `-Dev`: Vite (http://127.0.0.1:5173) + backend con recarga automática.
- `-VenvDir <nombre>`: crea/usa un entorno virtual con otro nombre dentro de `backend/`.
- `-Reset`: **borra** la base de datos y los archivos de `data/` y vuelve a sembrar (pide escribir `SI`).

### Si Windows bloquea `python.exe`

Algunos equipos (Control inteligente de aplicaciones, antivirus o políticas de la organización)
impiden ejecutar el `python.exe` de ciertos entornos virtuales, por ejemplo los creados con `uv venv`.
Los scripts **prueban** cada entorno (`backend\.venv`, `backend\.venv_alt`, `backend\.venv-rj` o
cualquier otro con `pyvenv.cfg`) y usan el primero que realmente se ejecuta. Si ninguno funciona,
`setup.ps1` crea uno nuevo con `python -m venv` en un nombre libre, sin borrar el bloqueado.
Si también se bloquea, instale Python 3.12 desde python.org y ejecute:

```powershell
.\scripts\setup.ps1 -VenvDir .venv-python-org
```

Para ejecutar scripts de Python del proyecto con el entorno detectado:

```powershell
.\scripts\py.ps1 experiment\generar_conjuntos.py
```

### Instalación manual (sin scripts)

Equivalente a `setup.ps1` + `start.ps1`, ejecutando cada comando en PowerShell desde la carpeta del proyecto
(sustituya `py -3.12` por la ruta de su Python 3.12 si no tiene el lanzador `py`):

```powershell
py -3.12 -m venv backend\.venv-rj
```
```powershell
backend\.venv-rj\Scripts\python.exe -m pip install -e "backend[dev]"
```
```powershell
Copy-Item .env.example .env
```
Edite `.env` y reemplace `RJ_SECRET_KEY` por un valor aleatorio largo (por ejemplo, la salida de
`backend\.venv-rj\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"`).
```powershell
cd frontend; npm ci; npm run build; cd ..
```
```powershell
cd backend; .\.venv-rj\Scripts\python.exe -m app.seed
```
```powershell
.\.venv-rj\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Cuentas ficticias de demostración

Contraseña común: `Demo-Juliaca-2026`. Es **pública y ficticia**: sirve solo para demostraciones locales.
Con `RJ_ENV=production` el servidor se niega a arrancar en modo demostración.

| Rol | Correo | Notas |
|---|---|---|
| Administrador | `admin@rastrojuliaca.test` | Sin acceso al contenido de expedientes |
| Revisor 1 | `revisor1@rastrojuliaca.test` | Habilitado para RESTRINGIDO e INSTITUCIONAL |
| Revisor 2 | `revisor2@rastrojuliaca.test` | Habilitado para RESTRINGIDO |
| Denunciante 1 | `denunciante1@rastrojuliaca.test` | |
| Denunciante 2 | `denunciante2@rastrojuliaca.test` | |
| Colaboradores | `colaborador1..3@rastrojuliaca.test` | |

Expedientes ficticios incluidos: robo vehicular (aprobado, publicado, con 5 aportaciones, una duplicada),
accidente de tránsito (publicado), objeto extraviado (pendiente), daños materiales (corrección solicitada),
incidente de seguridad ciudadana (aprobado sin publicar), persona adulta no ubicada (RESTRINGIDO,
pendiente de segunda aprobación), robo de celular (rechazado), caso institucional (privado) y un borrador.
Las imágenes, el video y los PDF son **sintéticos** generados por `app/seed.py`.

### Guion sugerido para la demostración

1. Portada → Explorar → ficha pública RJ-…-00001 (solo datos autorizados).
2. Ingresar como **Revisor 1** → expediente de mototaxi → pestañas *Evidencias* (orden por cercanía,
   duplicado exacto, "datos insuficientes"), *Línea de tiempo*, *Informes* → exportar JSON/PDF.
3. Expediente "Vandalismo recurrente" → *Publicación* → publicar ficha y habilitar aportaciones.
4. Ingresar como **Colaborador 1** → aportar una foto al expediente recién publicado → ver estado.
5. Ingresar como **Revisor 2** → expediente de persona adulta → confirmar la segunda aprobación.
6. Ingresar como **Administrador** → auditoría (descargas y exportaciones registradas), categorías
   (intentar bajar la sensibilidad de "Menor de edad": se rechaza), conservación y derechos del titular.

## Pruebas

```powershell
.\scripts\test.ps1
```

Ejecuta pytest (backend), la verificación de tipos/compilación del frontend y Playwright (flujo completo
en escritorio + pruebas móviles). La salida queda en `docs/evidencias/`. Resultados verificados:
[`docs/resultados.md`](docs/resultados.md).

## Estructura

```
backend/            FastAPI + SQLAlchemy + Alembic
  app/routers/      auth, public, cases, contributions, review, reports, files, account, admin
  app/services/     forms (esquemas dinámicos), policies, pipeline, storage, antivirus, media, geo
  alembic/          migraciones
  tests/            pytest (incluye integración real con Defender y FFmpeg)
  e2e_server.py     servidor aislado para Playwright
frontend/           React + TypeScript + Vite + Tailwind + componentes estilo shadcn/ui
  src/pages/        public, auth, reporter, contributor, reviewer, admin
  e2e/              Playwright
scripts/            setup.ps1, start.ps1, test.ps1
docs/               documentación académica, resultados, seguridad
experiment/         protocolo experimental y herramientas de medición
data/               (generado) base de datos, almacenamiento privado, medios sintéticos
```

## Tecnologías y justificación

- **FastAPI + SQLAlchemy 2 + Alembic**: API tipada, ORM portable (SQLite → PostgreSQL), migraciones versionadas.
- **argon2-cffi**: hash de contraseñas Argon2id.
- **Pillow**: validación y re-codificación de imágenes sin metadatos (EXIF/GPS).
- **reportlab**: exportación PDF de informes.
- **React + React Router + React Hook Form + Zod**: formularios por pasos con validación generada desde el
  mismo esquema de campos que valida el backend.
- **Tailwind CSS + radix-ui (patrón shadcn/ui) + Lucide + Inter (local)**: UI accesible sin CDN externos.
- **Playwright + pytest**: pruebas de extremo a extremo y de API.

Nota: los componentes de interfaz siguen el patrón de shadcn/ui (código propio sobre Radix y
`class-variance-authority`) escrito directamente en `frontend/src/components/ui/`, sin ejecutar su CLI.

## Configuración

Variables `RJ_*` documentadas en [`.env.example`](.env.example). `setup.ps1` crea `.env` con un secreto
aleatorio. En `RJ_ENV=production` el servidor se niega a iniciar con el secreto por defecto.

PostgreSQL: defina `RJ_DATABASE_URL=postgresql+psycopg://…`, instale el controlador (`psycopg[binary]`) y
ejecute `python -m app.seed`. Esta configuración **no se ha probado** en este MVP.

## Seguridad y privacidad

Resumen de controles en [`docs/seguridad.md`](docs/seguridad.md). Ningún sistema es completamente seguro;
este prototipo no ha sido auditado externamente.

## Documentación académica y evaluación

- [`docs/documentacion-academica.md`](docs/documentacion-academica.md): problema, objetivos, alcance,
  requisitos, diagramas (arquitectura, ER, casos de uso), matriz de permisos, metodología, limitaciones.
- [`experiment/protocolo.md`](experiment/protocolo.md): protocolo A/B contrabalanceado y herramientas
  (`generar_conjuntos.py`, `servidor_escenario_b.py`, `registrar_sesion.py`, `analizar_resultados.py`).
