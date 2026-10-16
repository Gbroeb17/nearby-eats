# 附近吃什麼？ Nearby Eats

使用 Python 與 Streamlit 製作的附近餐廳搜尋工具，為 AI-Assisted Programming Project 課程專案。

## 專案目標

協助使用者依距離、餐廳種類、評分與營業時間選擇餐廳。搜尋結果受資料來源與回傳數量限制，不保證包含範圍內所有餐廳。

## 預計功能

- 指定搜尋位置與 1、3、5 公里半徑。
- 依餐廳種類分組，依距離或評分排序。
- 顯示評分、評論數、直線距離與營業狀態。
- 顯示打烊時間；缺少資料時明確標示未知。
- 篩選營業中的餐廳，連結至 Google Maps。

## 開發順序

1. 使用明確標示的模擬資料完成可操作介面。
2. 串接 Google Places API，處理錯誤與缺漏資料。
3. 測試距離、排序與跨午夜營業時間等核心邏輯。
4. 完成報告與 AI 協作紀錄。
5. 視時間加入 MCP 搜尋工具。

## 技術規劃

Python 3.12、Streamlit、Google Places API、pytest、GitHub Actions。

目前提供 Google 真實搜尋與模擬展示兩種模式。預設中心為中央大學周邊；可按「使用裝置位置」並授權瀏覽器定位。模擬模式資料均為虛構。

## 裝置定位

定位採瀏覽器 Geolocation，一次點選取得一次位置，不持續追蹤。取得位置不會呼叫 Google；按下餐廳搜尋後才將搜尋中心傳送至 Google。位置僅保留於工作階段，不寫入用量資料庫。

## HTTPS 雲端部署

免費部署規劃採 Streamlit Community Cloud 與 Supabase PostgreSQL，步驟見 [部署說明](docs/https-deployment.md)。範本為 `.streamlit/secrets.example.toml`，建表 SQL 為 `deploy/supabase.sql`。雲端預設要求 PostgreSQL，缺少設定或無法連線時停止真實查詢，避免誤用會在重啟後遺失的本機計數。尚未完成實際雲端部署。

本機開發請在本機 secrets 的最上方設定 `QUOTA_BACKEND = "sqlite"`；此設定不適用於免費雲端主機。PostgreSQL 計數以交易鎖定同月份資料列，供多個工作階段共用。

需要瀏覽器與作業系統允許定位，網站須在 HTTPS 或本機 localhost/127.0.0.1 環境。內建瀏覽器可能不支援，可改用 Chrome 或 Edge。定位被拒、逾時或不可用時顯示提示，保留原搜尋中心，可一鍵切回中央大學或展開手動座標。電腦定位可能存在較大誤差，畫面顯示瀏覽器回報的精確度。手機連線至電腦的區網 HTTP 網址一般不符合安全環境要求，部署至 HTTPS 後再使用手機定位。

## Google 真實搜尋

在本機建立 `.streamlit/secrets.toml`（此檔案已被 Git 忽略）：

```toml
GOOGLE_PLACES_API_KEY = "填入自己的金鑰"
```

需啟用 Places API (New)、連結帳單，並允許金鑰呼叫該 API。按搜尋按鈕才會發送一次 Nearby Search 請求，包含評分與營業時間，可能計費。單次最多回傳最近 20 家，不保證涵蓋全部餐廳或所有食物種類。分類來自 Google 類型，部分類型歸併為中文類別，未明確分類者列入其他。

分類、排序與營業篩選僅操作本次記憶體中的結果。改變座標或半徑需重新搜尋；結果五分鐘後需手動更新，不自動增加請求。營業狀態為查詢時快照；缺少打烊時間時不推測，無法通過最短剩餘時間篩選。

收到 403 時，請檢查帳單是否啟用、Places API (New) 是否已啟用，以及金鑰的 API/IP 限制。

## 每月用量保護

網站預設每月最多 950 次請求，保留免費 1,000 次與網站上限之間的緩衝。達到網站上限時顯示通知並停用搜尋按鈕，伺服器也會在發送請求前再次檢查。使用 SQLite 原子交易預先計數，避免多個使用者同時查詢突破限制；失敗或結果不明的請求仍保守計入。

計數保存在 `data/api_usage.sqlite3`，不包含金鑰或餐廳資料、不上傳 GitHub，重新整理或重啟不會歸零。依美國太平洋時間月份分開記錄。勿刪除此資料庫；部署時必須保存於持久儲存。同一資料庫服務的使用者共用計數，多台伺服器若各用獨立資料庫則無法共用限制。

此計數不是 Google 官方用量，無法自動包含功能上線前或其他程式的請求，也無法保證帳戶完全不產生費用。可在本機 secrets 設定更低的上限，並補計該月份未納入的外部用量：

```toml
MONTHLY_REQUEST_LIMIT = 950

[EXTERNAL_USAGE_BY_MONTH]
"2026-10" = 10 # 範例：請換成未被此網站計數的實際次數，不是 Google 總用量
```

用量資料庫無法讀寫時停止查詢。模擬模式、分類與排序不扣額度。手動驗證腳本也共用此計數。仍應定期與 Google 官方帳單及請求報表核對。

## 本機啟動（Windows PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m streamlit run app.py
```

啟動後開啟終端機顯示的本機網址，通常是 http://localhost:8501 。不需要 Google API 金鑰即可操作模擬版。

```powershell
.\.venv\Scripts\python -m pytest -q
```

模擬版的營業時間假設每天相同；正式資料串接時需另外處理週間排程、特殊日期與店家時區。評分排序採評分、評論數、距離依序比較，並非綜合推薦演算法。

## 金鑰管理

API 金鑰使用環境變數或本機 Streamlit secrets 設定，禁止提交到 GitHub。真實資料串接前，需設定金鑰限制、使用配額與費用提醒。

## 作業紀錄

AI 合作過程記錄於 [docs/ai-collaboration.md](docs/ai-collaboration.md)。開發時逐步提交可驗證的變更，不補造開發歷史。
