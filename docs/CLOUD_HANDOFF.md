# クラウド側Codexへの引き継ぎ

専用リポジトリ：`mailbox1156790-rgb/moco-sns-automation`。更新日：2026-10-19 JST。
最初に `AGENTS.md`、`docs/reports/2026-10-19-initial.md`、`docs/API_RESEARCH.md` を読んでください。秘密値をチャットで求める必要はありません。

## 現在の状態

GitHubの信頼済み定型指示をMacで受信し、下書き制作・確認待ち管理・実測・分析・GitHub報告を実行する基盤が動いています。**現在はThreadsの文章投稿だけが対象です。動画制作・Instagram/YouTube投稿を再開しないでください。** Threads文章用公開APIは実装・模擬検証済みですが、投稿用権限と初回本文/日時の本人確認が未完了のため無効です。動作モードは `draft_only`、新規SNS公開は0件です。最新情報は `docs/reports/2026-10-19-threads-only.md`。

本人が最初のテーマを **AI動画・SNS自動化の実用的なヒント** と指定しました。親しみのある短い問いかけと具体的な手順を仮方針とし、本人の経験や成果を創作しません。視聴者属性は未取得です。投稿頻度/時刻、避けたい内容、現行導線、本人素材と声・顔の利用範囲は未確定です。最初の原稿は `content/drafts/2026-10-19-first-batch/` に保存済みです。内容と制作記録は `docs/reports/2026-10-19-first-drafts.md` を参照してください。

|媒体|投稿先|API照合済みID|実測|
|---|---|---|---|
|YouTube|https://www.youtube.com/@MOCOchannel/shorts|UCjcZcz7chD2o6hu4ZUZSA8Q|本人OAuthのmine/forHandle一致。既存Shorts 3本の公開統計|
|Instagram|https://www.instagram.com/mocochan85/|17841469438292740|本人ユーザー名/テスターID一致。既存リール3本、6指標|
|Threads|https://www.threads.com/@mocochan85|27052393934458790|本人指定プロフィールとAPIユーザー名/ID照合。既存3件、6指標|

認証情報はMacのKeychainだけに保存しています。InstagramはGraph API v26.0、Threadsはv1.0の実接続です。テスター検索候補の内部IDはAPI IDへ流用していません。権限一覧APIはInstagramがHTTP 400、ThreadsがHTTP 500で未取得。UIの読取2権限準備と実際の読み取り成功とは分けて記録しています。Metaトークンの実期限と更新自動化は未確認/未実装です。

専用Metaアプリは本人が作成した `Moco SNS Automation`、アプリID1150847227441767、InstagramクライアントID2011482642896301、ThreadsクライアントID1774625623767445。読取はInstagram `instagram_business_basic` / `instagram_business_manage_insights`、Threads `threads_basic` / `threads_manage_insights` の本人承認範囲です。投稿権限 `threads_content_publish` の追加は本人確認待ちです。返信・DM権限は追加しません。投稿用トークンは既存読取キーと別の `threads_publish` に新規保存する実装で、まだ保存していません。

Annaの既存アプリ・認証情報は変更していません。**本人はChromeのAnnaログイン保持を希望しています。Chromeでログアウト/切り替えをしないでください。** Threadsは本人がSafariで認証し、Macの非表示フォームへコピーして保存しました。Safariのログインは本人申告、API IDとInsightsはMacから実照合済みです。CAPTCHAの迂回やFacebookパスワード再設定は行っていません。保存済みパスワードの確認は本人だけが行い、ツールで一覧・値を読まないでください。

詳細：`docs/reports/2026-10-19-youtube-connection.md`、`2026-10-19-instagram-connection.md`、`2026-10-19-threads-connection.md`、機械可読記録 `2026-10-19-verification.json`。

## Macの処理と検証

Python標準ライブラリ、SQLite、Swift/AppKit、FFmpegを使用。自動テスト80件成功。元の描画サンプルは `moco-7db4788a583f4b6f`、19.3秒・1080×1920・H.264/AAC、本人確認待ち。新しい制作物も本人承認前です。

本人のGitHub共同作業アカウントは `makoxx0815-tech`（数値ID343835729）。push/Issue権限とKeychain保管を確認済みです。
- [Issue #1](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/1#issuecomment-6264852109)：前景の状態確認、返信ID/DB一致、1件。
- [Issue #2](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/2#issuecomment-6264893882)：launchdが手動tickなしで受信・分析・返信。これは接続前の実測0件時点の証拠です。
- [Issue #3](https://github.com/mailbox1156790-rgb/moco-sns-automation/issues/3#issuecomment-6265853054)：公開YouTube 3本の定期実測報告。常駐返信・実ID照合・重複防止を確認済み。

当初は3媒体の照合済み投稿を収集しました。現在の定期取得・分析対象はThreadsの3件だけです。過去の計9件は保全しています。YouTubeの常駐実測成功は確認済み。Instagram/Threadsも各3件の前景実測と常駐用コードの本人ID確認を完了しました。その後の本人指示でInstagram/YouTubeの定期取得を休止しました。この2媒体の常駐実測成功は次周期待ちです。次の取得予定は2026-10-20 01:47 JST、Macの起動/ログイン/ネット接続が必要です。未取得を0で補いません。異なる媒体・公開後経過時間の数値から因果や最適時刻を断定しません。

以前のYouTube公開統計の自動報告は、Threads専用への変更に合わせ無効にしました。Instagram/ThreadsのInsights数値はMac内に保持し、クラウド側が取得できると仮定しないでください。GitHubへは接続状態・件数・指標名・公開投稿ID/URLだけ記録しています。

## クラウドからMacへ指示する方法

`moco:command` ラベル付きIssueへ厳密なJSONを置きます。指示ごとに新しいUUIDが必要です。例は `examples/command-status.json` と `examples/command-draft.json`。
許可は `draft` / `render` / `status` / `analyze` / `stop` のみです。数値の作者IDと最終編集者IDが信頼設定済みの場合だけ実行します。リポジトリ所有者・別bot・クラウドアカウントを自動で信頼しません。

公開・承認・再開・認証・シェル・git pullは受け付けません。クラウドはコード/原稿の編集・レビュー・PRを行えますが、MacのKeychain、DB、Safari、launchdを直接使えると仮定しないでください。原稿の変更はMacで確認して `revise` / `render` に反映します。現在のThreadsのrenderは文章ファイルの保存のみで、動画は生成しません。

## ローカルの場所

ソース：`/Users/maco/Documents/Codex/2026-10-19/sns-mac-https-github-com-mailbox1156790/moco-sns-automation`
実行用固定コピー：`~/Library/Application Support/MocoSNS/releases/710775ebd93cc644/`
ソースSHA-256：`710775ebd93cc644f9b26b70a93a60e19cdc959d3bcdea54e4284064d82c33c8`
共有状態・制作物：`~/Library/Application Support/MocoSNS/data/`（チェックアウトの `var` からリンク）
個別設定：同フォルダの `local-settings.json`（チェックアウトの `config/local.json` からリンク）
常駐処理：本人のlaunchd `jp.moco.sns-automation`、120秒ごとのGitHub受信。

Documentsへのバックグラウンドアクセス制限を避けるため、レビュー済みコードの固定コピーで実行しています。コード変更はMacで差分確認・必要なテスト後、`python3 scripts/install_runtime.py --github` で配置します。無条件のgit pullや公開リポジトリ用self-hosted runnerを追加しません。OS保護設定は変更していません。元データは無視対象 `work/` に保全しています。

## 次に進める作業

1. Threadsの初回本文・投稿先・公開タイミングを本人が確認する。本文は最新のThreads専用報告に掲載済み。
2. 専用アプリへ投稿権限1つを追加する本人確認、Safariでの再認証、Macの `secret-import threads_publish` への保存、本人ID照合を行う。既存読取認証は上書きしない。
3. 本人承認後にだけモード `threads_text` と `publishing.threads.enabled` / `permission_owner_approved` をMacで有効化する。`approve-threads` で本文・数値ID・時刻を固定し、初回は明示的な `publish-threads` で公開する。GitHub経由の承認は追加していない。
4. ID・URL・本文・投稿所有の照合と実測を確認する。自動予約は初回成功と本人の運用時刻確認後にだけ有効化する。POST応答不明は照合待ちで止め、再送しない。
5. Threadsのトークン更新・専用自動結果報告・異常通知を追加する。他媒体と動画の作業は休止を維持する。
