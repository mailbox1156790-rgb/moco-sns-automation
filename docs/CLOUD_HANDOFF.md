# クラウド側Codexへの引き継ぎ

専用リポジトリ：`mailbox1156790-rgb/moco-sns-automation`

まず `AGENTS.md` と `docs/reports/2026-10-19-initial.md`、`docs/API_RESEARCH.md` を読んでください。
このファイルだけで担当を移せます。チャット履歴に秘密値を求める必要はありません。

## 目標と現在地

GitHubの指示を本人のMacで受け、制作→本人確認→予約/公開→実測→分析→改善→GitHub報告を段階導入します。
現在は下書き専用。公開用APIは未実装です。初回の本人確認を省略しないでください。
Instagramは本人指定の `https://www.instagram.com/mocochan85/`。Threadsは未確認。
YouTubeの指定は `https://www.youtube.com/@MOCOchannel/shorts`、公開ページでハンドルを確認済み。本人の所有/OAuth照合はまだです。

Python標準ライブラリ、SQLite、Swift/AppKit、FFmpegを使用。Macのローカルサンプルは管理ID `moco-7db4788a583f4b6f`、19.3秒・1080×1920・H.264/AAC・本人確認待ち。
自動テスト27件成功。Macで画像/動画も確認しました。架空のSNS実績を作成していません。

## クラウドから行えること

- Pythonロジックの確認と `python3 -m unittest discover -s tests -v`。
- 公式仕様調査、本人の方針に基づく原稿案・改善案、PRでのコード変更。
- 本人から信頼設定されたGitHubアカウントを用いる場合の定型Issue作成。許可指示は `draft` / `render` / `status` / `analyze` / `stop`。

Issueには `moco:command` ラベルと厳密なJSON本文が必要です。新しいUUIDを指示ごとに使います。
本人が信頼した数値GitHub IDで作成/編集したIssueしかMacは実行しません。クラウド側の自動アカウントや別のbotを勝手に信頼設定へ追加しないでください。
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

## 次の優先事項

1. GitHub認証と実Issueによる往復確認（初期報告の最新状況を確認）。
2. Threads URL・YouTube所有・方針/時刻の本人確認。
3. Google/Metaの読取OAuth→アカウントID固定→既存投稿ID/URL・実測照合。
4. 詳細Analytics、Metaトークン更新、公開アダプタを段階導入。公開前に本人確認。

未確定のMeta権限名・Graph API版・利用上限を断定しないでください。developerサイトの一部はこの調査で取得できず、公式Meta Postmanコレクションを参照しています。
公開POSTの通信失敗を自動再送する実装は入れず、応答不明は照合待ちとして止めてください。
