"""
Download and prepare real public datasets for extraction testing.

This script downloads samples from CORD and SROIE datasets and converts them to PDF format.
"""

import os
import json
from pathlib import Path
from PIL import Image

def setup_directories():
    """Create necessary directories."""
    Path("receipts").mkdir(exist_ok=True)
    Path("invoices").mkdir(exist_ok=True)
    print("[OK] Created directories: receipts/, invoices/")

def download_cord_dataset(num_samples=30):
    """
    Download CORD dataset samples using Hugging Face datasets library.
    
    Args:
        num_samples: Number of receipt samples to download (default: 30)
    """
    try:
        from datasets import load_dataset
        print(f"\nDownloading CORD dataset ({num_samples} samples)...")
        
        # Load dataset
        dataset = load_dataset("naver-clova-ix/cord-v2", split="train")
        
        # Download samples
        for i, sample in enumerate(dataset.select(range(num_samples))):
            # Save image
            image = sample['image']
            image_path = f'receipts/receipt_{i:03d}.png'
            image.save(image_path)
            
            # Convert to PDF
            pdf_path = f'receipts/receipt_{i:03d}.pdf'
            convert_image_to_pdf(image_path, pdf_path)
            
            # Save ground truth annotations for reference
            gt_path = f'receipts/receipt_{i:03d}_gt.json'
            with open(gt_path, 'w', encoding='utf-8') as f:
                json.dump(sample['ground_truth'], f, indent=2, ensure_ascii=False)
            
            if (i + 1) % 10 == 0:
                print(f"  Downloaded {i + 1}/{num_samples} receipts...")
        
        print(f"[OK] Downloaded {num_samples} CORD receipts to receipts/")
        return True
        
    except ImportError:
        print("[ERROR] 'datasets' library not installed")
        print("  Install with: pip install datasets")
        return False
    except Exception as e:
        print(f"[ERROR] Error downloading CORD dataset: {e}")
        return False

def download_sroie_dataset_instructions():
    """
    Provide instructions for downloading SROIE dataset (requires Kaggle account).
    """
    print("\n" + "="*60)
    print("SROIE Dataset Download Instructions")
    print("="*60)
    print("\nThe SROIE dataset requires manual download from Kaggle.")
    print("\nOption 1 - Using Kaggle API:")
    print("  1. Install: pip install kaggle")
    print("  2. Get API key from https://www.kaggle.com/settings")
    print("  3. Place kaggle.json in ~/.kaggle/")
    print("  4. Run: kaggle datasets download -d urbikn/sroie-datasetv2")
    print("  5. Extract and copy 20-30 samples to invoices/")
    print("\nOption 2 - Manual Download:")
    print("  1. Visit: https://www.kaggle.com/datasets/urbikn/sroie-datasetv2")
    print("  2. Click 'Download' button")
    print("  3. Extract 20-30 diverse samples to invoices/")
    print("  4. Run this script again to convert images to PDF")
    print("\nAlternative - Hugging Face:")
    print("  Dataset also available at:")
    print("  https://huggingface.co/datasets/krishnapal2308/SROIE")
    print("="*60 + "\n")

def convert_image_to_pdf(image_path, output_path):
    """
    Convert an image file to PDF format.
    
    Args:
        image_path: Path to input image
        output_path: Path to output PDF
    """
    try:
        image = Image.open(image_path)
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(output_path, 'PDF', resolution=100.0)
        return True
    except Exception as e:
        print(f"[ERROR] Error converting {image_path}: {e}")
        return False

def convert_existing_images():
    """
    Convert any existing PNG/JPG images in receipts/ and invoices/ to PDF.
    """
    converted_count = 0
    
    for folder in ['receipts', 'invoices']:
        if not os.path.exists(folder):
            continue
            
        for filename in os.listdir(folder):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(folder, filename)
                pdf_filename = filename.rsplit('.', 1)[0] + '.pdf'
                pdf_path = os.path.join(folder, pdf_filename)
                
                # Skip if PDF already exists
                if os.path.exists(pdf_path):
                    continue
                
                if convert_image_to_pdf(image_path, pdf_path):
                    converted_count += 1
    
    if converted_count > 0:
        print(f"[OK] Converted {converted_count} images to PDF")
    
    return converted_count

def check_status():
    """Check download status and provide summary."""
    print("\n" + "="*60)
    print("Dataset Status")
    print("="*60)
    
    # Count files
    receipts_pdf = len([f for f in os.listdir('receipts') if f.endswith('.pdf')]) if os.path.exists('receipts') else 0
    receipts_img = len([f for f in os.listdir('receipts') if f.endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists('receipts') else 0
    invoices_pdf = len([f for f in os.listdir('invoices') if f.endswith('.pdf')]) if os.path.exists('invoices') else 0
    invoices_img = len([f for f in os.listdir('invoices') if f.endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists('invoices') else 0
    
    print(f"\nReceipts (CORD):")
    print(f"  PDF files: {receipts_pdf}")
    print(f"  Image files: {receipts_img}")
    print(f"  Status: {'[OK] Ready' if receipts_pdf >= 20 else '[PENDING] Need more samples (target: 20-30)'}")
    
    print(f"\nInvoices (SROIE):")
    print(f"  PDF files: {invoices_pdf}")
    print(f"  Image files: {invoices_img}")
    print(f"  Status: {'[OK] Ready' if invoices_pdf >= 20 else '[PENDING] Need more samples (target: 20-30)'}")
    
    print("\n" + "="*60 + "\n")

def main():
    """Main execution function."""
    print("="*60)
    print("Real Dataset Download & Preparation")
    print("="*60)
    
    # Setup
    setup_directories()
    
    # Download CORD dataset
    cord_success = download_cord_dataset(num_samples=30)
    
    # Provide SROIE instructions
    download_sroie_dataset_instructions()
    
    # Convert any existing images
    convert_existing_images()
    
    # Show status
    check_status()
    
    # Next steps
    print("Next Steps:")
    print("1. If SROIE download failed, follow the instructions above")
    print("2. Verify PDF files in receipts/ and invoices/ folders")
    print("3. Upload documents through the UI or API")
    print("4. Create document type schemas")
    print("5. Test extraction pipeline")
    print("\n")

if __name__ == "__main__":
    main()
