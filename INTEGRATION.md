# Observed integration / 実機で確認した範囲

Linux ARM64 / Java 21 / Youer **1.21.1 build 920** / NeoForge 21.1.252で、既存サーバーと分離した新規Dockerコンテナ・ディレクトリを使用。実ゲーム、実ダウンロード、非root UID1001で検証した。ホストへのポート公開はしていない。以下はモックやテスト用JARの結果ではない。

## Passed

- Export内の実インストーラで公式JARを取得し、公開SHA-256と一致。
- 実ゲームの `Done (...)! For help, type "help"` 到達。
- イメージ本来のentrypointとEggの`exec bash .youer/start.sh`で起動。
- DockerのSTDIN attachから`list`へ実応答、`stop`でプレイヤー/ワールド保存とexit0。
- 同じ世界identityを保って再起動し、再度Ready。
- 別のSIGTERM試験でも新しい保存完了ログとexit0。強制killは不使用。
- 停止後に、build920を指定してExport内の同じインストーラを再実行しexit0。
- world、properties、EULA、config、mods/plugins/customの非実行sentinelを含む**58ファイル・39,058,807 bytes**が再インストール前後で完全一致。
- 再インストール後も非root所有権を確認して実起動し、Ready。その後STDINから正常停止しexit0。
- Java再起動によるpropertiesのbyte差はコメント/並びの差で、キー/値のsemantic比較は一致。

## Tested payload identities

- Embedded install script SHA-256: `df1e9a2a928fd67098475cc834e00d912576cb0cafc8ebd5d17b562c95d63812`
- Runtime SHA-256: `f7042d63e61ca5db33465d08315a66ed9ffd4667feab4be9f29bdaced87ff6aa`
- Youer JAR SHA-256: `ccb6e44668919d6a5a69aeffbe3fefb71f7c9c6127cc01ea1febc3f20f32fca1`

公開用Eggには固定のEgg UUIDと更新URLを追加しているが、上記のインストーラ/起動スクリプトのbyte列はテスト版と一致する。JARやテスト世界は配布しない。

## Limits / 未検証

- 実クライアント参加、個別mod/plugin機能、長期稼働、複数人負荷、他Minecraft/Youer版、AMD64実ゲームは未検証。ARM64/x64のCIはオフラインコード試験であり、AMD64ゲーム起動試験ではない。
- EULAへの同意はこの隔離テストについてユーザーが明示承認。配布インストーラは初回`eula=false`を作成し、既存EULAを保持する。EULA=false状態でのゲーム本体の起動拒否自体は別途未検証。
- mods/pluginsの保存確認は非実行sentinelであり、それらのロード互換性を証明しない。
- Dockerによる実起動/保存/停止試験と、実Panel管理サーバーの全ライフサイクルは別。Wings native properties parserによるport変更は別経路。
- バックアップ復元、ディスクフル中のソフトウェア全体のtransactional rollback、任意の同時ファイル改変への耐性を保証するものではない。

通常CIはゲーム取得・ライセンス同意を行わず、Python 3.11/3.13 × native Linux ARM64/x64でオフラインunit/build/shell検証を行う。保守手順は[PUBLISHING.md](PUBLISHING.md)。
