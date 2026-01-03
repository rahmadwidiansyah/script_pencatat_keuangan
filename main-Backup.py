import re
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Inisialisasi App
app = FastAPI(title="AI Keuangan Service")

# Model data yang diterima
class ChatRequest(BaseModel):
    text: str

# ==========================================
# 1. WEB UI (Halaman Depan)
# ==========================================
@app.get("/", response_class=HTMLResponse)
def home():
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>AI Keuangan Status</title>
            <style>
                body { font-family: 'Segoe UI', sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0f2f5; margin: 0; }
                .card { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; }
                .status-dot { height: 15px; width: 15px; background-color: #2ecc71; border-radius: 50%; display: inline-block; margin-right: 10px; }
                h1 { color: #333; margin: 0; display: flex; align-items: center; justify-content: center; }
                p { color: #666; margin-top: 10px; }
                .code { background: #eee; padding: 5px 10px; border-radius: 5px; font-family: monospace; font-size: 0.9em; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1><span class="status-dot"></span> Webhook Ready</h1>
                <p>AI Keuangan Service is running perfectly.</p>
                <p>Endpoint URL: <span class="code">POST /analyze</span></p>
            </div>
        </body>
    </html>
    """
    return html_content

# ==========================================
# 2. LOGIC AI (Config & Functions)
# ==========================================
CATEGORIES_CONFIG = {
    ("🍔 Makan & Minum", "Pengeluaran 🔴"): ["makan", "minum", "nasi", "sarapan", "maksi", "makan siang", "makan malam", "lauk", "sayur", "beras", "ayam", "ikan", "telur", "tempe", "tahu", "warteg", "padang", "soto", "bakso", "mie ayam", "bubur", "geprek", "pecel", "penyetan", "rames", "catering", "masak", "bumbu", "dapur", "air galon", "aqua", "refill", "prasmanan", "gorengan", "seblak", "ketoprak"],
    ("🍟 Jajan & Nongkrong", "Pengeluaran 🔴"): ["kopi", "ngopi", "coffee", "starbucks", "janji jiwa", "kenangan", "fore", "boba", "mixue", "chatime", "es teh", "teh solo", "menantea", "snack", "camilan", "jajan", "martabak", "roti", "kue", "coklat", "es krim", "gelato", "mcd", "kfc", "burger", "pizza", "hokben", "solaria", "nongkrong", "hangout", "cafe", "bioskop", "nonton", "tiket", "popcorn"],
    ("🚗 Transportasi", "Pengeluaran 🔴"): ["bensin", "pertalite", "pertamax", "solar", "shell", "vivo", "bp", "isi bensin", "pom", "spbu", "parkir", "parkiran", "pak ogah", "valet", "tol", "e-toll", "topup emoney", "flazz", "tapcash", "brizzi", "gojek", "gocar", "grab", "grabcar", "maxim", "inwiki", "ojol", "angkot", "busway", "tj", "kereta", "krl", "mrt", "lrt", "bus", "servis", "ganti oli", "tambal ban", "cuci motor", "cuci mobil", "bengkel"],
    ("🏠 Kebutuhan Rumah & Ikan", "Pengeluaran 🔴"): ["listrik", "token", "pln", "air", "pdam", "iuran", "sampah", "keamanan", "rt", "rw", "gas", "elpiji", "lpg", "sedot wc", "tukang", "renovasi", "lampu", "baterai", "deterjen", "sabun cuci", "pewangi", "wipol", "sunlight", "rinso", "attack", "tissue", "tisu", "kresek", "laundry", "setrika", "pelet", "pakan ikan", "akuarium", "filter", "kapas", "ikan hias"],
    ("📱 Data & Digital", "Pengeluaran 🔴"): ["pulsa", "kuota", "paket data", "telkomsel", "indosat", "xl", "tri", "axis", "wifi", "internet", "indihome", "biznet", "first media", "myrepublic", "iconnet", "netflix", "spotify", "youtube", "premium", "disney", "vidio", "wetv", "icloud", "google drive", "zoom", "langganan", "subscribe", "aplikasi", "game", "steam", "voucher game", "diamond", "topup game"],
    ("🛍️ Belanja & Fashion", "Pengeluaran 🔴"): ["baju", "celana", "kaos", "kemeja", "sepatu", "sandal", "tas", "dompet", "jaket", "hoodie", "kerudung", "jilbab", "outfit", "batik", "skincare", "makeup", "facial", "potong rambut", "cukur", "barbershop", "salon", "parfum", "deodorant", "sabun mandi", "shampo", "odol", "sikat gigi", "body wash", "tokopedia", "shopee", "lazada", "tiktok shop", "belanja", "checkout"],
    ("💊 Kesehatan", "Pengeluaran 🔴"): ["dokter", "berobat", "konsul", "rs", "rumah sakit", "klinik", "puskesmas", "bidan", "obat", "apotek", "tebus obat", "vitamin", "suplemen", "madu", "tolak angin", "paracetamol", "panadol", "minyak kayu putih", "betadine", "hansaplast", "masker", "hand sanitizer", "check up", "gigi", "kacamata", "softlens", "bpjs", "asuransi", "premi", "prudential", "allianz", "manulife"],
    ("🎁 Sosial & Sedekah", "Pengeluaran 🔴"): ["sedekah", "infaq", "zakat", "donasi", "sumbangan", "kotak amal", "masjid", "gereja", "panti", "kado", "hadiah", "gift", "kenang-kenangan", "kondangan", "amplop", "nikahan", "jenguk", "besuk", "traktir", "kasih orang", "bagi bagi", "sawer", "hampers", "thr keponakan", "angpao"],
    ("💳 Cicilan & Paylater", "Pengeluaran 🔴"): ["cicilan", "angsuran", "kredit", "dp", "pelunasan", "tagihan", "paylater", "spaylater", "gopaylater", "kredivo", "akulaku", "home credit", "kartu kredit", "cc", "bunga cicilan", "denda", "pinjol", "hutang"],
    ("💼 Pendapatan Tetap", "Pemasukan 🟢"): ["gaji", "gajian", "salary", "payroll", "upah", "honor", "tunjangan", "thr", "bonus tahunan", "insentif", "rapel", "pesangon"],
    ("🛵 Side Job/Tambahan", "Pemasukan 🟢"): ["ngojek", "nyopi", "proyek", "freelance", "side job", "ceperan", "jualan", "dagang", "laku", "profit", "untung", "laba", "komisi", "affiliate", "adsense", "konten", "jasa", "tip", "tips", "reward", "cashback", "refund", "reimburse"],
    ("🛎️ Kiriman/TF Masuk", "Pemasukan 🟢"): ["kiriman", "orangtua", "ortu", "dapat transfer", "terima transfer", "dikirim uang", "uang masuk", "dikasih", "hadiah uang", "tombokan"],
    ("🔄 Pindah Saldo", "Netral ⚪"): ["topup", "top up", "isi saldo", "tarik tunai", "ambil uang", "atm", "pindah saldo", "transfer ke sendiri", "tf ke sendiri", "isi gopay", "isi ovo", "isi dana", "isi shopeepay", "topup ewallet"]
}

def get_nominal_smart(text):
    clean_text = text.lower().replace(".", "").replace(",", "")
    match_currency = re.search(r'\b(\d+)\s*(rb|ribu|k|jt|juta)\b', clean_text)
    if match_currency:
        angka = int(match_currency.group(1))
        suffix = match_currency.group(2)
        if suffix in ['rb', 'ribu', 'k']: return angka * 1000
        elif suffix in ['jt', 'juta']: return angka * 1000000
    all_numbers = re.findall(r'\b\d+\b', clean_text)
    if all_numbers:
        numbers = [int(n) for n in all_numbers]
        valid_prices = [n for n in numbers if n >= 500]
        if valid_prices: return max(valid_prices)
        elif numbers: return max(numbers)
    return None

def detect_category_and_type(text):
    best_category = "❓ Lain-lain"
    best_type = "Perlu Cek Manual"
    best_score = 0
    for (kategori_name, jenis_transaksi), keywords in CATEGORIES_CONFIG.items():
        score = 0
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text): score += 1
        if score > best_score:
            best_score = score
            best_category = kategori_name
            best_type = jenis_transaksi
    if best_score == 0:
        if any(x in text for x in ["beli", "bayar", "jajan"]): best_type = "Pengeluaran 🔴"
        elif any(x in text for x in ["dapat", "terima", "masuk"]): best_type = "Pemasukan 🟢"
        else: best_type = "❓ Tidak Diketahui"
        best_category = f"❓ Lain-lain ({best_type})"
    return best_category, best_type, best_score

# ==========================================
# 3. API ENDPOINT (Webhook)
# ==========================================
@app.post("/analyze")
def analyze_transaction(request: ChatRequest):
    text = request.text.lower()
    kategori, jenis, score = detect_category_and_type(text)
    nominal = get_nominal_smart(text)
    return {
        "status": "OK" if nominal else "WARNING_NOMINAL_NOT_FOUND",
        "original_text": request.text,
        "type": jenis,
        "category": kategori,
        "amount": nominal if nominal else 0,
        "amount_formatted": f"Rp {nominal:,}".replace(",", ".") if nominal else "Rp 0",
        "debug_score": score
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
