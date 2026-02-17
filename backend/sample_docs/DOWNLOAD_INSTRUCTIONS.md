# Dataset Download Instructions

## Status

### CORD Dataset (Receipts) - ✓ COMPLETE
- **Location**: `receipts/`
- **Files**: 30 receipt PDFs + images + ground truth JSON
- **Source**: Hugging Face `naver-clova-ix/cord-v2`
- **Status**: Ready for use

### SROIE Dataset (Invoices) - Manual Download Required

The SROIE dataset requires manual download. Choose one of these options:

#### Option 1: Download from Kaggle (Recommended)

1. **Create Kaggle Account** (if you don't have one)
   - Visit https://www.kaggle.com/
   - Sign up for free

2. **Download Dataset**
   - Visit: https://www.kaggle.com/datasets/urbikn/sroie-datasetv2
   - Click the "Download" button (requires login)
   - Extract the ZIP file

3. **Select Samples**
   - Choose 20-30 diverse invoice images from the dataset
   - Look for varied layouts, different stores, quality levels
   - Copy them to `backend/sample_docs/invoices/`

4. **Convert to PDF** (if needed)
   ```python
   from PIL import Image
   import os
   
   for filename in os.listdir('invoices'):
       if filename.endswith(('.png', '.jpg', '.jpeg')):
           img = Image.open(f'invoices/{filename}')
           if img.mode != 'RGB':
               img = img.convert('RGB')
           pdf_name = filename.rsplit('.', 1)[0] + '.pdf'
           img.save(f'invoices/{pdf_name}', 'PDF')
   ```

#### Option 2: Use Kaggle API

```bash
# Install Kaggle CLI
pip install kaggle

# Get API credentials
# 1. Go to https://www.kaggle.com/settings
# 2. Click "Create New API Token"
# 3. Save kaggle.json to ~/.kaggle/ (Linux/Mac) or C:\Users\<username>\.kaggle\ (Windows)

# Download dataset
kaggle datasets download -d urbikn/sroie-datasetv2

# Extract
unzip sroie-datasetv2.zip -d sroie_data

# Copy 20-30 samples to invoices/
# Then convert to PDF using the Python script above
```

#### Option 3: Use CORD Receipts as "Invoices" (For Testing)

If you just want to test the extraction pipeline quickly:

```bash
# Copy some CORD receipts to invoices folder
cd backend/sample_docs
cp receipts/receipt_0{10..19}.pdf invoices/
# Rename them
cd invoices
for f in receipt_*.pdf; do mv "$f" "${f/receipt/invoice}"; done
```

This will give you invoice-like documents to test with. While not true invoices, CORD receipts have similar structure (merchant info, line items, totals) and will demonstrate the extraction capabilities.

## Alternative Invoice Datasets

If SROIE is not accessible, consider these alternatives:

1. **RVL-CDIP Invoice Subset**
   - 25,000 invoice images
   - Available on Hugging Face: `aharley/rvl_cdip`
   - Filter for "invoice" class

2. **DocBank**
   - 500K document pages including financial forms
   - Available at: https://doc-analysis.github.io/docbank-page/

3. **Use existing sample invoices**
   - The repo already has 2 sample invoices in `backend/sample_docs/`:
     - `vendor_invoice_medical_2024.pdf`
     - `vendor_invoice_repairs_2024.pdf`
   - These are synthetic but can be used for initial testing

## Current File Count

Run this to check status:

```bash
cd backend/sample_docs
echo "Receipts: $(ls receipts/*.pdf 2>/dev/null | wc -l) PDFs"
echo "Invoices: $(ls invoices/*.pdf 2>/dev/null | wc -l) PDFs"
```

## Next Steps After Download

1. Verify you have 20-30 PDFs in both `receipts/` and `invoices/` folders
2. Proceed to create document type schemas in the UI
3. Upload documents and test classification
4. Run extraction and measure accuracy

## License & Citation

### CORD Dataset
- License: CC-BY-4.0 (Commercial use allowed)
- Citation:
  ```
  @inproceedings{park2019cord,
    title={CORD: A Consolidated Receipt Dataset for Post-OCR Parsing},
    author={Park, Seunghyun and Shin, Seung and Lee, Bado and Lee, Junyeop and Surh, Jaeheung and Seo, Minjoon and Lee, Hwalsuk},
    booktitle={Workshop on Document Intelligence at NeurIPS 2019},
    year={2019}
  }
  ```

### SROIE Dataset
- License: Research/Academic use (check Kaggle terms)
- Citation:
  ```
  @inproceedings{huang2019icdar2019,
    title={ICDAR2019 Competition on Scanned Receipts OCR and Information Extraction},
    author={Huang, Zheng and Chen, Kai and He, Jianhua and Bai, Xiang and Karatzas, Dimosthenis and Lu, Shijian and Jawahar, CV},
    booktitle={2019 International Conference on Document Analysis and Recognition (ICDAR)},
    pages={1516--1520},
    year={2019},
    organization={IEEE}
  }
  ```
