# HTTPS 上線

## 免費長期部署：Streamlit Community Cloud + Supabase

網站在雲端執行，個人電腦關機不影響網站。免費服務沒有全天候可用保證：Streamlit 閒置可能休眠，Supabase 免費專案低活動達七天可能暫停，屆時需到平台恢復。Google Places 費用獨立計算，仍須核對用量。

### 1. Supabase 持久計數

1. 登入 https://supabase.com/dashboard ，建立 Free 組織與專案 `nearby-eats`。選擇鄰近區域（例如 Singapore），保存資料庫密碼，不需開啟付費方案。
2. 在 SQL Editor 執行儲存庫的 `deploy/supabase.sql`，建立專用的非公開計數資料表。
3. 點 Connect，選 PostgreSQL URI 的 **Session pooler**（port 5432、支援 IPv4）。複製平台提供的實際連線字串，替換資料庫密碼；若密碼含特殊字元，需以 URL 編碼。
4. 不要把密碼或連線字串傳到聊天或提交 GitHub。

### 2. Streamlit 部署

1. 登入 https://share.streamlit.io ，以 GitHub 授權存取 `Gbroeb17/nearby-eats`。
2. Create app / Deploy an app：Repository `Gbroeb17/nearby-eats`、Branch `main`、Main file path `app.py`。
3. Advanced settings 選 Python 3.12，Secrets 貼入 `.streamlit/secrets.example.toml` 範本，將 Google key 與 Supabase session pooler 連線字串換成真實值。
4. `QUOTA_BACKEND` 必須是 `postgres`，不要把本機 `sqlite` 設定直接複製到雲端。
5. 當月外部用量補計需包含切換前的請求量；可保守高估，避免把本機使用過的額度再用一次。部署後本機若仍獨立用 SQLite，兩邊不共用計數，應停止本機真實查詢或改成共用相同 PostgreSQL。
6. 按 Deploy。成功後平台提供 HTTPS `*.streamlit.app` 網址；自訂名稱是否可用以平台為準。
7. 若要免登入分享，在 Streamlit 分享設定將「網站」設為公開。GitHub 儲存庫不必改成公開。

### 3. 驗證

- 手機開啟 HTTPS 網址並授權定位，確認顯示實際位置。
- 按一次搜尋確認真實資料可用與計數增加；分類排序不增加。
- 重啟雲端網站後確認計數仍在。用量資料庫無法使用或未設定時，真實查詢會保持鎖定。
- 若 Google key 限制了家中公用 IP，雲端請求可能被拒。不要填網站網址當 Python 後端的 IP 限制；依部署平台出站網路條件調整，保留 Places API (New) 的 API 限制。

官方說明：
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/platform/free-project-pausing

## 暫時分享本機網站

Cloudflare Quick Tunnel 可為本機 Streamlit 提供暫時 HTTPS 網址，不需要網域或 Cloudflare 帳號。

1. 在專案目錄啟動 `python -m streamlit run app.py --server.address 127.0.0.1`。
2. 使用官方 cloudflared 執行 `cloudflared tunnel --url http://127.0.0.1:8501`。
3. 開啟終端機顯示的 `https://…trycloudflare.com` 網址。

手機可以使用不同網路；定位仍需瀏覽器與系統授權。此方式使用電腦上的金鑰與用量資料庫，不需複製金鑰到雲端。電腦須保持連網且不休眠，Streamlit 與 tunnel 都須運作。停止 tunnel 後連結失效，重新啟動會產生不同網址。取得網址的人可使用餐廳搜尋，所有請求共用既有網站上限。

此方式用於開發、測試與短期展示，沒有上線時間保證，並非長期雲端主機。

## 長期部署

需有支援 Python、WebSocket 與 HTTPS 的雲端主機。API 金鑰以雲端秘密設定提供，禁止加入儲存庫。`data/api_usage.sqlite3` 必須使用持久磁碟且只跑一個服務實例；若使用多個實例則需改成共用資料庫。搬移時應將當月既有計數帶入，避免重新開始計數。

若平台不保證保存本機檔案，不能直接依賴現在的 SQLite 作為跨重啟額度保護，需先改用持久外部資料庫。

參考：https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/
