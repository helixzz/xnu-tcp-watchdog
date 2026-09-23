# XNU TCP Watchdog

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Français](README.fr.md) | **Español** | [한국어](README.ko.md)

Un pequeño LaunchDaemon para macOS que mitiga un fallo documentado de desbordamiento
del reloj TCP de XNU en Mac con largos periodos de actividad. Avisa antes del límite
de `2^32` milisegundos y puede programar un reinicio preventivo antes de que los
temporizadores TCP dejen de avanzar.

> [!WARNING]
> Este proyecto es una solución operativa provisional, no una corrección del kernel.
> Puede reiniciar un Mac automáticamente. Revisa el código y prueba las notificaciones
> antes de activar `reboot_enabled`.

> [!IMPORTANT]
> Antes de instalar, consulta las [versiones y comprobaciones (en inglés)](README.md#do-i-need-this-tool).
> El código publicado de macOS 26.0–26.3 contiene este defecto; el de 26.4 y 26.5 ya lo corrige.
> Se espera que macOS 27 herede la corrección, pero aquí no se ha verificado de forma independiente.
> La herramienta no detecta los sistemas corregidos. Tras actualizar a un kernel corregido,
> desinstálala o establece `reboot_enabled` en `false`.

## Por qué existe

Algunas versiones de XNU mantienen el reloj de marcas de tiempo TCP en un contador
de 32 bits medido en milisegundos. Tras unos 49 días, 17 horas, 2 minutos y 47
segundos de actividad, el contador vuelve a cero. Las reproducciones y el análisis
del código público de XNU indican que la protección de actualización monótona puede
dejar `tcp_now` congelado, impedir la limpieza de TIME_WAIT y agotar finalmente los
puertos TCP efímeros.

- [Reproducción detallada y análisis del código](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [Observación independiente a los 49,7 días](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Implementación corregida de Apple: XNU 12377.101.15](https://github.com/apple-oss-distributions/xnu/blob/xnu-12377.101.15/bsd/netinet/tcp_subr.c#L3906)

Usa `sw_vers` y `uname -v` para comparar tu sistema y el kernel en ejecución con
la tabla enlazada. Verificar el código fuente no equivale a una prueba prolongada
en hardware real. Consulta la etiqueta de versión correspondiente, no la antigua
rama `main`.

## Funcionamiento

- Se ejecuta cada cinco minutos como LaunchDaemon del sistema.
- Registra el uptime y los recuentos TIME_WAIT y SYN_SENT.
- Avisa 24 horas y una hora antes del reinicio previsto.
- De forma predeterminada, programa un reinicio una hora antes del desbordamiento.
- Solo usa valores altos de TIME_WAIT/SYN_SENT como señal de emergencia cerca de esa ventana.
- Aplaza el reinicio previsto si ningún destino acepta la alerta final.
- Al alcanzar o superar el límite, la emergencia no depende del éxito de la notificación.
- El reinicio automático está **desactivado de forma predeterminada** y debe habilitarse expresamente.

## Requisitos

- macOS con `/usr/bin/python3` (instala Apple Command Line Tools si es necesario)
- Una cuenta administradora para instalar
- Opcional: bot de Telegram, Webhook de bot personalizado de Feishu o comando propio

## Instalación

```sh
git clone https://github.com/helixzz/xnu-tcp-watchdog.git
cd xnu-tcp-watchdog
sudo ./install.sh
```

El instalador crea:

- `/usr/local/libexec/xnu-tcp-watchdog.py`
- `/usr/local/etc/xnu-tcp-watchdog.json` (`root:wheel`, modo `0600`)
- `/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist`

Nunca sobrescribe una configuración existente.

## Configurar notificaciones

Edita la configuración legible únicamente por root:

```sh
sudo nano /usr/local/etc/xnu-tcp-watchdog.json
```

Ejemplo de Telegram:

```json
"telegram": {
  "bot_token": "123456:replace-with-your-token",
  "chat_ids": ["123456789"]
}
```

Ejemplo de bot personalizado de Feishu:

```json
"feishu": {
  "webhook_urls": ["https://open.feishu.cn/open-apis/bot/v2/hook/replace-me"]
}
```

Para iMessage, OpenClaw, Hermes u otro sistema, indica el ejecutable y sus argumentos
en `notification_command`. El texto de la alerta se pasa por la entrada estándar,
sin usar un shell:

```json
"notification_command": ["/usr/local/bin/my-notify-wrapper"]
```

Guarda los tokens y las URL de Webhook únicamente en la configuración instalada.
Nunca los incluyas en un commit de Git.

Prueba la entrega antes de habilitar los reinicios:

```sh
sudo /usr/bin/python3 /usr/local/libexec/xnu-tcp-watchdog.py --test-notification
```

Después, establece `"reboot_enabled": true` y recarga el servicio:

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

## Verificación y registros

```sh
sudo launchctl print system/io.github.xnu-tcp-watchdog
tail -20 /var/log/xnu-tcp-watchdog.log
```

`state = not running` es normal entre comprobaciones; revisa el último código de
salida y el intervalo de ejecución.

## Desinstalación

```sh
sudo ./uninstall.sh
```

La configuración, el estado y los registros se conservan para facilitar la
recuperación. Elimínalos manualmente solo cuando ya no sean necesarios.

## Seguridad

- El LaunchDaemon y el programa deben pertenecer a `root:wheel`.
- La configuración usa el modo `0600` porque puede contener credenciales de API.
- Los secretos se leen de la configuración; no se pasan como argumentos ni se
  escriben intencionadamente en los registros.
- Los comandos personalizados se ejecutan como root. Usa solo un ejecutable propiedad
  de root que los usuarios sin privilegios no puedan modificar.

## Licencia

[MIT](LICENSE)
