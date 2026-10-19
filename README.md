# もこ SNS自動運用 / Mac実行基盤

このリポジトリで指示・手順・検証・報告を管理し、制作と実行は本人のMacで行います。
現在は **フェーズ1：下書き専用** です。公開投稿用APIは実装していません。
設定を変更するだけで公開できる構成にはしていません。

- [初期調査・実装報告](docs/reports/2026-10-19-initial.md)
- [クラウド側Codexへの引き継ぎ](docs/CLOUD_HANDOFF.md)
- [3媒体接続後の初回下書き](docs/reports/2026-10-19-first-drafts.md)
- [Threads接続・実測結果](docs/reports/2026-10-19-threads-connection.md)
- [操作手順](docs/OPERATIONS.md)
- [公式API調査](docs/API_RESEARCH.md)
- [構成・安全制御](docs/ARCHITECTURE.md)
- [次の実装](docs/ROADMAP.md)

## 対象

|媒体|投稿先|確認状況|
|---|---|---|
|Instagram|https://www.instagram.com/mocochan85/|Keychain保存・本人API ID照合済み。既存リール3本の6指標を実取得|
|Threads|https://www.threads.com/@mocochan85|Keychain保存・本人API ID照合済み。既存投稿3件の6指標を実取得|
|YouTube Shorts|https://www.youtube.com/@MOCOchannel/shorts|本人所有・OAuthチャンネルID照合済み。既存Shorts 3本の実測取得済み|

## ローカルで試す

Python 3.9以上。外部Pythonパッケージは不要です。動画生成にはmacOS、Swift/AppKit、Kyoko音声、`/usr/local/bin/ffmpeg` と `ffprobe` が必要です。
Mac固有の描画処理はクラウド上では実行しません。

```sh
python3 scripts/doctor.py
python3 -m unittest discover -s tests -v
python3 -m moco draft --platform youtube --topic 'AI動画の企画を一つに絞る'
python3 -m moco render ここを返された管理IDに置換
python3 -m moco status
```

制作物・データベース・認証に関係するローカル設定は `var/`、`config/local.json` に置き、Git管理から除外します。実際の秘密値はmacOS Keychainで扱います。
テスト用の架空の数字はテスト内に限定し、運用データへ混ぜません。

## GitHubからMacへ

本人の数値GitHub ID、Issueの作者・最終編集者、ラベル、定型JSON、作成コマンドUUIDを検証します。
許可する指示は `draft` / `render` / `status` / `analyze` / `stop` だけです。
任意コマンド、公開、承認、再開、認証、リポジトリ更新は受け付けません。
実行結果は元Issueのコメントへ返信します。このMacでは本人認証・数値ID設定・実Issueの往復を検証し、120秒間隔のGitHub受信を常駐処理に登録しました。
SNS公開用APIは未実装です。接続や検証の詳細は初期報告を参照してください。

## 停止

```sh
python3 -m moco stop
python3 scripts/service.py stop
```

再開はMac上で `python3 -m moco resume --owner-confirmed`、常駐処理の再登録は操作手順を参照してください。
