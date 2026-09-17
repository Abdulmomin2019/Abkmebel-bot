# 🚀 RENDER'GA QO'YISH — AVVAL SHUNI O'QING

Bu paketda **9 ta fayl** bor, hammasi bitta papkada (ichki papka yo'q) —
shuning uchun **telefondan yuklash oson**.

## Fayllar nima uchun kerak

| Fayl | Vazifasi |
|---|---|
| `bot_manager.py` | Botning o'zi (mijozlarga javob, kanal, guruh) |
| `tg_api.py` | Telegram bilan gaplashish |
| `telegram_scheduler.py` | Jadval bo'yicha post tashlash |
| `office_web.py`, `app_web.py` | AI-ofis va Ilova (Mini App) |
| `assets.py` | Post matnlari + rasmlar (kod ichida, papka kerak emas) |
| `config.json` | Sozlamalar (kanal, ish vaqti, narx) |
| `Procfile`, `render.yaml` | Render'ga "nima qanday ishga tushadi" deb aytadi |

## 5 qadam (telefondan, ~10 daqiqa)

1. **github.com** → `Sign up` (yoki `Sign in`) — bepul hisob.
2. **New repository** → nomi: `abkmebel-bot` → `Public` → **Create repository**.
3. **Add file → Upload files** → shu 9 faylni tanlang → **Commit changes**.
4. **render.com** → `Sign up` → **GitHub bilan** kiring → **New + → Blueprint** →
   repoyingizni tanlang → **Apply**.
5. So'ralgan joyga **BOT_TOKEN** ni qo'ying (boshqalari oldindan to'ldirilgan) →
   **Apply**. 2–3 daqiqadan keyin bot ishlaydi ✅

## Render XOHLAMASANGIZ — faqat GitHub bilan ham 24/7 bo'ladi

GitHub repo ichida `.github/workflows/bot.yml` faylini yaratsangiz, GitHub har 5 daqiqada
botni ishga tushirib ~4.5 daqiqa tinglab turadi. Mijoz yozsa — javob **1 daqiqada** keladi
(1500+ daqiqalik bepul limit faqat **ochiq (public)** repolarda cheksiz).

1. Repo → **Add file → Create new file** → nomi: `.github/workflows/bot.yml`
2. Ichiga quyidagini qo'ying (nusxa oling):

```yaml
name: Menejer bot (24/7 tinglash)
on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:
concurrency:
  group: bot-poll
  cancel-in-progress: false
jobs:
  poll:
    runs-on: ubuntu-latest
    timeout-minutes: 6
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Holatni tiklash
        uses: actions/cache/restore@v4
        with:
          path: data
          key: botdata-${{ github.run_id }}
          restore-keys: botdata-
      - name: Botni tinglash (4.5 daqiqa)
        env:
          BOT_TOKEN: ${{ secrets.BOT_TOKEN }}
          CHANNEL: ${{ secrets.CHANNEL }}
          ADMIN_ID: ${{ secrets.ADMIN_ID }}
          LISTEN_SECONDS: "260"
        run: python3 bot_manager.py --once
      - name: Holatni saqlash
        if: always()
        uses: actions/cache/save@v4
        with:
          path: data
          key: botdata-${{ github.run_id }}
```

3. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   `BOT_TOKEN`, `CHANNEL` (qiymati `@abk_mebel`), `ADMIN_ID` (`7707611721`)
4. **Actions** bo'limiga o'tib **Enable workflows** bosing — tamom.

> ⚠️ Bu variantda ilova (Mini App) uchun alohida manzil bo'lmaydi — menyu tugmasi ilovaga
> ulanmaydi. Ilova kerak bo'lsa Render ishlatiladi.

## Nima avtomatik bo'ladi

- Render manzilni o'zi topadi (`RENDER_EXTERNAL_URL`) — **webhook va menyu tugmasi o'zi o'rnatiladi**
- Ilova: `https://SIZNING-MANZIL.onrender.com/app`
- Postlar ham shu xizmat orqali ketadi — **GitHub Actions shart emas**
- Bepul tarif 15 daqiqada "uxlaydi" → **cron-job.org** orqali `/ping` ga har 10 daqiqada
  so'rov yuboring (bepul) — shunda bot 24/7 uyg'oq turadi.
