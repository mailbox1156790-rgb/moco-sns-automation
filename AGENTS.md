# このリポジトリで作業するCodexへ

- 最初に `docs/CLOUD_HANDOFF.md` と最新の `docs/reports/` を読む。
- 公開投稿は本人が投稿先・内容・日時を確認した後に実施する。この版には公開用APIを入れていない。本人の承認を代行しない。
- アカウントを同じユーザー名から推定して確定しない。YouTubeのOAuth接続先は `channels.list(mine=true)` と `forHandle=@MOCOchannel` のID一致で検証する。
- ローカル差分を確認してから変更する。reset/clean/強制push/既存データ削除はしない。
- パスワード・トークン・Cookie・ブラウザセッション・認証コードを、Git・チャット・ログへ書かない。APIレスポンスや例外を無加工でログ出力しない。
- `var/`、`config/local.json`、OAuthクライアントJSONはコミットしない。公開プロフィールの情報と推測、API実測値と未取得を区別する。
- TLS検証を無効化しない。HTTPリダイレクトへAuthorizationを転送しない。
- GitHub指示は定型JSONだけで、シェル、eval、外部コードのダウンロード実行を追加しない。Macに公開リポジトリ向けself-hosted runnerを設置しない。
- クラウドからMacのKeychainやブラウザを使えると仮定しない。Mac処理のコード変更はローカルで確認し、無条件のgit pullで常駐コードを更新しない。
- ロジックを変更したら `python3 -m unittest discover -s tests -v` を実行する。Macでの描画検証、外部API接続検証、公開検証を別々に記録する。
- 状態の `simulated` を `published` と報告しない。SNS投稿ID・公開URLが未取得なら空欄のままにする。
