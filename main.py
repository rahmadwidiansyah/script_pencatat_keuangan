import os
import re
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
from thefuzz import process, fuzz

app = FastAPI()

# Mengambil API Key dari .env (Standar Keamanan Baru)
API_KEY = os.getenv("PYTHON_AI_KEY", "kunci-rahasia-v4")
api_key_header = APIKeyHeader(name="X-API-KEY")

# ==========================================
# 1. DTO STRUKTUR (Sesuai Laravel)
# ==========================================
class WalletItem(BaseModel):
    name: str
    group_type: Optional[str] = None
    keyword: Optional[str] = None

class CategoryItem(BaseModel):
    category_name: str = Field(alias="category_name")
    keyword: Optional[str] = None

class AnalyzeRequest(BaseModel):
    text: str
    wallets: List[WalletItem] = []
    categories: List[CategoryItem] = []
    # sys_map dan kawan-kawan dihapus karena Laravel TransactionResolver yang menanganinya sekarang

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def get_nominal_smart(text: str) -> Optional[float]:
    text_lower = text.lower()
    
    # Deteksi format suffix (10k, 50rb, 1.5jt)
    match_suffix = re.search(r'(\d+[.,]?\d*)\s*(rb|ribu|k|jt|juta)\b', text_lower)
    if match_suffix:
        angka = float(match_suffix.group(1).replace(",", "."))
        suffix = match_suffix.group(2)
        if suffix in ['rb', 'ribu', 'k']: return angka * 1000
        elif suffix in ['jt', 'juta']: return angka * 1000000

    # Deteksi angka murni
    nums = re.findall(r'\b\d+\b', text_lower.replace(".", "").replace(",", ""))
    valid = [float(n) for n in nums if float(n) >= 1000] # Asumsi transaksi minimal Rp1.000
    
    return max(valid) if valid else None

def extract_subject(text: str) -> Optional[str]:
    match = re.search(r'#([a-zA-Z0-9_]+)', text)
    return match.group(1) if match else None

def guess_transaction_intent(text: str, category_name: str) -> str:
    text_lower = text.lower()
    cat_lower = category_name.lower() if category_name else ""

    # 1. Deteksi Transfer
    if any(w in text_lower for w in ['transfer', 'pindah', 'mutasi', 'tf']) or 'transfer' in cat_lower:
        return 'transfer'
    
    # 2. Deteksi Hutang (Debt)
    if any(w in text_lower for w in ['ngutang', 'pinjam', 'kasbon', 'cicil']) or 'hutang' in cat_lower:
        return 'debt'
    
    # 3. Deteksi Piutang (Receivable)
    if any(w in text_lower for w in ['piutang', 'dipinjam', 'pinjemin']) or 'piutang' in cat_lower:
        return 'receivable'
    
    # 4. Deteksi Pemasukan (Income)
    if any(w in text_lower for w in ['gaji', 'dikasih', 'pemasukan', 'cair', 'nemu']) or 'pendapatan' in cat_lower or 'gaji' in cat_lower:
        return 'income'
    
    # Default Fallback
    return 'expense'

# ==========================================
# 3. MAIN ANALYZE ENDPOINT
# ==========================================
@app.post("/analyze")
async def analyze_transaction(req: AnalyzeRequest, key: str = Depends(api_key_header)):
    if key != API_KEY: 
        raise HTTPException(status_code=403, detail="Akses Ditolak: API Key tidak valid.")
    
    text_lower = req.text.lower()
    nominal = get_nominal_smart(req.text)
    subject = extract_subject(req.text)

    # A. EKSTRAKSI DOMPET (Hanya mengembalikan nama string, ID diurus Laravel)
    matched_wallets = []
    for w in req.wallets:
        # Abaikan dompet sistem, kita hanya cari dompet fisik (Asset/Liquid)
        if w.group_type == 'System':
            continue

        raw_kws = w.keyword if w.keyword and w.keyword.strip() not in ['-', ''] else w.name
        kws = [k.strip().lower() for k in raw_kws.split(',')]
        
        found = False
        # Regex Match
        for kw in kws:
            if kw and re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                matched_wallets.append((text_lower.find(kw), w.name))
                found = True
                break
        
        # Fuzzy Match Backup
        if not found:
            match = process.extractOne(text_lower, kws, scorer=fuzz.token_set_ratio)
            if match and match[1] >= 85:
                matched_wallets.append((999, w.name))

    matched_wallets.sort(key=lambda x: x[0])
    ordered_wallet_names = list(dict.fromkeys([w[1] for w in matched_wallets])) # Buang duplikat, pertahankan urutan

    # B. EKSTRAKSI KATEGORI
    best_cat_name = None
    best_cat_score = 0
    for c in req.categories:
        raw_kws = c.keyword if c.keyword and c.keyword.strip() not in ['-', ''] else c.category_name
        kws = [k.strip().lower() for k in raw_kws.split(',')]
        
        escaped = [re.escape(k) for k in kws if k]
        if escaped:
            pattern = re.compile(r'\b(?:' + "|".join(escaped) + r')\b', re.IGNORECASE)
            m = pattern.findall(text_lower)
            if m:
                score = len(m) * 100
                if score > best_cat_score:
                    best_cat_score, best_cat_name = score, c.category_name
        
        if best_cat_score == 0:
            match = process.extractOne(text_lower, kws, scorer=fuzz.token_set_ratio)
            if match and match[1] > best_cat_score:
                best_cat_score, best_cat_name = match[1], c.category_name

    if best_cat_score < 60:
        best_cat_name = None

    # C. MENENTUKAN INTENT DAN PENEMPATAN DOMPET
    intent = guess_transaction_intent(req.text, best_cat_name or "")
    
    source_wallet = ordered_wallet_names[0] if len(ordered_wallet_names) > 0 else None
    dest_wallet = ordered_wallet_names[1] if len(ordered_wallet_names) > 1 else None

    # Koreksi penempatan dompet berdasarkan intent (Khusus Income, dompet yang disebut adalah tujuan)
    if intent == 'income' and source_wallet and not dest_wallet:
        dest_wallet = source_wallet
        source_wallet = None

    # D. KALKULASI CONFIDENCE SCORE (Skor Kepercayaan Sistem)
    confidence = 0.0
    if nominal: confidence += 0.3
    if best_cat_name: confidence += 0.3
    if source_wallet or dest_wallet: confidence += 0.3
    if subject: confidence += 0.1

    confidence = min(1.0, confidence)
    
    # E. KEPUTUSAN DRAFT / CLEARED (Lebih ketat)
    # Harus ada nominal, kategori, dan setidaknya 1 dompet fisik
    is_cleared = bool(nominal and best_cat_name and (source_wallet or dest_wallet) and confidence >= 0.8)

    # KEMBALIKAN FORMAT JSON BERSIH KE LARAVEL
    return {
        "success": True,
        "amount": nominal,
        "transaction_type": intent,
        "category": best_cat_name,
        "source_wallet": source_wallet,
        "destination_wallet": dest_wallet,
        "subject": subject,
        "notes": req.text,
        "is_cleared": is_cleared,
        "confidence": confidence
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3987)