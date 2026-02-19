import re
import os
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Keuangan Pro v1.6.6")

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
# 1. KONFIGURASI DOMPET & KATEGORI
# ==========================================

WALLET_GROUPS = {
    "LIQUID": {
        "shopeepay": ["shopeepay", "spay"], # Hapus titik di depan agar regex boundary bekerja
        "seabank":   ["seabank", "sea bank"],
        "dana":      ["dana"],
        "gopay":     ["gopay", "gojek"],
        "cash":      ["cash", "dompet", "tunai", "uang cash"],
        "market pulsa": ["mcp", "saldo market", "marketpulsa"]
    },
    "INVESTMENT": {
        "emas":      ["emas", "tabungan emas", "pegadaian", "logam mulia"],
        "tabungan":  ["tabungan", "nabung", "rekening"] # Tambah bank umum
    }
}

# --- OPTIMASI B: REVERSE MAPPING (Keyword -> Wallet Key) ---
KEYWORD_TO_WALLET = {}
for group_name, wallets in WALLET_GROUPS.items():
    for wallet_key, keywords in wallets.items():
        for kw in keywords:
            KEYWORD_TO_WALLET[kw.lower()] = wallet_key

CATEGORIES_CONFIG = {
    # --- HUTANG & PIUTANG (LOGIKA BARU) ---
    ("💸 Hutang (Masuk)", "Hutang (Masuk)"): ["pinjam uang","hutang masuk", "ngutang", "pinjem"],
    ("🧾 Cicil Hutang (Keluar)", "Cicil Hutang (Keluar)"): ["bayar hutang", "hutang keluar", "cicil hutang", "pelunasan hutang", "bayar utang"],
    ("💰 Piutang (Keluar)", "Piutang (Keluar)"): ["pinjamin", "piutang keluar", "kasih pinjam" , "minjemin"],
    ("📥 Piutang (Masuk)", "Piutang (Masuk)"): ["tagih", "piutang masuk", "bayar piutang", "terima piutang", "kembali uang", "balikin uang"],

    # --- PENGELUARAN ---
     ("🍔 Makan & Minum", "Pengeluaran 🔴"): ["makan", "minum", "nasi", "sarapan", "maksi", "makan siang", "makan malam", "lauk", "warteg", "padang", "soto", "bakso", "mie ayam", "bubur", "geprek", "pecel", "penyetan", "rames", "catering", "seblak", "ketoprak", "goreng"],
    ("🍟 Jajan & Nongkrong", "Pengeluaran 🔴"): ["kopi", "ngopi", "coffee", "starbucks", "janji jiwa", "kenangan", "fore", "boba", "mixue", "chatime", "es teh", "menantea", "snack", "camilan", "jajan", "martabak", "roti", "kue", "coklat", "es krim", "gelato", "mcd", "kfc", "burger", "pizza", "hokben", "solaria", "nongkrong", "hangout", "cafe", "bioskop", "nonton", "popcorn", "gorengan"],
    ("🚗 Transportasi", "Pengeluaran 🔴"): ["bensin", "pertalite", "pertamax", "solar", "shell", "vivo", "bp", "isi bensin", "pom", "spbu", "parkir", "parkiran", "pak ogah", "valet", "tol", "e-toll", "topup emoney", "flazz", "tapcash", "brizzi", "gojek", "gocar", "grab", "grabcar", "maxim", "inwiki", "ojol", "angkot", "busway", "tj", "kereta", "krl", "mrt", "lrt", "bus", "servis", "ganti oli", "tambal ban", "cuci motor", "cuci mobil", "bengkel"],
    ("🏠 Kebutuhan Rumah & Ikan", "Pengeluaran 🔴"): ["listrik", "token", "pln", "air", "pdam", "iuran", "sampah", "keamanan", "rt", "rw", "sedot wc", "tukang", "renovasi", "lampu", "baterai", "deterjen", "sabun cuci", "pewangi", "wipol", "sunlight", "rinso", "attack", "tissue", "tisu", "kresek", "laundry", "setrika", "pelet", "pakan ikan", "akuarium", "filter", "kapas", "ikan hias"],
    ("🛒 Groceries & Stok Dapur", "Pengeluaran 🔴"): ["belanja pasar", "mentah", "sayuran", "sayur mentah", "ayam mentah", "daging", "ikan mentah", "telur", "beras", "minyak goreng", "bumbu", "bawang", "cabai", "garam", "gula", "terigu", "saus", "kecap", "santan", "mentega", "bahan kue", "frozen food", "nugget", "sosis", "air galon", "aqua galon", "vit galon", "le minerale", "gas elpiji", "lpg", "pasar", "indomaret", "alfamart", "supermarket", "hypermart", "superindo"],
    ("🛠️ Servis & Barang Hobby", "Pengeluaran 🔴"): ["servis hp", "servis laptop", "perbaikan", "elektronik", "peralatan", "furniture", "meja", "kursi", "hobi", "mainan", "koleksi", "onderdil", "alat pertukangan", "hardware"],
    ("📱 Data & Digital", "Pengeluaran 🔴"): ["pulsa", "kuota", "paket data", "telkomsel", "indosat", "xl", "tri", "axis", "wifi", "internet", "indihome", "biznet", "first media", "myrepublic", "iconnet", "netflix", "spotify", "youtube", "premium", "disney", "vidio", "wetv", "icloud", "google drive", "zoom", "langganan", "subscribe", "aplikasi", "game", "steam", "voucher game", "diamond", "topup game"],
    ("🛍️ Belanja & Fashion", "Pengeluaran 🔴"): ["baju", "celana", "kaos", "kemeja", "sepatu", "sandal", "tas", "dompet", "jaket", "hoodie", "kerudung", "jilbab", "outfit", "batik", "skincare", "makeup", "facial", "potong rambut", "cukur", "barbershop", "salon", "parfum", "deodorant", "sabun mandi", "shampo", "odol", "sikat gigi", "body wash", "tokopedia", "shopee", "lazada", "tiktok shop", "belanja", "checkout"],
    ("💊 Kesehatan", "Pengeluaran 🔴"): ["dokter", "berobat", "konsul", "rs", "rumah sakit", "klinik", "puskesmas", "bidan", "obat", "apotek", "tebus obat", "vitamin", "suplemen", "madu", "tolak angin", "paracetamol", "panadol", "minyak kayu putih", "betadine", "hansaplast", "masker", "hand sanitizer", "check up", "gigi", "kacamata", "softlens", "bpjs", "asuransi", "premi", "prudential", "allianz", "manulife"],
    ("🎁 Sosial & Sedekah", "Pengeluaran 🔴"): ["sedekah", "infaq", "zakat", "donasi", "sumbangan", "kotak amal", "masjid", "gereja", "panti", "kado", "hadiah", "gift", "kenang-kenangan", "kondangan", "amplop", "nikahan", "jenguk", "besuk", "traktir", "kasih orang", "bagi bagi", "sawer", "hampers", "thr keponakan", "angpao"],
    ("🏨 Traveling & Liburan", "Pengeluaran 🔴"): ["liburan", "jalan-jalan", "jalan jalan", "healing", "wisata", "piknik", "hotel", "penginapan", "staycation", "villa", "airbnb", "reddoorz", "oyo", "tiket pesawat", "tiket kereta", "kai", "boarding", "travel", "sewa mobil", "rental", "bus antar kota", "paspor", "visa", "itinerary", "oleh-oleh", "souvenir"],
    ("🎓 Pendidikan & Kuliah", "Pengeluaran 🔴"): ["ukt", "spp", "biaya semester", "registrasi", "daftar ulang", "uang pangkal", "gedung", "skripsi", "tesis", "disertasi", "sidang", "wisuda", "toga", "yudisium", "herregistrasi", "cuti akademik", "kursus", "bimbel", "sertifikasi", "pelatihan", "workshop", "seminar", "webinar", "bootcamp", "praktek", "magang", "internship", "lab", "perpustakaan", "fotocopy", "print", "jilid", "alat tulis", "atk", "buku pelajaran", "diktat", "modul", "e-book", "jurnal", "asrama", "bayar kuliah", "kuliah" "uang saku"],
    ("🏠 Biaya Kost & Sewa", "Pengeluaran 🔴"): ["bayar kos", "kost", "kostan", "kosan", "sewa kamar", "kontrakan", "sewa rumah", "deposit", "iuran sampah", "iuran keamanan", "parkir kos"],
    ("💸 Admin & Pajak", "Pengeluaran 🔴"): ["biaya admin", "admin bank", "pajak", "pajak stnk", "pajak motor", "pajak mobil", "pbb", "meterai", "biaya layanan", "layanan aplikasi"],
    ("❤️ Transfer Muna", "Pengeluaran 🔴"): ["pacar", "muna", "MUNA"],
    ("💳 Cicilan & Paylater", "Pengeluaran 🔴"): ["cicilan", "angsuran", "kredit", "dp", "pelunasan", "tagihan", "paylater", "spaylater", "gopaylater", "kredivo", "akulaku", "home credit", "kartu kredit", "cc", "bunga cicilan", "denda", "pinjol"],
    ("🛵 Operasional Kerja", "Pengeluaran 🔴"): ["bensin ngojol", "atribut", "helm", "jaket ojol"],

    # --- PEMASUKAN (INCOME) ---
    ("💼 Pendapatan Tetap", "Pemasukan 🟢"): ["gaji", "gajian", "salary", "payroll", "upah", "honor", "tunjangan", "thr", "bonus tahunan", "insentif", "rapel", "pesangon"],
    ("🛵 Side Job/Tambahan", "Pemasukan 🟢"): ["ngojek", "nyopi", "ngojol", "sampingan", "proyek", "freelance", "side job", "ceperan", "jualan", "dagang", "laku", "profit", "untung", "laba", "komisi", "affiliate", "adsense", "konten", "jasa", "tip", "tips", "reward", "cashback", "refund", "reimburse"],
    ("🛎️ Kiriman/TF Masuk", "Pemasukan 🟢"): ["kiriman", "orangtua", "ortu", "dapat transfer", "terima transfer", "dikirim uang", "uang masuk", "dikasih", "hadiah uang", "tombokan"],

    # --- NETRAL (Hapus Investasi dari sini karena sudah jadi Wallet) ---
    ("🔄 Pindah Saldo", "Transfer 🔵"): ["pindah", "topup", "top up", "isi saldo", "tarik", "transfer", "tf", "kirim", "simpan", "deposit", "withdraw", "wd"]
}

# --- OPTIMASI C: PRECOMPILE CATEGORY REGEX ---
CATEGORY_PATTERNS = []
for (cat, typ), keywords in CATEGORIES_CONFIG.items():
    # Sort keywords by length desc agar keyword panjang match duluan ("makan siang" > "makan")
    keywords.sort(key=len, reverse=True)
    # Escape keywords special char
    escaped = [re.escape(k) for k in keywords]
    # Gabung jadi satu regex besar: \b(keyword1|keyword2)\b
    pattern = re.compile(r'\b(?:' + "|".join(escaped) + r')\b', re.IGNORECASE)
    CATEGORY_PATTERNS.append(((cat, typ), pattern))

# ==========================================
# 2. LOGIC FUNCTIONS
# ==========================================

# --- REVISI POIN A: PARSING NOMINAL AMAN ---
def get_nominal_smart(text):
    text_lower = text.lower()

    # 1. Cek Suffix (1.5jt, 10rb, 2,5jt)
    # Regex ini support titik/koma sebagai desimal JIKA ada suffix
    match_suffix = re.search(r'(\d+[.,]?\d*)\s*(rb|ribu|k|jt|juta)\b', text_lower)

    if match_suffix:
        angka_str = match_suffix.group(1).replace(",", ".") # Normalisasi koma jadi titik desimal
        suffix = match_suffix.group(2)

        try:
            angka = float(angka_str)
            if suffix in ['rb', 'ribu', 'k']:
                return int(angka * 1000)
            elif suffix in ['jt', 'juta']:
                return int(angka * 1000000)
        except ValueError:
            pass # Jika gagal parse float, lanjut ke bawah

    # 2. Fallback: Angka tanpa suffix (Ex: 15000, 20.000)
    # Hapus titik (separator ribuan) dan koma (separator desimal yang gak penting di angka bulat)
    clean_text = text_lower.replace(".", "").replace(",", "")
    all_numbers = re.findall(r'\b\d+\b', clean_text)

    # Filter angka >= 1000 (kecuali nominal kecil memang valid untukmu, bisa disesuaikan)
    valid_numbers = [int(n) for n in all_numbers if int(n) >= 1000]

    return max(valid_numbers) if valid_numbers else None

# --- REVISI POIN B: DETEKSI WALLET OPTIMIZED ---
def detect_wallets_ordered(text):
    text_lower = text.lower()
    matches = []

    # Loop melalui dictionary yang sudah di-flatten (lebih efisien)
    for kw, wallet_key in KEYWORD_TO_WALLET.items():
        # Gunakan regex boundary \b untuk match kata utuh
        # Ex: "perdana" tidak akan match "dana"
        pattern = r'\b' + re.escape(kw) + r'\b'

        for m in re.finditer(pattern, text_lower):
            matches.append((m.start(), wallet_key))

    # Sort berdasarkan posisi kemunculan di teks (Source -> Dest)
    matches.sort(key=lambda x: x[0])

    ordered = []
    seen = set()
    for _, w in matches:
        if w not in seen:
            ordered.append(w)
            seen.add(w)
    return ordered

def extract_subject(text):
    match = re.search(r'#([a-zA-Z0-9_]+)', text) # Tangkap #nama (alphanumeric only)
    return match.group(1).upper() if match else None

# --- REVISI POIN C: DETEKSI KATEGORI CEPAT ---
def detect_category_basic(text):
    # Tidak perlu text.lower() lagi karena regex sudah IGNORECASE
    best_cat, best_type, best_score = "❓ Lain-lain", None, 0

    for (cat, typ), pattern in CATEGORY_PATTERNS:
        # findall jauh lebih cepat daripada loop keyword manual
        matches = pattern.findall(text)
        score = len(matches)

        if score > best_score:
            best_score, best_cat, best_type = score, cat, typ

    if best_score == 0:
        text_lower = text.lower()
        if any(x in text_lower for x in ["beli", "bayar", "jajan", "-"]):
            best_type = "Pengeluaran 🔴"
            best_cat = "❓ Lain-lain (Pengeluaran)"
        elif any(x in text_lower for x in ["terima", "dapat", "masuk", "+"]):
            best_type = "Pemasukan 🟢"
            best_cat = "❓ Lain-lain (Pemasukan)"
        else:
            best_type = "Transfer 🔵"
            best_cat = "🔄 Pindah Saldo"

    return best_cat, best_type

def wallet_get_group(wallet_key):
    if not wallet_key: return None
    wk = wallet_key.lower()
    for gname, wallets in WALLET_GROUPS.items():
        if wk in wallets:
            return gname
    return None

# ==========================================
# 3. CORE ANALYZE
# ==========================================

@app.post("/analyze")
async def analyze_transaction(request: ChatRequest, api_key: str = Depends(get_api_key)):
    text = request.text
    text_lower = text.lower()
    nominal = get_nominal_smart(text)
    wallets = detect_wallets_ordered(text)
    subject = extract_subject(text)
    cat_name, cat_type = detect_category_basic(text)

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

                </div>

        </body>

    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3987)
