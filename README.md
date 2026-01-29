# API Invoice Watermark LUNAS

API ini digunakan untuk menambahkan watermark **“LUNAS”** secara otomatis pada file **PDF invoice**.  
Watermark ditempatkan secara **adaptif di area TOTAL/DUE**, dengan **center presisi (horizontal & vertical)**, rotasi, dan opacity.

Teknologi:
- Node.js (Express) – HTTP API
- Python (PyMuPDF / fitz) – PDF processing & rendering watermark

---

## ✨ Fitur

- Watermark teks **LUNAS**
- Posisi otomatis di area total invoice
- Center presisi berbasis font metrics (bukan kira-kira)
- Rotasi & opacity
- Support Windows & Ubuntu
- Input: PDF
- Output: PDF

---
```powershell
npm install

.venv\Scripts\activate
python -m venv .venv
pip install -U pip
pip install -r requirements.txt
```
``` bash
copy .env.example .env
```

```bash
npm start
```
