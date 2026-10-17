# Youer — configurable Pelican Egg

[![CI](https://github.com/keimag-dev/pelican-egg-youer/actions/workflows/ci.yml/badge.svg)](https://github.com/keimag-dev/pelican-egg-youer/actions/workflows/ci.yml)

**Pelican → Eggs → Import from URL:**

```text
https://github.com/keimag-dev/pelican-egg-youer/releases/latest/download/egg-youer.json
```

Release assets include `SHA256SUMS`. The same stable URL is embedded as the Egg's update URL. For pinned deployments, use the version-specific release URL instead. See [PUBLISHING.md](PUBLISHING.md) for CI and release maintenance.

Java 21 / Minecraft 1.21.1 用の汎用 Youer Egg。NeoForge と Paper/Purpur API のハイブリッドです。mod・plugin・modpack は同梱しません。特定の mod や既存サーバーへの依存はありません。

`egg-youer.json` は **PLCN_v3 の単体 import ファイル**です。installer と Bash runtime のソースを内包し、このリポジトリを実行時に取得しません。公開JSONには上記のstable release URLを更新先として設定しています。ビルダー単体の既定値は `null` なので、再生成時は後述の `--update-url` を指定してください。同じUUIDのEggへの再インポートは更新になります。独立した別Eggとしてforkする場合はUUIDと更新URLを変更してください。

## Import / 初回起動

1. 現行 Pelican で `egg-youer.json` を import。image は **Java 21** を選択。
2. primary allocation に Minecraft TCP port を割り当て、RAM・disk・CPU を設定します。目安は RAM 6144 MiB 以上、disk 10 GiB 以上。mod 構成に応じて増やしてください。query を有効にする場合は同じ port の UDP も別途管理者が確保します。Egg は firewall や公開設定を変更しません。
3. 下表の install 用変数を設定して install。`latest` は **指定 Minecraft version 内の最大 numeric build** を選びます。Minecraft version を勝手に変更しません。再現性が必要なら build を numeric で固定してください。
4. [Minecraft EULA](https://www.minecraft.net/eula) を読み、同意する本人が Pelican の EULA 確認機能または `eula.txt` を使って明示的に同意します。installer は初回 `eula=false` を作成するだけで、自動同意しません。
5. 起動後、console の通常 Minecraft command を使用できます。停止は `stop`。Bash は `exec java` するため stdin・signal・終了コードを中継プロセスが奪いません。

### 変数と反映時点

**I** = install / reinstall で JAR を取得するとき。**F** = `server.properties` が存在しない初回だけ。**S** = 毎回 start。
全変数は user-viewable / user-editable。列挙値は Pelican の `in:` rule により UI 選択肢として提供します。

| UI field / environment | Default | Supported values | Applies |
|---|---|---|---|
| Minecraft Version / `MINECRAFT_VERSION` | `1.21.1` | `1.x` / `1.x.y` numeric、公式 API に実在すること。Java 21 と検証済みなのは 1.21.1 | I |
| Youer Build / `YOUER_BUILD` | `latest` | `latest` または正の整数、先頭ゼロなし。その version の API に完全一致する build | I |
| Server Jar File / `SERVER_JARFILE` | `server.jar` | 英数字開始、英数字・`_ . -`、末尾 `.jar`、最大124文字。path や shell fragment 不可 | I, S |
| Server Name / `SERVER_NAME` | `Youer Server` | 1–256 printable characters、改行不可。`server-name` はすべての Minecraft client に表示されるとは限りません | F |
| Message of the Day / `MOTD` | `A Youer Minecraft Server` | 1–256 printable characters、改行不可。Unicode / literal backslash は properties 用に escape | F |
| Maximum Players / `MAX_PLAYERS` | `20` | 1–10000 integer | F |
| Game Mode / `GAMEMODE` | `survival` | `survival`, `creative`, `adventure`, `spectator` | F |
| Difficulty / `DIFFICULTY` | `normal` | `peaceful`, `easy`, `normal`, `hard` | F |
| Online Mode / `ONLINE_MODE` | `true` | `true`, `false`。通常は true を維持 | F |
| Whitelist Enabled / `WHITELIST` | `false` | `true`, `false`。identity を追加しません | F |
| View Distance / `VIEW_DISTANCE` | `10` | 2–32 integer | F |
| World Name / `LEVEL_NAME` | `world` | 英数字開始、英数字・`_ -`、最大64文字 | F |
| Java Heap (MiB) / `HEAP_MB` | `0` | `0` = automatic、または512–1048576 integer | S |
| Native Memory Headroom (MiB) / `NATIVE_HEADROOM_MB` | `1024` | 256–1048576 integer | S |
| Unlimited Allocation Heap (MiB) / `UNLIMITED_HEAP_MB` | `4096` | 512–1048576 integer | S |

整数は先頭ゼロなしの十進表記。F の値を後から変えても、既存設定を保護するため reinstall では反映しません。既存サーバーの gameplay 設定は `server.properties` を編集して restart してください。`SERVER_JARFILE` を変更したら、その名前の JAR を install してから start します。

Pelican `config.files` は **毎回 start 時に** `server-ip` を空にし、`server-port` / `query.port` を primary allocation port に設定します。それ以外の gameplay 項目は startup に強制しません。Panel が行う port 設定と installer の preservation は別の処理です。

### Memory policy

- `SERVER_MEMORY > 0`: heap auto = allocation − native headroom。明示 heap もこの上限内でなければ **起動を拒否**。利用可能 heap が512 MiB 未満でも拒否します。
- `SERVER_MEMORY=0`（unlimited）: auto heap は `UNLIMITED_HEAP_MB`、明示 heap は `HEAP_MB`。無制限の `-Xmx` は作りません。
- 初期 heap は128 MiB。6144 MiB allocation と1024 MiB reserveなら `-Xmx5120M`。reserve は native memory の保証・制限ではなく、負荷に応じた調整が必要です。host RAM / container limit は別に確保します。
- arbitrary JVM flags や direct download URL は意図的に公開しません。shell expansion / eval / checksum を回避した不明な JAR の取得を許しません。

## Reinstall / upgrade の安全性

**先に停止してバックアップ**。Minecraft / loader の変更は world や mod の互換性を破壊し得ます。downgrade はとくに危険です。

- 選択された JAR だけを同一 filesystem の一時ファイルへ download。公式 API の SHA-256 と JAR manifest を確認してから atomic replace。失敗時は旧 JAR を保持、一時ファイルを削除。
- `server.properties`, `eula.txt`, worlds, mods, plugins, whitelist / ops / bans、任意の user file を installer は上書き・削除しません。EULA の既存 true/false も維持します。
- installer 管理領域は `.youer/start.sh` と `.youer/install.json`。runtime を手編集した場合や未所有の `.youer` がある場合は、reinstall を拒否して衝突を通知します。変更をバックアップして `.youer` を退避してからやり直してください。
- JAR / config / helper の symlink や非通常ファイルは拒否します。停止中の信頼できる volume を対象とし、同時 install や実行中の volume 書き換えはサポートしません。
- build 不在・不正値・空 metadata・checksum 不足/不一致・HTTP/JSON error は失敗。別 version や別 build への fallback はありません。
- atomicity は JAR ファイル単位です。JAR 検証後の disk-full 等による helper 書き込み失敗まで含めた複数ファイル transaction ではありません。修復して reinstall してください。
- **実行する上流ソフトウェア自身の動作は別**です。Youer は起動時に libraries / config を生成し、既定の incompatible-mod cleanup 機能を持ちます。mod 追加前に upstream 設定・互換性を確認しバックアップしてください。Egg がユーザーの既存 Youer config を勝手に変更することはありません。

## Images / dependencies

- Runtime: `ghcr.io/pelican-eggs/yolks:java_21`。Linux ARM64 / AMD64 向け Java image。Bash と Java 21、通常の非rootユーザーを使用。**runtime Python 不要**。image tag は mutable なので、厳密な再現には管理者が検証済み multiarch digest を別途固定してください。
- Installer: official Docker `debian:bookworm-slim`。使い捨て installer container 内だけで `apt-get install --no-install-recommends python3 ca-certificates`。host package は変更しません。installer 自体に Java は不要です。
- Network: Debian apt repositories、`api.mohistmc.com` の HTTPS。ゲーム初回起動では Youer / NeoForge の library download 先への接続も必要です。HTTP timeout は60秒/read、JAR streaming は15分/1GiB、metadata は4MiB で制限します。これは**ゲーム稼働時間の制限ではありません**。

## Build / test

Python 3.11+ standard library と Bash があれば実行できます。pip 不要。

```sh
python -W error -m unittest discover -s tests -v
python build_egg.py --update-url https://github.com/keimag-dev/pelican-egg-youer/releases/latest/download/egg-youer.json
python -W error scripts/publication_guard.py --verify-build
bash -n runtime.sh
```

独立 repository へ `youer/` の中身を移した場合は `python build_egg.py` と `python -m unittest discover -s tests -v`。実在する公開 artifact URL を設定する場合は `python build_egg.py --update-url "$PUBLISHED_EGG_URL"`。既定は null で、exporter は URL の公開可否を推測しません。CI では同じ option を使って再生成してください。

## Public sources / live contract

- [Youer official repository / Java 21](https://github.com/MohistMC/Youer)
- [`GET /project/youer/1.21.1/builds`](https://api.mohistmc.com/project/youer/1.21.1/builds): top-level array。各 entry の `id` は positive integer、`file_sha256` は64桁 hexadecimal。`latest` という文字列を download endpoint に渡しません。
- [`GET /project/youer/1.21.1/builds/920/download`](https://api.mohistmc.com/project/youer/1.21.1/builds/920/download): JAR binary。
- [Current official Paper PLCN_v3 schema](https://raw.githubusercontent.com/pelican-eggs/minecraft/main/java/paper/egg-paper.yaml)
- [Upstream launcher at build920 commit](https://github.com/MohistMC/Youer/blob/e315863237815205021e0255f3057cca22eb28a0/youerlauncher/src/main/java/com/mohistmc/launcher/youer/Main.java)

2026-10-17 live check: 595 advertised builds、max920、SHA-256 `ccb6e44668919d6a5a69aeffbe3fefb71f7c9c6127cc01ea1febc3f20f32fca1`。download HEAD は HTTP200 /128324527 bytes。既存の同 build JAR を read-only hash 照合し一致を確認しました。JAR や game assets は配布物に含めません。詳細・未実施の platform smoke gate は [TESTING.md](TESTING.md)。

## License

このディレクトリの自作コードは MIT ([LICENSE](LICENSE))。Youer / Minecraft / NeoForge / plugins / mods / Docker images の著作権・ライセンスは各 upstream に従います。Egg の MIT は取得する game binary の再配布許可ではありません。
