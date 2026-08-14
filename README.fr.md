# XNU TCP Watchdog

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | **Français** | [Español](README.es.md) | [한국어](README.ko.md)

Un petit LaunchDaemon macOS qui contourne une défaillance signalée de rebouclage
de l'horloge TCP de XNU sur les Mac fonctionnant sans interruption. Il avertit
avant la limite de `2^32` millisecondes et peut planifier un redémarrage préventif
avant que les temporisateurs TCP ne cessent d'avancer.

> [!WARNING]
> Ce projet est un contournement opérationnel, pas un correctif du noyau. Il peut
> redémarrer automatiquement un Mac. Examinez le code et testez les notifications
> avant d'activer `reboot_enabled`.

## Pourquoi ce projet existe

Certaines versions de XNU conservent l'horloge d'horodatage TCP dans un compteur
32 bits en millisecondes. Après environ 49 jours, 17 heures, 2 minutes et 47
secondes de fonctionnement, le compteur reboucle. Les reproductions et l'analyse
du code source public de XNU indiquent que la protection de mise à jour monotone
peut alors figer `tcp_now`, empêcher le nettoyage de TIME_WAIT et finir par
épuiser les ports TCP éphémères.

- [Reproduction détaillée et analyse du code](https://blog.forevers.love/blog/xnu-tcp-timestamp-overflow-49-day-bug/)
- [Observation indépendante au bout de 49,7 jours](https://zenn.dev/inazumimakoto/articles/mac-tcp-report)
- [Implémentation publique de `calculate_tcp_clock()` par Apple](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/netinet/tcp_subr.c#L3510-L3544)

Apple peut modifier cette implémentation dans de futures versions de macOS.
Vérifiez votre système et le code XNU actuel avant de conclure que ce
contournement est toujours nécessaire.

## Fonctionnement

- S'exécute toutes les cinq minutes comme LaunchDaemon système.
- Journalise l'uptime et les nombres de sockets TIME_WAIT et SYN_SENT.
- Avertit 24 heures puis une heure avant le redémarrage prévu.
- Planifie par défaut un redémarrage préventif une heure avant le rebouclage.
- N'utilise des valeurs TIME_WAIT/SYN_SENT élevées comme signal d'urgence que
  près de la fenêtre de rebouclage.
- Reporte le redémarrage planifié si aucune destination n'accepte l'alerte finale.
- À la limite ou après celle-ci, l'urgence ne dépend pas du succès de la notification.
- Le redémarrage automatique est **désactivé par défaut** et doit être activé explicitement.

## Prérequis

- macOS avec `/usr/bin/python3` (installez les Apple Command Line Tools si nécessaire)
- Un compte administrateur pour l'installation
- Facultatif : bot Telegram, Webhook de bot personnalisé Feishu ou commande de notification

## Installation

```sh
git clone https://github.com/helixzz/xnu-tcp-watchdog.git
cd xnu-tcp-watchdog
sudo ./install.sh
```

Le programme d'installation crée :

- `/usr/local/libexec/xnu-tcp-watchdog.py`
- `/usr/local/etc/xnu-tcp-watchdog.json` (`root:wheel`, mode `0600`)
- `/Library/LaunchDaemons/io.github.xnu-tcp-watchdog.plist`

Un fichier de configuration existant n'est jamais écrasé.

## Configuration des notifications

Modifiez la configuration lisible uniquement par root :

```sh
sudo nano /usr/local/etc/xnu-tcp-watchdog.json
```

Exemple Telegram :

```json
"telegram": {
  "bot_token": "123456:replace-with-your-token",
  "chat_ids": ["123456789"]
}
```

Exemple de bot personnalisé Feishu :

```json
"feishu": {
  "webhook_urls": ["https://open.feishu.cn/open-apis/bot/v2/hook/replace-me"]
}
```

Pour iMessage, OpenClaw, Hermes ou un autre service, indiquez l'exécutable et
ses arguments dans `notification_command`. Le texte est transmis sur l'entrée
standard, sans passer par un shell :

```json
"notification_command": ["/usr/local/bin/my-notify-wrapper"]
```

Conservez les jetons et URL de Webhook uniquement dans la configuration installée.
Ne les versionnez jamais dans Git.

Testez la notification avant d'autoriser les redémarrages :

```sh
sudo /usr/bin/python3 /usr/local/libexec/xnu-tcp-watchdog.py --test-notification
```

Définissez ensuite `"reboot_enabled": true` et rechargez le service :

```sh
sudo launchctl kickstart -k system/io.github.xnu-tcp-watchdog
```

## Vérification et journaux

```sh
sudo launchctl print system/io.github.xnu-tcp-watchdog
tail -20 /var/log/xnu-tcp-watchdog.log
```

`state = not running` est normal entre deux contrôles ; vérifiez le dernier code
de sortie et l'intervalle d'exécution.

## Désinstallation

```sh
sudo ./uninstall.sh
```

La configuration, l'état et les journaux sont conservés afin de faciliter la
récupération. Supprimez-les manuellement seulement lorsqu'ils ne sont plus utiles.

## Sécurité

- Le LaunchDaemon et le programme doivent appartenir à `root:wheel`.
- La configuration est en mode `0600`, car elle peut contenir des identifiants API.
- Les secrets sont lus depuis la configuration, jamais passés en argument ni
  volontairement écrits dans les journaux.
- Les commandes personnalisées s'exécutent en root. N'utilisez qu'un exécutable
  appartenant à root et non modifiable par un utilisateur non privilégié.

## Licence

[MIT](LICENSE)
