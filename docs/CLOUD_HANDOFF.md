# クラウド側Codexへの引き継ぎ

専用リポジトリ：`mailbox1156790-rgb/moco-sns-automation`

まず `AGENTS.md` と `docs/reports/2026-10-19-initial.md`、`docs/API_RESEARCH.md` を読んでください。
このファイルだけで担当を移せます。チャット履歴に秘密値を求める必要はありません。

## 目標と現在地

GitHubの指示を本人のMacで受け、制作→本人確認→予約/公開→実測→分析→改善→GitHub報告を段階導入します。
現在は下書き専用。公開用APIは未実装です。初回の本人確認を省略しないでください。
Instagramは本人指定の `https://www.instagram.com/mocochan85/`。Threadsも本人指定の `https://www.threads.com/@mocochan85` を受領し設定済み（共有パラメータは除去）。Threadsの本文・APIアカウント照合は未実施。
YouTubeは本人所有の `https://www.youtube.com/@MOCOchannel/shorts`。読み取りOAuth後にチャンネルID `UCjcZcz7chD2o6hu4ZUZSA8Q` の一致も確認済みです。

Python標準ライブラリ、SQLite、Swift/AppKit、FFmpegを使用。Macのローカルサンプルは管理ID `moco-7db4788a583f4b6f`、19.3秒・1080×1920・H.264/AAC・本人確認待ち。
自動テスト42件成功。YouTubeの公開済みShorts 3本で公式APIの実測を取得し、常駐処理での更新も成功しました。新規公開は0件です。
本人のGitHub認証とpush/Issue権限を確認し、ソースと報告をmainへpush済みです。
[実Issue #1](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/1)をMacで処理し、[実返信](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/1#issuecomment-6264852109)とローカル実行記録を照合済みです。
Mac常駐処理が[実Issue #2](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/2)を自動受信し、実測0件の分析結果を返信したことも確認しました（手動tickなし）。120秒間隔で受信します。

## クラウドから行えること

- Pythonロジックの確認と `python3 -m unittest discover -s tests -v`。
- 公式仕様調査、本人の方針に基づく原稿案・改善案、PRでのコード変更。
- 本人から信頼設定されたGitHubアカウントを用いる場合の定型Issue作成。許可指示は `draft` / `render` / `status` / `analyze` / `stop`。

Issueには `moco:command` ラベルと厳密なJSON本文が必要です。新しいUUIDを指示ごとに使います。
本人が信頼した数値GitHub IDで作成/編集したIssueしかMacは実行しません。クラウド側の自動アカウントや別のbotを勝手に信頼設定へ追加しないでください。
現在Macで登録した本人の共同作業アカウントは `makoxx0815-tech` です。リポジトリ所有者やクラウド側の別アカウントも自動では信頼されません。
公開・承認・再開・シェル・認証・git pullの指示は実行されません。

## Macに残るもの

ソース：`/Users/maco/Documents/Codex/2026-10-19/sns-mac-https-github-com-mailbox1156790/moco-sns-automation`
実行用固定コピー：`~/Library/Application Support/MocoSNS/releases/コードハッシュ/`
状態・制作物：同フォルダの `data/`。チェックアウトの `var` がリンクしています。
個別設定：同フォルダの `local-settings.json`。チェックアウトの `config/local.json` がリンクしています。
認証情報：macOS Keychain。GitHubへのコミットやクラウド側への移送は禁止です。
常駐処理：本人のlaunchd `jp.moco.sns-automation`、120秒間隔。ログ/状態はローカルだけに保存。

GitHubからコードを自動更新しません。Macで差分を確認・テストし、`python3 scripts/install_runtime.py --github` で新しい固定コピーを配置します。
本人のOS保護設定は変更しません。Macのスリープ中には処理できない点を運用計画に含めてください。

YouTubeの最初の認証はMacの5分タイムアウトで終了しました。待受を60分へ修正し、再認証・Keychain保存・実API照合まで完了しました。最新結果は `docs/reports/2026-10-19-youtube-connection.md` と実測JSONを参照してください。古い認証URLは再利用しません。

このMacだけのローカル設定で、登録済みYouTube投稿を6時間ごとに再取得します。`metrics_collection.enabled` の基本設定はfalseです。Metaなど未接続媒体を勝手に有効化しないでください。毎回の実測スナップショットをGitHubへ自動追記する機能は次段階です。

## 次の優先事項

1. 優先テーマ・投稿頻度/時刻の本人確認。YouTube所有は本人確認済み、Threads URLも受領済み。
2. クラウド側で定型Issueを作成する場合、作者がMacで信頼設定済みかを確認。別の作者なら本人に確認してから追加。
3. YouTubeの読取OAuth・ID固定・3本の実測照合は完了。Instagram/ThreadsのMeta接続を進める。Instagram種別は本人も不明と回答。Chromeでは対象アカウントの本人ログインが必要。
4. 詳細Analytics、Metaトークン更新、公開アダプタを段階導入。公開前に本人確認。

未確定のMeta権限名・Graph API版・利用上限を断定しないでください。developerサイトの一部はこの調査で取得できず、公式Meta Postmanコレクションを参照しています。
公開POSTの通信失敗を自動再送する実装は入れず、応答不明は照合待ちとして止めてください。
