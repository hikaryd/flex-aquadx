# Шрифты — лицензии и атрибуция

Все шрифты в этом каталоге распространяются по [SIL Open Font License 1.1](https://scripts.sil.org/OFL),
совместимой с CC BY-NC-SA 4.0 проекта `flex-aquadx`.

| Файл | Семейство | Автор / правообладатель | Источник |
|---|---|---|---|
| `Inter.ttf` | Inter (variable opsz/wght) | Rasmus Andersson, The Inter Authors | https://github.com/rsms/inter, https://github.com/google/fonts/tree/main/ofl/inter |
| `JetBrainsMono.ttf` | JetBrains Mono (variable wght) | JetBrains s.r.o. | https://github.com/JetBrains/JetBrainsMono, https://github.com/google/fonts/tree/main/ofl/jetbrainsmono |
| `NotoSansJP.ttf` | Noto Sans JP (variable wght) | Google / The Noto Project Authors | https://github.com/notofonts/noto-cjk, https://github.com/google/fonts/tree/main/ofl/notosansjp |

Полный текст OFL 1.1 см. в файлах LICENSE.txt оригинальных репозиториев или
по ссылке: https://scripts.sil.org/OFL.

## Замена шрифтов

При замене файла важно сохранять имя (см. `src/aquadx/render/fonts.py:_FONT_ROLES`)
или добавить новое имя в список приоритетов. Любое изменение содержимого .ttf
меняет `FONT_PACK_HASH` и автоматически инвалидирует кэш отрендеренных PNG.
