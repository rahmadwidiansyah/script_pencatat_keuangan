import re
import os
import asyncpg
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

# --- VARIABEL GLOBAL UNTUK CACHE MEMORI ---
WALLET_GROUPS = {}
KEYWORD_TO_WALLET = {}
CATEGORIES_CONFIG = {}
ALL_KEYWORDS = []
CATEGORY_PATTERNS = []

# Variabel Default (Fallback)
DEFAULT_EXPENSE = ("❓ Lain-lain (Pengeluaran)", "Pengeluaran 🔴")
DEFAULT_INCOME = ("❓ Lain-lain (Pemasukan)", "Pemasukan 🟢")
DEFAULT_TRANSFER = ("🔄 Pindah Saldo", "Transfer 🔵")

# Konfigurasi Fuzzy
MIN_LEN = 4
MIN_SCORE = 85
LEN_TOLERANCE = 2

# --- FUNGSI LOAD DATABASE ---
async def load_data_from_db():
    global WALLET_GROUPS, KEYWORD_TO_WALLET, CATEGORIES_CONFIG
    global ALL_KEYWORDS, CATEGORY_PATTERNS
    global DEFAULT_EXPENSE, DEFAULT_INCOME, DEFAULT_TRANSFER

    print("🔄 Memuat ulang data dari PostgreSQL...")

    # Koneksi ke DB
    conn = await asyncpg.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432")
    )

    try:
        # 1. Reset Variabel
        WALLET_GROUPS.clear()
        KEYWORD_TO_WALLET.clear()
        CATEGORIES_CONFIG.clear()
        ALL_KEYWORDS.clear()
        CATEGORY_PATTERNS.clear()

        # 2. Ambil Data Accounts (Wallets)
        accounts = await conn.fetch("SELECT nama, group_type, keywords FROM accounts WHERE keywords IS NOT NULL")
        for acc in accounts:
            grp = acc['group_type'] or "GENERAL"
            wallet_key = acc['nama'].lower() # Misal "seabank"
            kws = acc['keywords']

            if grp not in WALLET_GROUPS:
                WALLET_GROUPS[grp] = {}
            WALLET_GROUPS[grp][wallet_key] = kws

            for kw in kws:
                KEYWORD_TO_WALLET[kw.lower()] = wallet_key
                ALL_KEYWORDS.append(kw.lower())

        # 3. Ambil Data Kategori
        categories = await conn.fetch("SELECT nama, jenis, keywords, is_default_expense, is_default_income, is_default_transfer FROM categories")
        for cat in categories:
            cat_tuple = (cat['nama'], cat['jenis'])
            kws = cat['keywords'] or []

            if kws:
                CATEGORIES_CONFIG[cat_tuple] = kws
                for kw in kws:
                    ALL_KEYWORDS.append(kw.lower())

            # Set Default Fallback jika dicentang di DB
            if cat['is_default_expense']: DEFAULT_EXPENSE = cat_tuple
            if cat['is_default_income']: DEFAULT_INCOME = cat_tuple
            if cat['is_default_transfer']: DEFAULT_TRANSFER = cat_tuple

        # 4. Normalisasi ALL_KEYWORDS & Compile Regex
        ALL_KEYWORDS = list(set(ALL_KEYWORDS))

        for (cat, typ), keywords in CATEGORIES_CONFIG.items():
            keywords.sort(key=len, reverse=True)
            escaped = [re.escape(k) for k in keywords]
            pattern = re.compile(r'\b(?:' + "|".join(escaped) + r')\b', re.IGNORECASE)
            CATEGORY_PATTERNS.append(((cat, typ), pattern))

        print("✅ Data berhasil dimuat!")

    finally:
        await conn.close()

# --- LIFESPAN (Jalan Otomatis Saat Start) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_data_from_db() # Load awal
    yield
    # Cleanup kalau server mati (jika ada)

app = FastAPI(title="AI Keuangan Pro", lifespan=lifespan)

# --- API KEY CONFIG ---
API_KEY_NAME = "X-API-KEY"
API_KEY = os.getenv("API_KEY_SECRET", "kunci-rahasia-default")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

class ChatRequest(BaseModel):
    text: str

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(status_code=403, detail="Akses Ditolak")

# ==========================================
# ENDPOINT REFRESH (Panggil ini kalau update DB)
# ==========================================
@app.post("/refresh-keywords")
async def refresh_keywords(api_key: str = Depends(get_api_key)):
    try:
        await load_data_from_db()
        return {"success": True, "message": "Database berhasil disinkronisasi ulang ke memori."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# LOGIC FUNCTIONS (Pindahkan kode get_nominal_smart, detect_wallets_ordered, fix_typo_vn kamu ke sini)
# ==========================================

def get_nominal_smart(text):
    text_lower = text.lower()
    match_suffix = re.search(r'(\d+[.,]?\d*)\s*(rb|ribu|k|jt|juta)\b', text_lower)

    if match_suffix:
        angka_str = match_suffix.group(1).replace(",", ".")
        suffix = match_suffix.group(2)
        try:
            angka = float(angka_str)
            if suffix in ['rb', 'ribu', 'k']: return int(angka * 1000)
            elif suffix in ['jt', 'juta']: return int(angka * 1000000)
        except ValueError:
            pass

    clean_text = text_lower.replace(".", "").replace(",", "")
    all_numbers = re.findall(r'\b\d+\b', clean_text)
    valid_numbers = [int(n) for n in all_numbers if int(n) >= 1000]
    return max(valid_numbers) if valid_numbers else None


def detect_wallets_ordered(text_lower):
    matches = []
    for kw, wallet_key in KEYWORD_TO_WALLET.items():
        pattern = r'\b' + re.escape(kw) + r'\b'
        for m in re.finditer(pattern, text_lower):
            matches.append((m.start(), wallet_key))

    matches.sort(key=lambda x: x[0])
    ordered = []
    seen = set()
    for _, w in matches:
        if w not in seen:
            ordered.append(w)
            seen.add(w)
    return ordered


def extract_subject(text):
    match = re.search(r'#([a-zA-Z0-9_]+)', text)
    return match.group(1).upper() if match else None


def detect_category_basic(text_lower):
    best_cat, best_type = DEFAULT_EXPENSE
    best_score = 0

    # 1. Cari kategori spesifik dari regex yang sudah di-compile
    for (cat, typ), pattern in CATEGORY_PATTERNS:
        matches = pattern.findall(text_lower)
        score = len(matches)
        if score > best_score:
            best_score, best_cat, best_type = score, cat, typ

    # 2. Logika Fallback (Jika tidak ada kategori yang cocok)
    if best_score == 0:
        # Ambil keyword pemicu langsung dari variabel memori yang bersumber dari DB
        kw_expense = CATEGORIES_CONFIG.get(DEFAULT_EXPENSE, [])
        kw_income = CATEGORIES_CONFIG.get(DEFAULT_INCOME, [])

        if any(x in text_lower for x in kw_expense):
            best_cat, best_type = DEFAULT_EXPENSE
        elif any(x in text_lower for x in kw_income):
            best_cat, best_type = DEFAULT_INCOME
        else:
            best_cat, best_type = DEFAULT_TRANSFER

    return best_cat, best_type


def wallet_get_group(wallet_key):
    if not wallet_key: return None
    wk = wallet_key.lower()
    for gname, wallets in WALLET_GROUPS.items():
        if wk in wallets:
            return gname
    return None

# ==========================================
# CORE ANALYZE
# ==========================================

@app.post("/analyze")
async def analyze_transaction(request: ChatRequest, api_key: str = Depends(get_api_key)):
    text = request.text
    text_lower = text.lower()

    # --- FITUR BARU: DETEKSI HAPUS (DELETE INTENT) ---
    delete_keywords = ["hapus", "delete", "batal", "cancel", "undo"]
    if any(kw in text_lower for kw in delete_keywords):
        # 1. Cek jika ada ID spesifik (angka)
        id_match = re.search(r'\b(\d+)\b', text_lower)

        # 2. Cek jika ada indikasi "terakhir"
        is_last = any(x in text_lower for x in ["terakhir", "last", "tadi", "barusan"])

        # JALUR A: Hapus berdasarkan ID
        if id_match:
            return {
                "success": True,
                "intent": "delete transaction",
                "id": id_match.group(1),
                "message": f"🗑️ Menghapus transaksi ID: {id_match.group(1)}."
            }

        # JALUR B: Hapus transaksi terakhir
        if is_last or text_lower in delete_keywords: # Jika cuma ketik "hapus" tanpa angka, asumsikan hapus terakhir
            return {
                "success": True,
                "intent": "delete last",
                "message": "🗑️ Menghapus transaksi terakhir kamu."
            }



    # --- Transaksi Normal
    nominal = get_nominal_smart(text)
    wallets = detect_wallets_ordered(text_lower)
    subject = extract_subject(text)
    cat_name, cat_type = detect_category_basic(text_lower)

    source, dest = None, None

    # --- LOGIKA CORE DENGAN AKUN STATIS ---

    # 1. Kasus HUTANG & PIUTANG (Wajib #nama)
    if "Hutang" in (cat_type or "") or "Piutang" in (cat_type or ""):
        if not subject:
            return {"success": False, "message": f"Gagal: Transaksi {cat_type} wajib mencantumkan #nama."}
        if not wallets:
            return {"success": False, "message": f"Gagal: Wajib menyebutkan dompet (BCA, Gopay, dll)."}

        wallet_detect = wallets[0].upper()

        if cat_type == "Hutang (Masuk)":
            source, dest = "HUTANG", wallet_detect
        elif cat_type == "Cicil Hutang (Keluar)":
            source, dest = wallet_detect, "HUTANG"
        elif cat_type == "Piutang (Keluar)":
            source, dest = wallet_detect, "PIUTANG"
        elif cat_type == "Piutang (Masuk)":
            source, dest = "PIUTANG", wallet_detect

    # 2. Kasus TRANSFER / INVESTASI (Wajib 2 Dompet Fisik)
    elif cat_type == "Transfer 🔵":
        if len(wallets) >= 2:
            src_key, dst_key = wallets[0], wallets[1]
            source, dest = src_key.upper(), dst_key.upper()

            src_group = wallet_get_group(src_key)
            dst_group = wallet_get_group(dst_key)

            merchant_indicators = ["beli", "bayar", "jajan", "pakai", "checkout", "belanja"]

            is_confident_transfer = (
                cat_type == "Transfer 🔵"
                or (
                    any(x in text_lower for x in ["pindah", "topup", "tarik", "top up", "tf", "transfer"])
                    and src_group == "LIQUID"
                    and dst_group == "LIQUID"
                    and not any(m in text_lower for m in merchant_indicators)
                )
            )

            # Prioritaskan INVESTMENT jika tujuan termasuk INVESTMENT
            if dst_group == "INVESTMENT":
                cat_type = "Investasi 🟡"
                cat_name = f"📈 Nabung ke {dst_key.upper()}"
            elif is_confident_transfer:
                cat_name = "🔄 Pindah Saldo"
        else:
            return {"success": False, "message": "Gagal: Transfer wajib menyebutkan 2 dompet."}

    # 3. Kasus PEMASUKAN UMUM (Gaji, dll)
    elif cat_type == "Pemasukan 🟢":
        if wallets:
            source, dest = "EKSTERNAL", wallets[0].upper()
        else:
            return {"success": False, "message": "Gagal: Pemasukan wajib menyebutkan dompet tujuan."}

    # 4. Kasus PENGELUARAN UMUM (Makan, dll)
    elif cat_type == "Pengeluaran 🔴":
        if wallets:
            source, dest = wallets[0].upper(), "MERCHANT"
        else:
            return {"success": False, "message": "Gagal: Pengeluaran wajib menyebutkan dompet asal."}

    # --- VALIDASI AKHIR ---
    if not nominal:
        return {"success": False, "message": "Gagal: Nominal tidak ditemukan."}

    if not source or not dest:
        return {"success": False, "message": "Gagal: Source atau Destination tidak terdeteksi dengan benar."}

    return {
        "success": True,
        "intent": "add transaction",
        "message": f"{cat_type}: {cat_name} | Rp {nominal:,}",
        "data": {
            "original_text": text,
            "type": cat_type,
            "category": cat_name,
            "amount": nominal,
            "subject": subject,
            "source_wallet": source,
            "dest_wallet": dest,
            "formatted": f"Rp {nominal:,}"
        }
    }

@app.get("/", response_class=HTMLResponse)
def home():
    return """

    <html><head>

                <title>AI Keuangan</title>

                <style>

                    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f4f4f9; }

                    .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }

                    .badge { background: #3498db; color: white; padding: 5px 10px; border-radius: 15px; font-size: 0.8em; }

                </style>

            </head>

        <body>

            <div class="card">

                    <h1 style="color:green;"><span class="status-dot"></span> Webhook Ready</h1>

                    <p>AI Keuangan Service is running perfectly.</p>

                    <p>Endpoint URL: <span class="code">POST /analyze</span></p>

                    <p>Testing URL: <span class="code">/docs</span></p>
                    <p>Refresh: <span class="code">/refresh-keywords</span></p>

                </div>

        </body>

    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3987)
