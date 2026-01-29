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


WINDOWS
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


```bash
curl -X POST "http://localhost:3200/watermark/lunas" ^
  -F "file=@D:\Documents\invoice.pdf;type=application/pdf" ^
  -o invoice-LUNAS.pdf
```
OR
```bash
curl -X POST "http://localhost:3200/watermark/lunas" ^
  -F "file=@D:\Documents\invoice.pdf;type=application/pdf" ^
  -F "options={
    \"text\":\"LUNAS\",
    \"rotate\":-20,
    \"opacity\":0.18,
    \"wmWidthPctOfContent\":0.40,
    \"shiftXPctOfContent\":0.065,
    \"shiftYPctOfContent\":-0.020
  }" ^
  -o invoice-LUNAS.pdf
```


LINUX
---
```bash
sudo apt update
sudo apt install -y nodejs npm python3 python3-pip python3-venv git
```

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

npm start
```


```bash
curl -X POST "http://localhost:3200/watermark/lunas" \
  -F "file=@/home/user/invoice.pdf;type=application/pdf" \
  -o invoice-LUNAS.pdf
```
OR 
```bash
curl -X POST "http://localhost:3200/watermark/lunas" \
  -F "file=@/home/user/invoice.pdf;type=application/pdf" \
  -F 'options={
    "text":"LUNAS",
    "rotate":-20,
    "opacity":0.18,
    "wmWidthPctOfContent":0.40,
    "shiftXPctOfContent":0.065,
    "shiftYPctOfContent":-0.020
  }' \
  -o invoice-LUNAS.pdf
```
