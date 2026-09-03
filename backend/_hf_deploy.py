"""一次性部署腳本：組裝 HF Space 暫存目錄 → 建 Space → 設 Secret → 上傳"""
import os
import shutil

from huggingface_hub import HfApi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # cardperks/
STAGE = os.path.join(ROOT, "_hf_stage")
TOKEN = os.environ["HF_TOKEN"]
REPO = "yassintw/cardperks"
DB_URL = open(os.path.join(ROOT, "backend", ".env"), encoding="utf-8").read().split("=", 1)[1].strip()

# 1) 組裝暫存目錄（排除機密與產物）
if os.path.exists(STAGE):
    shutil.rmtree(STAGE)
os.makedirs(STAGE)

shutil.copy(os.path.join(ROOT, "Dockerfile.hf"), os.path.join(STAGE, "Dockerfile"))

with open(os.path.join(STAGE, "README.md"), "w", encoding="utf-8") as f:
    f.write("""---
title: 卡優惠 CardPerks
emoji: 💳
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
short_description: 台灣信用卡優惠聚合——輸入商家，告訴你刷哪張卡最划算
---

# 卡優惠 CardPerks

記下你的卡 → 搜尋商家 → 立即比較回饋金額、綁定支付與登錄條件。
優惠資料每日自動更新自各發卡銀行官網，每筆附原始來源佐證與查核日期。

- 地圖模式：附近商家有哪些卡有優惠
- Pro：優惠到期提醒、帳單健檢（算出你刷錯卡少賺多少）
- 資料透明：每筆優惠可點開「原始資料來源」自行驗證
""")

shutil.copytree(os.path.join(ROOT, "backend"), os.path.join(STAGE, "backend"),
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "cardperks.db", "_*", "pipeline"))
shutil.copytree(os.path.join(ROOT, "legal"), os.path.join(STAGE, "legal"))
shutil.copy(os.path.join(ROOT, "index.html"), os.path.join(STAGE, "index.html"))
shutil.copy(os.path.join(ROOT, "schema.sql"), os.path.join(STAGE, "schema.sql"))
print("暫存目錄組裝完成")

# 2) 建 Space（公開、Docker）
api = HfApi(token=TOKEN)
url = api.create_repo(repo_id=REPO, repo_type="space", space_sdk="docker",
                      private=False, exist_ok=True)
print("Space:", url)

# 3) 設定 Secrets（資料庫連線；絕不放進檔案）
api.add_space_secret(repo_id=REPO, key="DATABASE_URL", value=DB_URL)
print("Secret DATABASE_URL 已設定")

# 4) 上傳
res = api.upload_folder(folder_path=STAGE, repo_id=REPO, repo_type="space",
                        commit_message="CardPerks 首次部署（FastAPI+原型+Supabase）")
print("上傳完成:", res)

shutil.rmtree(STAGE)
print("暫存目錄已清理")
