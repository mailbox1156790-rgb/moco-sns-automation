# クラウド側Codexへの引き継ぎ

専用リポジトリ：`mailbox1156790-rgb/moco-sns-automation`。更新日：2026-10-19 JST。
最初に `AGENTS.md`、`docs/reports/2026-10-19-initial.md`、`docs/API_RESEARCH.md` を読んでください。秘密値をチャットで求める必要はありません。

## 現在の状態

GitHubの信頼済み定型指示をMacで受信し、下書き制作・確認待ち管理・実測・分析・GitHub報告を実行する基盤が動いています。公開APIは未実装、動作モードは `draft_only`、新規SNS公開は0件です。

本人が最初のテーマを **AI動画・SNS自動化の実用的なヒント** と指定しました。親しみのある短い問いかけと具体的な手順を仮方針とし、本人の経験や成果を創作しません。視聴者属性は未取得です。投稿頻度/時刻、避けたい内容、現行導線、本人素材と声・顔の利用範囲は未確定です。最初の原稿は `content/drafts/2026-10-19-first-batch/` に保存済みです。内容と制作記録は `docs/reports/2026-10-19-first-drafts.md` を参照してください。

|媒体|投稿先|API照合済みID|実測|
|---|---|---|---|
|YouTube|https://www.youtube.com/@MOCOchannel/shorts|UCjcZcz7chD2o6hu4ZUZSA8Q|本人OAuthのmine/forHandle一致。既存Shorts 3本の公開統計|
|Instagram|https://www.instagram.com/mocochan85/|17841469438292740|本人ユーザー名/テスターID一致。既存リール3本、6指標|
|Threads|https://www.threads.com/@mocochan85|27052393934458790|本人指定プロフィールとAPIユーザー名/ID照合。既存3件、6指標|

認証情報はMacのKeychainだけに保存しています。InstagramはGraph API v26.0、Threadsはv1.0の実接続です。テスター検索候補の内部IDはAPI IDへ流用していません。権限一覧APIはInstagramがHTTP 400、ThreadsがHTTP 500で未取得。UIの読取2権限準備と実際の読み取り成功とは分けて記録しています。Metaトークンの実期限と更新自動化は未確認/未実装です。

専用Metaアプリは本人が作成した `Moco SNS Automation`、アプリID1150847227441767、InstagramクライアントID2011482642896301、ThreadsクライアントID1774625623767445。読取はInstagram `instagram_business_basic` / `instagram_business_manage_insights`、Threads `threads_basic` / `threads_manage_insights` の本人承認範囲です。投稿・返信・DMの追加許可は求めていません。

Annaの既存アプリ・認証情報は変更していません。**本人はChromeのAnnaログイン保持を希望しています。Chromeでログアウト/切り替えをしないでください。** Threadsは本人がSafariで認証し、Macの非表示フォームへコピーして保存しました。Safariのログインは本人申告、API IDとInsightsはMacから実照合済みです。CAPTCHAの迂回やFacebookパスワード再設定は行っていません。保存済みパスワードの確認は本人だけが行い、ツールで一覧・値を読まないでください。

詳細：`docs/reports/2026-10-19-youtube-connection.md`、`2026-10-19-instagram-connection.md`、`2026-10-19-threads-connection.md`、機械可読記録 `2026-10-19-verification.json`。

## Macの処理と検証

Python標準ライブラリ、SQLite、Swift/AppKit、FFmpegを使用。自動テスト59件成功。元の描画サンプルは `moco-7db4788a583f4b6f`、19.3秒・1080×1920・H.264/AAC、本人確認待ち。新しい制作物も本人承認前です。

本人のGitHub共同作業アカウントは `makoxx0815-tech`（数値ID343835729）。push/Issue権限とKeychain保管を確認済みです。
- [Issue #1](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/1#issuecomment-6264852109)：前景の状態確認、返信ID/DB一致、1件。
- [Issue #2](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/2#issuecomment-6264893882)：launchdが手動tickなしで受信・分析・返信。これは接続前の実測0件時点の証拠です。
- [Issue #3](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/3#issuecomment-6265853054)：公開YouTube 3本の定期実測報告。常駐返信・実ID照合・重複防止を確認済み。

このMacでは登録済みの照合済み投稿だけを6時間ごとに収集し、最新9件を分析対象にしています。YouTubeの常駐実測成功は確認済み。Instagram/Threadsも各3件の前景実測と常駐用コードの本人ID確認を完了し、収集対象へ追加しました。この2媒体の常駐実測成功は次周期待ちです。次の取得予定は2026-10-20 01:47 JST、Macの起動/ログイン/ネット接続が必要です。未取得を0で補いません。異なる媒体・公開後経過時間の数値から因果や最適時刻を断定しません。

GitHubへ自動送信する実測値は、公開状態と所有を再確認したYouTubeの公開統計だけです。Instagram/ThreadsのInsights数値はMac内に保持し、クラウド側が取得できると仮定しないでください。GitHubへは接続状態・件数・指標名・公開投稿ID/URLだけ記録しています。

## クラウドからMacへ指示する方法

`moco:command` ラベル付きIssueへ厳密なJSONを置きます。指示ごとに新しいUUIDが必要です。例は `examples/command-status.json` と `examples/command-draft.json`。
許可は `draft` / `render` / `status` / `analyze` / `stop` のみです。数値の作者IDと最終編集者IDが信頼設定済みの場合だけ実行します。リポジトリ所有者・別bot・クラウドアカウントを自動で信頼しません。

公開・承認・再開・認証・シェル・git pullは受け付けません。クラウドはコード/原稿の編集・レビュー・PRを行えますが、MacのKeychain、DB、Safari、launchdを直接使えると仮定しないでください。原稿の変更はMacで確認して `revise` / `render` に反映します。

## ローカルの場所

ソース：`/Users/maco/Documents/Codex/2026-10-19/sns-mac-https-github-com-mailbox1156790/moco-sns-automation`
実行用固定コピー：`~/Library/Application Support/MocoSNS/releases/d6598cb54d3e6e13/`
ソースSHA-256：`d6598cb54d3e6e13dfce16bc785c60d8135c781272ba3de14e0650fa88daad9c`
共有状態・制作物：`~/Library/Application Support/MocoSNS/data/`（チェックアウトの `var` からリンク）
個別設定：同フォルダの `local-settings.json`（チェックアウトの `config/local.json` からリンク）
常駐処理：本人のlaunchd `jp.moco.sns-automation`、120秒ごとのGitHub受信。

Documentsへのバックグラウンドアクセス制限を避けるため、レビュー済みコードの固定コピーで実行しています。コード変更はMacで差分確認・必要なテスト後、`python3 scripts/install_runtime.py --github` で配置します。無条件のgit pullや公開リポジトリ用self-hosted runnerを追加しません。OS保護設定は変更していません。元データは無視対象 `work/` に保全しています。

## 次に進める作業

1. 本人指定テーマの具体的な原稿・動画・カバーを提示し、内容/素材/投稿先/日時を本人が確認できる形にする。
2. Metaトークンの期限確認と安全な更新、YouTube詳細Analytics、失敗通知・ログローテーション・バックアップ/復元を実装する。
3. 公開アダプタは別段階で実装する。必要な公開権限の追加はその時点で本人確認。可能な媒体では非公開検証から行う。
4. 初回の公開は本人の内容・投稿先・日時確認後。送信前に状態を永続化し、応答不明は照合待ちで停止する。公開POSTを無条件再送しない。
5. ID・URL・公開状態を再取得し、同じ媒体と同じ経過時間の実測で改善案を作る。
