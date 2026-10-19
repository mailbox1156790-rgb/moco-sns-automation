# 公式API・認証調査（2026-10-19 JST）

以下は実装候補と公式仕様の確認です。アカウントでのAPI実動確認とは区別します。
パスワードやブラウザCookieの自動操作で公開する方式は採用しません。

## YouTube Shorts

YouTube Data APIの `videos.insert` が動画アップロード用です。OAuth 2.0の `youtube.upload` 等が必要で、タイトル・説明・privacyStatus・publishAt等を扱います。
公開/限定公開/非公開を常に明示し、将来の初期接続では非公開アップロード→所有・処理状態確認→本人の初回公開承認を分けます。
この版はアップロードを実装していません。古い資料のクォータ固定値や監査制限を転記せず、プロジェクトの現行制限も接続時に確認します。[公式アップロードAPI](https://developers.google.com/youtube/data/reference/rest/v3/videos/insert)

`channels.list(forHandle=@MOCOchannel)` と、本人OAuthの `mine=true` のID一致で対象を照合します。ブラウザでログインしているだけでは所有確認になりません。[公式チャンネル取得API](https://developers.google.com/youtube/data/reference/rest/v3/channels/list)

Macの認証はデスクトップ用OAuthクライアント、PKCE、state照合、127.0.0.1の一時コールバックを使います。取得したrefresh tokenはKeychainへ保存します。この版は `youtube.readonly` と `yt-analytics.readonly` だけを要求します。[公式デスクトップOAuth](https://developers.google.com/identity/protocols/oauth2/native-app)

実績はData APIの動画統計とYouTube Analytics APIのレポートが候補です。`reports.query` は期間・指標・ディメンションを指定でき、OAuthが必要です。現行ページでは `youtube.readonly` の必要性も明記されています。統計の提供が遅れる場合があるため、未提供の期間をゼロで補いません。この版はData APIの再生・高評価・コメントのみ初期実装し、Analytics詳細取込は未実装です。[公式Analyticsレポート](https://developers.google.com/youtube/analytics/reference/reports/query)

## Instagramリール

本人指定のURLは https://www.instagram.com/mocochan85/ 。本人ログイン後のプロフェッショナルダッシュボードを確認し、Professionalであることは確認済みです。Creator/Businessの内訳は未確認です。API本人ID照合は完了しました。Meta本人確認後、開発者アプリ画面へのアクセス復旧を確認しました。専用アプリを本人が作成し、読取2権限追加・テスター招待の本人承認まで完了しました。再設定後の新しい認証からトークン生成まで確認し、Keychain保存・本人ユーザー名/ID一致・既存リール3本のInsights実取得まで完了しました（2026-10-19の画面観測）。
Instagram API with Instagram LoginはProfessionalアカウント向けで、Facebook Pageの接続を必須にしない経路です。基本・公開権限は `instagram_business_basic` と `instagram_business_content_publish`。Facebook Login用の権限と混ぜません。[Meta公式Instagram Loginコレクション](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login)

リール公開にはメディアコンテナ作成、処理状態確認、`media_publish`、返されたmedia IDの再取得を組み合わせます。Meta公式コレクションはFacebook Login経路の公開例も提供しています。経路ごとにホスト・トークン・権限が異なるため、例をそのまま別経路へ流用しません。[Meta公式リール公開例](https://www.postman.com/meta/instagram/request/gabnx7r/publish-reel)

分析にはInstagram Insightsを利用します。利用可能指標・権限の組み合わせ・Graph API版はMeta Developer画面で最終確認が必要です。developerサイトの一部URLはこの調査で429またはページ削除表示となり、調査時にはInsights権限を文書で確定できませんでした。その後、本人ログイン済みのMeta公式「アクセス許可と機能」画面で、Instagram Login用の `instagram_business_manage_insights` と `instagram_business_basic` の名称・用途を確認しました。この2権限は本人承認後に専用アプリへ追加済みです。実トークンをKeychainへ保存し、Graph API v26.0で本人ID・投稿一覧と、リール3本のviews/reach/likes/comments/saved/sharesを実取得しました。権限一覧の `/me/permissions` はHTTP 400のため未取得です。初期クライアントは未設定のAPI版を拒否し、未対応の指標はnullで残します。

本人操作：Instagram本人ログインと読み取りOAuth同意、必要に応じたApp Review/アクセスレベル確認。Metaの同意フローと期限更新の自動化は未実装です。

## Threads

Threads用MetaアプリとOAuthを利用します。本人承認後、もこ専用アプリにThreads用途と基本/Insightsの2読取権限を追加し、公式画面の「テスト準備完了」を確認しました。本人トークンは未取得です。投稿は `threads_basic` / `threads_content_publish`、分析は `threads_manage_insights` を候補に、本人の付与済み権限を確認します。投稿実測にはviews/likes/replies/reposts/quotes/shares等があります。[Meta公式Threads Insights](https://www.postman.com/meta/threads/request/ndeeu6p/get-post-insights)

通常は `/threads` でコンテナを作り、`/threads_publish` で公開してIDを照合します。テキスト作成時の `auto_publish_text=true` は即時公開を起こすため、下書き検証では呼びません。画像・動画の配信方法やURL公開の範囲は本人の素材運用を決めてから設計します。[Meta公式Threads公開フロー](https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api?entity=request-34203612-f8bf85ba-a2a2-47f8-9183-f94cd3e9c9d3)

長期トークンと更新エンドポイントが提供されています。公式コレクション例のexpires_inは5,184,000秒です。固定の無期限トークンとは扱わず、実際の有効期限と更新可否を確認します。この版はKeychainへの保存と読取APIの初期実装までで、更新自動化は未実装です。[Meta公式Threads認証例](https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api?entity=request-34203612-74fb48b1-ad1a-480e-b200-4dcdb8126a2f)

## GitHub

初期導入はMac上のGitHub CLI認証を利用。長期運用は専用GitHub Appまたは対象リポジトリ限定のfine-grained PATが候補です。必要権限は原則としてMetadata読取・Issues読書き。コードの取得/報告のcommit用にContents権限を別途扱います。アカウント全体への権限追加はこの段階では行いません。[GitHubの権限一覧](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)

Issueを指定ラベルで受信し、本人の数値ID・最終編集者を検証。任意シェルやリモートのコード更新には使いません。最小APIクライアントはTLS検証を有効にし、認証ヘッダをリダイレクト転送しません。

## 接続後の検証順

1. 認証→実アカウントID→本人確認済み設定への固定。
2. 既存投稿のID・URL・所有を照合し、読取実測を取得。
3. 制作済み動画を本人が確認。
4. 新規公開機能を実装し、可能な媒体は非公開段階で確認。Metaの公開用コンテナは恒久的な下書き保管とは扱わない。
5. 初回の本文・素材・投稿先・日時を本人が確認した後に公開。
6. 公開後のID・URL・状態を再取得。応答不明時は再送せず照合待ちへ。
