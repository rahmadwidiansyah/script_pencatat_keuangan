import re
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Inisialisasi App
app = FastAPI(title="AI Keuangan Service (Smart Ribuan)")

class ChatRequest(BaseModel):
    text: str

# ==========================================
# 1. WEB UI
# ==========================================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <title>AI Keuangan</title>
            <style>
                body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f4f4f9; }
                .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }
                .badge { background: #3498db; color: white; padding: 5px 10px; border-radius: 15px; font-size: 0.8em; }
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

# ==========================================
# 2. CONFIG & LOGIC
# ==========================================
CATEGORIES_CONFIG = {
    ("🍔 Makan & Minum", "Pengeluaran 🔴"): ["makan", "minum", "nasi", "sarapan", "maksi", "makan siang", "makan malam", "lauk", "sayur", "beras", "ayam", "ikan", "telur", "tempe", "tahu", "warteg", "padang", "soto", "bakso", "mie ayam", "bubur", "geprek", "pecel", "penyetan", "rames", "catering", "masak", "bumbu", "dapur", "air galon", "aqua", "refill", "prasmanan", "gorengan", "seblak", "ketoprak"],
    ("🍟 Jajan & Nongkrong", "Pengeluaran 🔴"): ["kopi", "ngopi", "coffee", "starbucks", "janji jiwa", "kenangan", "fore", "boba", "mixue", "chatime", "es teh", "teh solo", "menantea", "snack", "camilan", "jajan", "martabak", "roti", "kue", "coklat", "es krim", "gelato", "mcd", "kfc", "burger", "pizza", "hokben", "solaria", "nongkrong", "hangout", "cafe", "bioskop", "nonton", "popcorn"],
    ("🚗 Transportasi", "Pengeluaran 🔴"): ["bensin", "pertalite", "pertamax", "solar", "shell", "vivo", "bp", "isi bensin", "pom", "spbu", "parkir", "parkiran", "pak ogah", "valet", "tol", "e-toll", "topup emoney", "flazz", "tapcash", "brizzi", "gojek", "gocar", "grab", "grabcar", "maxim", "inwiki", "ojol", "angkot", "busway", "tj", "kereta", "krl", "mrt", "lrt", "bus", "servis", "ganti oli", "tambal ban", "cuci motor", "cuci mobil", "bengkel"],
    ("🏠 Kebutuhan Rumah & Ikan", "Pengeluaran 🔴"): ["listrik", "token", "pln", "air", "pdam", "iuran", "sampah", "keamanan", "rt", "rw", "gas", "elpiji", "lpg", "sedot wc", "tukang", "renovasi", "lampu", "baterai", "deterjen", "sabun cuci", "pewangi", "wipol", "sunlight", "rinso", "attack", "tissue", "tisu", "kresek", "laundry", "setrika", "pelet", "pakan ikan", "akuarium", "filter", "kapas", "ikan hias"],
    ("📱 Data & Digital", "Pengeluaran 🔴"): ["pulsa", "kuota", "paket data", "telkomsel", "indosat", "xl", "tri", "axis", "wifi", "internet", "indihome", "biznet", "first media", "myrepublic", "iconnet", "netflix", "spotify", "youtube", "premium", "disney", "vidio", "wetv", "icloud", "google drive", "zoom", "langganan", "subscribe", "aplikasi", "game", "steam", "voucher game", "diamond", "topup game"],
    ("🛍️ Belanja & Fashion", "Pengeluaran 🔴"): ["baju", "celana", "kaos", "kemeja", "sepatu", "sandal", "tas", "dompet", "jaket", "hoodie", "kerudung", "jilbab", "outfit", "batik", "skincare", "makeup", "facial", "potong rambut", "cukur", "barbershop", "salon", "parfum", "deodorant", "sabun mandi", "shampo", "odol", "sikat gigi", "body wash", "tokopedia", "shopee", "lazada", "tiktok shop", "belanja", "checkout"],
    ("💊 Kesehatan", "Pengeluaran 🔴"): ["dokter", "berobat", "konsul", "rs", "rumah sakit", "klinik", "puskesmas", "bidan", "obat", "apotek", "tebus obat", "vitamin", "suplemen", "madu", "tolak angin", "paracetamol", "panadol", "minyak kayu putih", "betadine", "hansaplast", "masker", "hand sanitizer", "check up", "gigi", "kacamata", "softlens", "bpjs", "asuransi", "premi", "prudential", "allianz", "manulife"],
    ("🎁 Sosial & Sedekah", "Pengeluaran 🔴"): ["sedekah", "infaq", "zakat", "donasi", "sumbangan", "kotak amal", "masjid", "gereja", "panti", "kado", "hadiah", "gift", "kenang-kenangan", "kondangan", "amplop", "nikahan", "jenguk", "besuk", "traktir", "kasih orang", "bagi bagi", "sawer", "hampers", "thr keponakan", "angpao"],
    ("🏨 Traveling & Liburan", "Pengeluaran 🔴"): ["liburan", "jalan-jalan", "jalan jalan", "healing", "wisata", "piknik", "hotel", "penginapan", "staycation", "villa", "airbnb", "reddoorz", "oyo", "tiket pesawat", "tiket kereta", "kai", "boarding", "travel", "sewa mobil", "rental", "bus antar kota", "paspor", "visa", "itinerary", "oleh-oleh", "souvenir"],
    ("🎓 Pendidikan & Kuliah", "Pengeluaran 🔴"): ["ukt", "spp", "biaya semester", "registrasi", "daftar ulang", "uang pangkal", "gedung", "skripsi", "tesis", "disertasi", "sidang", "wisuda", "toga", "yudisium", "herregistrasi", "cuti akademik", "kursus", "bimbel", "sertifikasi", "pelatihan", "workshop", "seminar", "webinar", "bootcamp", "praktek", "magang", "internship", "lab", "perpustakaan", "fotocopy", "print", "jilid", "alat tulis", "atk", "buku pelajaran", "diktat", "modul", "e-book", "jurnal", "asrama", "kost", "uang saku"]
    ("🏠 Biaya Kost & Sewa", "Pengeluaran 🔴"): ["bayar kos", "kost", "kostan", "kosan", "sewa kamar", "kontrakan", "sewa rumah", "deposit", "iuran sampah", "iuran keamanan", "parkir kos"],
    ("❤️ Transfer Muna", "Pengeluaran 🔴"): ["TF", "tf", "muna", "MUNA"],
    ("💳 Cicilan & Paylater", "Pengeluaran 🔴"): ["cicilan", "angsuran", "kredit", "dp", "pelunasan", "tagihan", "paylater", "spaylater", "gopaylater", "kredivo", "akulaku", "home credit", "kartu kredit", "cc", "bunga cicilan", "denda", "pinjol", "hutang"],
    ("💼 Pendapatan Tetap", "Pemasukan 🟢"): ["gaji", "gajian", "salary", "payroll", "upah", "honor", "tunjangan", "thr", "bonus tahunan", "insentif", "rapel", "pesangon"],
    ("🛵 Side Job/Tambahan", "Pemasukan 🟢"): ["ngojek", "nyopi", "ngojol", "sampingan", "proyek", "freelance", "side job", "ceperan", "jualan", "dagang", "laku", "profit", "untung", "laba", "komisi", "affiliate", "adsense", "konten", "jasa", "tip", "tips", "reward", "cashback", "refund", "reimburse"],
    ("🛎️ Kiriman/TF Masuk", "Pemasukan 🟢"): ["kiriman", "orangtua", "ortu", "dapat transfer", "terima transfer", "dikirim uang", "uang masuk", "dikasih", "hadiah uang", "tombokan"],
    ("🔄 Pindah Saldo", "Netral ⚪"): ["topup", "top up", "isi saldo", "tarik tunai", "ambil uang", "atm", "pindah saldo", "transfer ke sendiri", "tf ke sendiri", "isi gopay", "isi ovo", "isi dana", "isi shopeepay", "topup ewallet"]
}

def get_nominal_smart(text):
    """
    Logika:
    1. Cek Suffix (15k, 20rb) -> Valid
    2. Cek Prefix (Rp 20000) -> Valid
    3. Cek Angka Polos (20000, 12300) -> Valid JIKA >= 1000
    """
    # Hapus titik dan koma agar "12.300" jadi "12300"
    clean_text = text.lower().replace(".", "").replace(",", "")
    
    # --- Priority 1: Suffix (k, rb, juta) ---
    match_suffix = re.search(r'(\d+)\s*(rb|ribu|k|jt|juta)\b', clean_text)
    if match_suffix:
        angka = int(match_suffix.group(1))
        suffix = match_suffix.group(2)
        if suffix in ['rb', 'ribu', 'k']: return angka * 1000
        elif suffix in ['jt', 'juta']: return angka * 1000000
    
    # --- Priority 2: Prefix (Rp) ---
    match_rp = re.search(r'rp\s*(\d+)', clean_text)
    if match_rp:
        return int(match_rp.group(1))

    # --- Priority 3: Angka Polos (Harus Ribuan) ---
    # Cari semua angka yang berdiri sendiri
    all_numbers = re.findall(r'\b\d+\b', clean_text)
    
    # Filter: Hanya ambil angka yang >= 1000
    valid_numbers = [int(n) for n in all_numbers if int(n) >= 1000]
    
    if valid_numbers:
        # Mengambil angka valid terbesar (asumsi harga biasanya angka terbesar dalam kalimat)
        # Contoh: "Beli 2 ayam 25000" -> 2 diabaikan, 25000 diambil.
        return max(valid_numbers)

    return None

def detect_category_and_type(text):
    best_category = "❓ Lain-lain"
    best_type = None 
    best_score = 0
    
    for (kategori_name, jenis_transaksi), keywords in CATEGORIES_CONFIG.items():
        score = 0
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text): score += 1
        
        if score > best_score:
            best_score = score
            best_category = kategori_name
            best_type = jenis_transaksi
    
    # Fallback Logic
    if best_score == 0:
        if any(x in text for x in ["beli", "bayar", "jajan", "keluar"]):
            best_type = "Pengeluaran 🔴"
            best_category = "❓ Lain-lain (Pengeluaran)"
        elif any(x in text for x in ["dapat", "terima", "masuk"]):
            best_type = "Pemasukan 🟢"
            best_category = "❓ Lain-lain (Pemasukan)"
        else:
            best_type = None 
            best_category = "❓ Tidak Diketahui"

    return best_category, best_type

# ==========================================
# 3. API ENDPOINT
# ==========================================
@app.post("/analyze")
def analyze_transaction(request: ChatRequest):
    text = request.text.lower()
    
    kategori, jenis = detect_category_and_type(text)
    nominal = get_nominal_smart(text)

    # ============================
    # VALIDASI
    # ============================
    is_valid = True
    error_messages = []

    if nominal is None:
        is_valid = False
        error_messages.append("Nominal tidak ditemukan atau terlalu kecil (minimal 1000 jika tanpa 'rb/k').")

    if jenis is None:
        is_valid = False
        error_messages.append("Jenis transaksi tidak jelas (masuk/keluar?).")

    # ============================
    # RESPONSE JSON (Flagging Opsi B)
    # ============================
    if is_valid:
        return {
            "success": True,
            "message": f"Berhasil mencatat {jenis} Rp {nominal:,}",
            "data": {
                "original_text": request.text,
                "type": jenis,
                "category": kategori,
                "amount": nominal,
                "amount_formatted": f"Rp {nominal:,}".replace(",", ".")
            }
        }
    else:
        return {
            "success": False,
            "message": " | ".join(error_messages),
            "data": None,
            "hint": "Coba format: 'Makan 15000' atau 'Beli pulsa 12300'"
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
