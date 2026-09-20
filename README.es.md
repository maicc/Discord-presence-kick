# KickPresence

[English](README.md) | [Español](README.es.md)

Presencia de Discord (Rich Presence) que muestra automáticamente cuando tu canal de Kick está en vivo.

- Miniatura real del stream como imagen grande
- Título del stream, categoría y cantidad de espectadores
- Cronómetro con el tiempo en vivo
- Botón **Ver** que lleva al canal (sólo lo ven los demás, no vos)
- Título e imagen clickeables
- Ícono en la bandeja del sistema, con avisos al empezar y terminar el stream
- Ventana de configuración para elegir el canal, sin editar archivos a mano
- Una sola instancia: si ya está abierto, no se abre dos veces

## Requisitos

- Windows 10/11
- Discord para escritorio abierto (con la app cerrada no se publica la presencia)
- Para compilar: Python 3.12 o superior

## Uso

1. Ejecutá `KickPresence.exe`
2. La primera vez se abre la ventana de configuración: escribí tu canal de Kick (podés pegar `kick.com/tu-canal`), dale a **Verificar** y después a **Guardar**
3. Queda el ícono en la bandeja del sistema. Cuando arranques el stream, la presencia se publica sola

Para cambiar de canal: clic derecho en el ícono de la bandeja → **Configurar canal...**

La configuración se guarda en `%APPDATA%\KickPresence\config.json`. Si dejás un `config.json` junto al `.exe`, se usa ese (modo portable).

## Compilar

```powershell
.\compilar.bat
```

o

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Genera `dist\KickPresence.exe`. El script crea el entorno virtual, instala las dependencias, regenera el ícono desde `assets\rika-icon.jpg`, cierra la app si está abierta y compila.

## Tu propia app de Discord

El `.exe` incluye un Application ID por defecto para que funcione sin configurar nada. Si querés usar tu propia app (para cambiar el nombre o los assets):

1. Creá una aplicación en https://discord.com/developers/applications
2. Copiá el **Application ID** en `discord_client_id` dentro de `config.json`
3. En *Rich Presence → Art Assets* subí las imágenes `kick-icon` (imagen grande de reserva) y `live_badge` (badge chico), mínimo 512x512, cuadradas

El nombre de la app es el que aparece en la actividad ("Jugando a ...").

## Configuración

| Clave | Descripción |
|---|---|
| `discord_client_id` | Application ID de Discord |
| `kick_channels` | Canales de Kick a monitorear (gana el primero que esté en vivo) |
| `poll_interval_seconds` | Cada cuánto se consulta la API (mínimo 15) |
| `refresh_interval_seconds` | Cada cuánto se reenvía la presencia |
| `show_viewers` / `show_category` / `show_elapsed_time` | Qué datos mostrar |
| `notify_on_change` | Avisos al empezar y terminar el stream |
| `use_stream_thumbnail` | Usar la miniatura real del stream |
| `clickable_urls` | Título e imagen clickeables |
| `status_display_type` | `name`, `state` o `details`: qué texto se ve en la lista de miembros |
| `large_image_live` / `small_image_live` | Nombres de los assets en Discord |
| `button_label` | Texto del botón |

## Estructura

| Archivo | Rol |
|---|---|
| `main.py` | Punto de entrada, monitoreo, bandeja del sistema y CLI |
| `kick_api.py` | Cliente de la API de Kick |
| `presence.py` | Discord Rich Presence: reconexión, assets, manejo de errores |
| `settings_ui.py` | Ventana de configuración (tkinter) |
| `config.py` | Carga, validación y guardado de la configuración |
| `icon.py` | Generación del `.ico` y del ícono de la bandeja |
| `build.ps1` / `compilar.bat` | Compilación con PyInstaller |
| `instalar-autostart.ps1` | Inicio automático con Windows (`-Quitar` para desactivarlo) |

## Modos de línea de comandos

| Comando | Qué hace |
|---|---|
| `--setup` | Abre la ventana de configuración y sale |
| `--once` | Consulta los canales una vez y muestra el resultado |
| `--test` | Envía una presencia de prueba a Discord |
| `--dry-run` | Monitorea sin publicar nada en Discord |
| `--console` | Corre en modo consola, sin bandeja |
| `--tray` | Fuerza el modo bandeja |
| `-v`, `--verbose` | Log detallado |

## Notas

- El botón **Ver** no aparece en tu propio perfil: es una limitación de Discord, sólo lo ven los demás usuarios
- Si ya hay una instancia corriendo, la segunda muestra un aviso y se cierra
- Las imágenes de `assets/` pertenecen a sus respectivos autores; el código es libre de usar y modificar
