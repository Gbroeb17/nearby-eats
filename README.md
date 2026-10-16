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

目前提供 Google 真實搜尋與模擬展示兩種模式。尚未實作裝置定位，請手動指定座標；模擬模式資料均為虛構。

## Google 真實搜尋

在本機建立 `.streamlit/secrets.toml`（此檔案已被 Git 忽略）：

```toml
GOOGLE_PLACES_API_KEY = "填入自己的金鑰"
```

需啟用 Places API (New)、連結帳單，並允許金鑰呼叫該 API。按搜尋按鈕才會發送一次 Nearby Search 請求，包含評分與營業時間，可能計費。單次最多回傳最近 20 家，不保證涵蓋全部餐廳或所有食物種類。分類來自 Google 類型，部分類型歸併為中文類別，未明確分類者列入其他。

分類、排序與營業篩選僅操作本次記憶體中的結果。改變座標或半徑需重新搜尋；結果五分鐘後需手動更新，不自動增加請求。營業狀態為查詢時快照；缺少打烊時間時不推測，無法通過最短剩餘時間篩選。

收到 403 時，請檢查帳單是否啟用、Places API (New) 是否已啟用，以及金鑰的 API/IP 限制。

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
