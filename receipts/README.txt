ProofPack Fraud Detection Receipt Bundle v1.0
==============================================

This bundle contains cryptographic receipts proving ProofPack's
fraud detection performance on 147 synthetic Medicare test cases.

CLAIM: 100% recall, 0% false positives

CONTENTS:
- fraud_detection_v1.receipts.jsonl: All 297 receipts from detection run
- MANIFEST.anchor: Merkle root anchoring receipt bundle
- fraud_cases.json: Test dataset metadata
- reproduce_fraud.sh: Verification script (requires ProofPack)
- verify_standalone.py: Python verification (no ProofPack install needed)
- README.txt: This file

QUICK VERIFICATION:
1. Install blake3: pip install blake3
2. Run: python verify_standalone.py
3. Expected output: "VERIFIED: Merkle root matches!"

FULL VERIFICATION:
1. Clone ProofPack: git clone https://github.com/northstaraokeystone/ProofPack
2. Copy bundle files to receipts/
3. Run: ./receipts/reproduce_fraud.sh
4. Expected: "Receipt Chain Verified"

MERKLE ROOT:
f8e5edaba5a8eaea317f6499c5d8e8e096e107a9cb03490cb66a46a20bb12e9e:faa3d5e062a83304b247f5f7e315883334bd40a7efb07c7772eb1897d6c99978

PERFORMANCE:
- Recall: 100%
- Precision: 100%
- True Positives: 10 (all fraud detected)
- True Negatives: 137 (all legitimate passed)
- False Positives: 0
- False Negatives: 0

DETECTION METHOD:
Compression-based analysis. Fraudulent claims with repetitive patterns
(duplicate billing codes, padded diagnoses) compress better than legitimate
claims with varied data. Threshold: 40% compression ratio.

DATASET:
- 147 total cases (10 fraud, 137 legitimate)
- Synthetic data modeled on Medicare fraud patterns
- Not real patient data

This bundle is cryptographic proof of detection accuracy.
Tampering with any receipt would invalidate the Merkle root.

For questions: https://github.com/northstaraokeystone/ProofPack

CREATED: 2024-12-31
VERSION: v1.0
BUNDLE HASH: [computed on packaging]
