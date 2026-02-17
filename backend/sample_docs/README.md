# Sample Documents - Real Public Datasets

This directory contains sample documents from publicly available datasets for testing the extraction pipeline.

## Dataset Sources

### 1. CORD Dataset (Receipts)
**Location**: `receipts/`

**Source**: [CORD v2 on Hugging Face](https://huggingface.co/datasets/naver-clova-ix/cord-v2)

**License**: CC-BY-4.0 (Commercial use allowed)

**Download Instructions**:

Option A - Using Hugging Face Datasets (Recommended):
```python
from datasets import load_dataset
import os

# Load the dataset
dataset = load_dataset("naver-clova-ix/cord-v2")

# Save 20-30 sample images to receipts/ folder
for i, sample in enumerate(dataset['train'].select(range(30))):
    # Save image
    image = sample['image']
    image.save(f'receipts/receipt_{i:03d}.png')
    
    # Optionally save ground truth annotations
    with open(f'receipts/receipt_{i:03d}.json', 'w') as f:
        import json
        json.dump(sample['ground_truth'], f, indent=2)
```

Option B - Manual Download:
1. Visit https://huggingface.co/datasets/naver-clova-ix/cord-v2
2. Download the dataset (2.31 GB)
3. Extract 20-30 sample receipts to `receipts/` folder
4. Convert images to PDF if needed for testing

**Dataset Details**:
- 11,000+ Indonesian retail receipts
- Clear key-value pairs (store name, date, total, etc.)
- Line item tables with products, quantities, prices
- High-quality digital receipts

### 2. SROIE Dataset (Invoices)
**Location**: `invoices/`

**Source**: [SROIE on Kaggle](https://www.kaggle.com/datasets/urbikn/sroie-datasetv2)

**License**: Research/Academic use (check Kaggle dataset terms)

**Download Instructions**:

Option A - Using Kaggle API:
```bash
# Install Kaggle CLI
pip install kaggle

# Configure API credentials (get from kaggle.com/settings)
# Place kaggle.json in ~/.kaggle/

# Download dataset
kaggle datasets download -d urbikn/sroie-datasetv2

# Extract and select 20-30 samples
unzip sroie-datasetv2.zip
# Copy sample images to invoices/ folder
```

Option B - Manual Download:
1. Create Kaggle account at https://www.kaggle.com
2. Visit https://www.kaggle.com/datasets/urbikn/sroie-datasetv2
3. Click "Download" button
4. Extract 20-30 diverse invoice samples to `invoices/` folder

**Dataset Details**:
- 1,000 scanned receipt/invoice images
- Varied layouts and quality levels
- OCR challenges (scanned documents)
- Industry-standard benchmark dataset

## Converting Images to PDF

If the datasets provide images (PNG/JPG), you can convert them to PDF for testing:

```python
from PIL import Image
import os

def convert_to_pdf(image_path, output_path):
    image = Image.open(image_path)
    # Convert to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')
    image.save(output_path, 'PDF', resolution=100.0)

# Convert all images in receipts/
for filename in os.listdir('receipts/'):
    if filename.endswith(('.png', '.jpg', '.jpeg')):
        image_path = os.path.join('receipts', filename)
        pdf_path = os.path.join('receipts', filename.rsplit('.', 1)[0] + '.pdf')
        convert_to_pdf(image_path, pdf_path)
```

## Citation Requirements

### CORD Dataset
```
@inproceedings{park2019cord,
  title={CORD: A Consolidated Receipt Dataset for Post-OCR Parsing},
  author={Park, Seunghyun and Shin, Seung and Lee, Bado and Lee, Junyeop and Surh, Jaeheung and Seo, Minjoon and Lee, Hwalsuk},
  booktitle={Workshop on Document Intelligence at NeurIPS 2019},
  year={2019}
}
```

### SROIE Dataset
```
@inproceedings{huang2019icdar2019,
  title={ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction},
  author={Huang, Zheng and Chen, Kai and He, Jianhua and Bai, Xiang and Karatzas, Dimosthenis and Lu, Shijian and Jawahar, CV},
  booktitle={2019 International Conference on Document Analysis and Recognition (ICDAR)},
  pages={1516--1520},
  year={2019},
  organization={IEEE}
}
```

## Current Status

- [x] Downloaded CORD dataset samples (30 receipts) ✓
- [x] Converted images to PDF format ✓
- [x] Created 10 invoice samples from CORD data for testing ✓
- [x] Verified all files are accessible ✓

**Note**: For production use with true invoice data, follow the SROIE download instructions in `DOWNLOAD_INSTRUCTIONS.md`. The current invoice samples are CORD receipts renamed for testing purposes.

## Next Steps

After downloading the datasets:
1. Upload samples through the UI or API
2. Create document type schemas (Receipt, Invoice)
3. Test classification
4. Run extraction and measure accuracy
5. Document results in use case guides
