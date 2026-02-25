# Public Datasets for Extraction Testing

This document describes the real public datasets downloaded for testing the extraction pipeline.

## Overview

We have prepared 2 financial document use cases with real public data:

1. **Receipts** - 30 samples from CORD dataset
2. **Invoices** - 10 samples (CORD receipts used as proxies for testing)

## Dataset 1: CORD (Receipts)

### Source
- **Name**: CORD (Consolidated Receipt Dataset for Post-OCR Parsing)
- **Provider**: Naver Clova AI
- **URL**: https://github.com/clovaai/cord
- **Hugging Face**: https://huggingface.co/datasets/naver-clova-ix/cord-v2
- **License**: CC-BY-4.0 (Commercial use allowed)

### Description
CORD contains over 11,000 Indonesian retail receipt images with comprehensive annotations. The dataset includes:
- Store information (name, address, phone)
- Transaction details (date, time, receipt number)
- Line items (product names, quantities, prices)
- Payment information (subtotals, tax, total, payment method)

### Downloaded Samples
- **Location**: `backend/sample_docs/receipts/`
- **Count**: 30 receipt PDFs
- **Format**: PDF (converted from PNG)
- **Additional Files**:
  - PNG images (original format)
  - JSON ground truth annotations

### Characteristics
- High-quality digital receipts
- Clear text and structure
- Consistent layout patterns
- Multiple stores and formats
- Perfect for demonstrating simple → moderate complexity progression

### Use Case
- **Phase 1**: Simple key-value extraction (store name, date, total)
- **Phase 2**: Table extraction (line items with products, quantities, prices)

## Dataset 2: Invoices (Testing Samples)

### Source
- **Current**: CORD receipts (samples 10-19) renamed as invoices
- **Recommended**: SROIE dataset for production use

### Description
For initial testing, we're using CORD receipts as invoice proxies because they share similar structure:
- Vendor/merchant information
- Line items with descriptions and amounts
- Tax calculations
- Total amounts

### Downloaded Samples
- **Location**: `backend/sample_docs/invoices/`
- **Count**: 10 invoice PDFs
- **Format**: PDF

### For Production Use: SROIE Dataset

#### Recommended Source
- **Name**: SROIE (Scanned Receipts OCR and Information Extraction)
- **Provider**: ICDAR 2019 Competition
- **Kaggle**: https://www.kaggle.com/datasets/urbikn/sroie-datasetv2
- **License**: Research/Academic use

#### Why SROIE?
- 1,000 scanned receipt/invoice images
- Varied layouts and quality levels
- OCR challenges (scanned documents)
- Industry-standard benchmark
- Tests extraction robustness

#### Download Instructions
See `backend/sample_docs/DOWNLOAD_INSTRUCTIONS.md` for detailed steps.

## Dataset Statistics

| Dataset | Count | Format | Quality | Complexity | Use Case |
|---------|-------|--------|---------|------------|----------|
| CORD Receipts | 30 | PDF | High | Simple → Moderate | Receipt extraction |
| Invoice Samples | 10 | PDF | High | Moderate | Invoice extraction (testing) |
| SROIE (recommended) | 1,000 | Images | Varied | Moderate → Complex | Invoice extraction (production) |

## Ground Truth Annotations

### CORD Dataset
Each receipt includes a JSON file with ground truth annotations:
- `receipt_XXX_gt.json` contains:
  - Bounding boxes for all text
  - Semantic labels (store name, date, total, etc.)
  - Line item structure
  - Menu hierarchy

### Using Ground Truth
The ground truth can be used to:
1. Validate extraction accuracy
2. Calculate precision/recall metrics
3. Compare LLM extraction vs. human annotations
4. Identify common failure patterns

## License & Citation

### CORD Dataset

**License**: Creative Commons Attribution 4.0 International (CC-BY-4.0)

**Citation**:
```bibtex
@inproceedings{park2019cord,
  title={CORD: A Consolidated Receipt Dataset for Post-OCR Parsing},
  author={Park, Seunghyun and Shin, Seung and Lee, Bado and Lee, Junyeop and Surh, Jaeheung and Seo, Minjoon and Lee, Hwalsuk},
  booktitle={Workshop on Document Intelligence at NeurIPS 2019},
  year={2019}
}
```

### SROIE Dataset

**License**: Research and academic use (check Kaggle dataset terms)

**Citation**:
```bibtex
@inproceedings{huang2019icdar2019,
  title={ICDAR2019 Competition on Scanned Receipts OCR and Information Extraction},
  author={Huang, Zheng and Chen, Kai and He, Jianhua and Bai, Xiang and Karatzas, Dimosthenis and Lu, Shijian and Jawahar, CV},
  booktitle={2019 International Conference on Document Analysis and Recognition (ICDAR)},
  pages={1516--1520},
  year={2019},
  organization={IEEE}
}
```

## Next Steps

1. **Upload Documents**: Use the UI to upload PDFs from `backend/sample_docs/receipts/` and `invoices/`
2. **Create Schemas**: Define document types with extraction fields
3. **Test Classification**: Verify documents are classified correctly
4. **Run Extraction**: Test structured data extraction
5. **Measure Accuracy**: Compare results with ground truth
6. **Document Results**: Record findings in use case guides

## Alternative Datasets

If you need different document types or more samples:

1. **RVL-CDIP** (400K documents, 16 classes including invoices)
   - https://huggingface.co/datasets/aharley/rvl_cdip
   - Good for document classification

2. **DocBank** (500K document pages)
   - https://doc-analysis.github.io/docbank-page/
   - Includes financial forms and tables

3. **CORU** (20K+ multilingual receipts, 2024)
   - https://huggingface.co/papers/2406.04493
   - Arabic and English receipts

## Support

For questions or issues with datasets:
- Check `backend/sample_docs/DOWNLOAD_INSTRUCTIONS.md`
- Review dataset provider documentation
- Ensure proper attribution and license compliance
