# RastroJuliaca — frontend

SPA en React + TypeScript + Vite + Tailwind. Las instrucciones de instalación están en el
[README principal](../README.md).

- `npm run dev`: servidor de desarrollo en http://127.0.0.1:5173 (redirige `/api` al backend en el puerto 8000).
- `npm run build`: verificación de tipos y compilación a `dist/` (el backend sirve esta carpeta).
- `npx playwright test`: pruebas de extremo a extremo; inician un backend aislado con su propia base de datos.
