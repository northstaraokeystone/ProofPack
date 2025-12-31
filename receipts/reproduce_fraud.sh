#!/bin/bash
# ProofPack Fraud Detection Verification Script
# Verifies published receipts by checking Merkle root integrity
# Usage: ./receipts/reproduce_fraud.sh

set -e

echo "=== ProofPack Fraud Detection Verification ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Check if we're in ProofPack directory
if [ ! -f "proofpack/__init__.py" ]; then
    echo "ERROR: Must run from ProofPack root directory"
    echo "Usage: cd ProofPack && ./receipts/reproduce_fraud.sh"
    exit 1
fi

# Check required files exist
if [ ! -f "receipts/fraud_detection_v1.receipts.jsonl" ]; then
    echo "ERROR: receipts/fraud_detection_v1.receipts.jsonl not found"
    exit 1
fi

if [ ! -f "receipts/MANIFEST.anchor" ]; then
    echo "ERROR: receipts/MANIFEST.anchor not found"
    exit 1
fi

echo "Verifying receipt chain integrity..."
echo ""

# Verify Merkle root matches
python3 << 'EOF'
import json
import sys
sys.path.insert(0, '.')

from proofpack.core.receipt import merkle

# Load receipts
print("Loading receipts...")
with open('receipts/fraud_detection_v1.receipts.jsonl') as f:
    receipts = [json.loads(line) for line in f if line.strip()]

print(f"  Loaded {len(receipts)} receipts")

# Compute Merkle root
print("\nComputing Merkle root...")
computed_root = merkle(receipts)
print(f"  Computed: {computed_root}")

# Load published root from manifest
print("\nLoading published Merkle root...")
with open('receipts/MANIFEST.anchor') as f:
    manifest = json.load(f)
    published_root = manifest['merkle_root']

print(f"  Published: {published_root}")

# Compare
print("\nVerification:")
if computed_root == published_root:
    print("  ✓ Merkle root VERIFIED - receipts are authentic")
    print("")
    print("=== Receipt Chain Verified ===")
    print("")

    # Display results from manifest
    perf = manifest.get('performance', {})
    print("Performance (from receipts):")
    print(f"  Recall:          {perf.get('recall', 0):.2%}")
    print(f"  Precision:       {perf.get('precision', 0):.2%}")
    print(f"  True Positives:  {perf.get('true_positives', 0)}")
    print(f"  True Negatives:  {perf.get('true_negatives', 0)}")
    print(f"  False Positives: {perf.get('false_positives', 0)}")
    print(f"  False Negatives: {perf.get('false_negatives', 0)}")

    dataset = manifest.get('dataset', {})
    print(f"\nDataset:")
    print(f"  Total cases: {dataset.get('total', 0)}")
    print(f"  Fraud cases: {dataset.get('fraud_cases', 0)}")
    print(f"  Legit cases: {dataset.get('legit_cases', 0)}")

    sys.exit(0)
else:
    print("  ✗ MISMATCH - receipts may have been tampered!")
    print(f"  Expected: {published_root}")
    print(f"  Got:      {computed_root}")
    sys.exit(1)
EOF

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "To fully reproduce detection (regenerates receipts):"
    echo "  python receipts/generate_fraud_receipts.py"
else
    echo "Verification FAILED!"
fi

exit $exit_code
