# Fase 3 - Reorganización incremental de DJPlus

## Objetivo
Reordenar la estructura del proyecto sin romper la aplicación, moviendo un archivo por vez y verificando que siga funcionando antes de continuar.

## Regla de trabajo
1. Crear una rama de trabajo para cambios grandes si hace falta.
2. Implementar una sola característica por vez.
3. Probar que funcione.
4. Hacer commit.
5. Continuar con la siguiente característica.

## Orden propuesto para la reorganización
1. Mover database.py a app/database/database.py
2. Ajustar imports y verificar arranque.
3. Mover models.py a app/database/models.py o app/models/models.py
4. Ajustar imports y verificar.
5. Reorganizar la UI paso a paso: views, widgets, dialogs, etc.
6. Introducir TrackRepository, TrackTableModel y QTableView.

## Criterio de aceptación
- La app sigue arrancando.
- Los imports funcionan correctamente.
- Cada cambio queda validado con una prueba o ejecución mínima.
