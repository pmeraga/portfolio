"""
Download the SAML-D dataset from Kaggle.
"""

import kagglehub
import os

# Download latest version
print("Downloading SAML-D dataset from Kaggle...")
path = kagglehub.dataset_download("berkanoztas/synthetic-transaction-monitoring-dataset-aml")

print("Path to dataset files:", path)

# List files in the downloaded directory
if os.path.exists(path):
    print("\nFiles in dataset directory:")
    for file in os.listdir(path):
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path):
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"  - {file} ({size_mb:.2f} MB)")
        elif os.path.isdir(file_path):
            print(f"  - {file}/ (directory)")

