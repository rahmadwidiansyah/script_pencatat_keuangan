from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import List, Optional
import re
import uvicorn
from thefuzz import process, fuzz

app = FastAPI()
API_KEY = "kunci-rahasia-v4"
api_key_header = APIKeyHeader(name="X-API-KEY")

class ItemData(BaseModel):
    id: int
    name: str
    type_id: Optional[int] = None
    group_type: Optional[str] = None
    keyword: Optional[str] = None

class SysMap(BaseModel):
    merchant_id: Optional[int] = None
    external_id: Optional[int] = None
    hutang_id: Optional[int] = None
    piutang_id: Optional[int] = None

class TypeMap(BaseModel):
    income_ids: List[int] = []
    expense_ids: List[int] = []
    transfer_ids: List[int] = []

class CatMap(BaseModel):
    hutang_ids: List[int] = []
    piutang_ids: List[int] = []

class AnalyzeRequest(BaseModel):
    text: str
    wallets: List[ItemData]
    categories: List[ItemData]
    sys_map: SysMap
    type_map: TypeMap
    cat_map: CatMap

def get_nominal_smart(text):
    text_lower = text.lower()
    match_suffix = re.search(r'(\d+[.,]?\d*)\s*(rb|ribu|k|jt|juta)\b', text_lower)
    if match_suffix:
        angka = float(match_suffix.group(1).replace(",", "."))
        suffix = match_suffix.group(2)
        if suffix in ['rb', 'ribu', 'k']: return int(angka * 1000)
        elif suffix in ['jt', 'juta']: return int(angka * 1000000)

    nums = re.findall(r'\b\d+\b', text_lower.replace(".", "").replace(",", ""))
    valid = [int(n) for n in nums if int(n) >= 1000]
    return max(valid) if valid else None

def extract_subject(text):
    match = re.search(r'#([a-zA-Z0-9_]+)', text)
    return match.group(1) if match else "Pihak Terkait"

@app.post("/analyze")
async def analyze_transaction(req: AnalyzeRequest, key: str = Depends(api_key_header)):
    if key != API_KEY: raise HTTPException(status_code=403)
    
    text_lower = req.text.lower()
    nominal = get_nominal_smart(req.text)
    subject = extract_subject(req.text)

    # =========================================================================
    # 1. DETEKSI DOMPET (Regex + Jaring Pengaman Fuzzy Tingkat Tinggi)
    # =========================================================================
    matches = []
    for w in req.wallets:
        # BUG FIX: Cegah keyword strip ('-') atau kosong bikin deteksi buta huruf
        raw_kws = w.keyword if (w.keyword and w.keyword.strip() not in ['-', '']) else w.name
        kws = [k.strip().lower() for k in raw_kws.split(',')]
        
        found = False
        for kw in kws:
            if not kw: continue
            for m in re.finditer(r'\b' + re.escape(kw) + r'\b', text_lower):
                matches.append((m.start(), w))
                found = True
        
        # JARING PENGAMAN: Kalau regex gagal, kita paksa scan dompet fisik pakai Fuzzy
        if not found and w.group_type in ['Asset', 'Liquid']:
            match = process.extractOne(text_lower, kws, scorer=fuzz.token_set_ratio)
            if match and match[1] >= 85: # Tingkat kemiripan 85% ke atas
                matches.append((999, w)) # Beri index akhir agar dompet regex tetap diutamakan

    matches.sort(key=lambda x: x[0])
    ordered_wallets = []
    seen = set()
    for _, w in matches:
        if w.id not in seen:
            ordered_wallets.append(w)
            seen.add(w.id)

    # =========================================================================
    # 2. DETEKSI KATEGORI
    # =========================================================================
    best_cat = None
    best_cat_score = 0
    for c in req.categories:
        raw_kws = c.keyword if (c.keyword and c.keyword.strip() not in ['-', '']) else c.name
        kws = [k.strip().lower() for k in raw_kws.split(',')]
        
        escaped = [re.escape(k) for k in kws if k]
        if escaped:
            pattern = re.compile(r'\b(?:' + "|".join(escaped) + r')\b', re.IGNORECASE)
            m = pattern.findall(text_lower)
            if m:
                score = len(m) * 100
                if score > best_cat_score:
                    best_cat_score, best_cat = score, c
        
        if best_cat_score == 0:
            match = process.extractOne(text_lower, kws, scorer=fuzz.token_set_ratio)
            if match and match[1] > best_cat_score:
                best_cat_score, best_cat = match[1], c

    if best_cat_score < 60:
        best_cat = None

    # =========================================================================
    # 3. MAPPING SYSTEM WALLET (Kombinasi Peta Laravel + Backup Tebakan Python)
    # =========================================================================
    merch_id = req.sys_map.merchant_id or next((w.id for w in req.wallets if w.group_type == 'System' and any(x in w.name.lower() for x in ['merchant', 'pengeluaran', 'keluar', 'belanja', 'toko'])), None)
    ext_id = req.sys_map.external_id or next((w.id for w in req.wallets if w.group_type == 'System' and any(x in w.name.lower() for x in ['external', 'pemasukan', 'masuk', 'income', 'luar'])), None)
    hut_id = req.sys_map.hutang_id or next((w.id for w in req.wallets if w.group_type == 'System' and 'hutang' in w.name.lower()), None)
    piu_id = req.sys_map.piutang_id or next((w.id for w in req.wallets if w.group_type == 'System' and 'piutang' in w.name.lower()), None)

    # =========================================================================
    # 4. RUTING OTOMATIS (Bebas Hardcode)
    # =========================================================================
    source_id, dest_id = None, None
    type_id = best_cat.type_id if best_cat else None

    # Backup logic jika Laravel gagal map tipe (misal karena nama Tipenya "Mutasi")
    is_transfer = (type_id in req.type_map.transfer_ids) or (best_cat and any(x in best_cat.name.lower() for x in ['transfer', 'pindah', 'mutasi']))
    is_income = (type_id in req.type_map.income_ids) or (best_cat and any(x in best_cat.name.lower() for x in ['pemasukan', 'gaji', 'bonus', 'masuk']))

    if best_cat:
        wallet_1 = ordered_wallets[0].id if len(ordered_wallets) > 0 else None
        wallet_2 = ordered_wallets[1].id if len(ordered_wallets) > 1 else None

        cat_name = best_cat.name.lower()

        # A. Logika Hutang 
        if best_cat.id in req.cat_map.hutang_ids or 'hutang' in cat_name:
            if any(w in text_lower for w in ["bayar", "cicil", "lunas"]):
                source_id, dest_id = wallet_1, hut_id
            else: 
                source_id, dest_id = hut_id, wallet_1
                
        # B. Logika Piutang 
        elif best_cat.id in req.cat_map.piutang_ids or 'piutang' in cat_name:
            if any(w in text_lower for w in ["bayar", "terima", "lunas", "dapat", "nagih"]):
                source_id, dest_id = piu_id, wallet_1
            else: 
                source_id, dest_id = wallet_1, piu_id

        # C. Logika Transfer (Butuh 2 dompet)
        elif is_transfer or len(ordered_wallets) >= 2:
            source_id = wallet_1
            dest_id = wallet_2
            
        # D. Logika Pemasukan
        elif is_income:
            source_id, dest_id = ext_id, wallet_1
            
        # E. Logika Pengeluaran
        else:
            source_id, dest_id = wallet_1, merch_id

    # Validasi Akhir
    is_cleared = bool(nominal and source_id and dest_id and best_cat)

    return {
        "success": True,
        "amount": nominal,
        "category_id": best_cat.id if best_cat else None,
        "type_id": type_id,
        "source_wallet_id": source_id,
        "dest_wallet_id": dest_id,
        "subject": subject,
        "is_cleared": is_cleared
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3987)