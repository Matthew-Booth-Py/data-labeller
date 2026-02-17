"""Download SROIE dataset from Hugging Face."""

import os
from pathlib import Path
from PIL import Image

def download_sroie_from_hf(num_samples=30):
    """Download SROIE dataset from Hugging Face."""
    try:
        from datasets import load_dataset
        print(f"\nDownloading SROIE dataset from Hugging Face ({num_samples} samples)...")
        
        # Load dataset
        dataset = load_dataset("krishnapal2308/SROIE", split="train")
        
        # Download samples
        for i, sample in enumerate(dataset.select(range(min(num_samples, len(dataset))))):
            try:
                # Get image
                image = sample['image']
                
                # Save image
                image_path = f'invoices/invoice_{i:03d}.png'
                image.save(image_path)
                
                # Convert to PDF
                pdf_path = f'invoices/invoice_{i:03d}.pdf'
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(pdf_path, 'PDF', resolution=100.0)
                
                if (i + 1) % 10 == 0:
                    print(f"  Downloaded {i + 1}/{num_samples} invoices...")
                    
            except Exception as e:
                print(f"  [WARNING] Skipped sample {i}: {e}")
                continue
        
        print(f"[OK] Downloaded SROIE invoices to invoices/")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error downloading SROIE dataset: {e}")
        return False

if __name__ == "__main__":
    Path("invoices").mkdir(exist_ok=True)
    download_sroie_from_hf(30)
