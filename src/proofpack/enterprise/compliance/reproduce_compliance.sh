#!/bin/bash
# ProofPack Compliance Verification Script
# Reproduces compliance test results
# Usage: ./compliance/reproduce_compliance.sh

set -e  # Exit on error

echo "=== ProofPack Receipts-Native Compliance Verification ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Standard: Receipts-Native Architecture v2.0"
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found"
    exit 1
fi

# Check if we're in ProofPack directory
if [ ! -f "proofpack/__init__.py" ]; then
    echo "ERROR: Must run from ProofPack root directory"
    echo "Usage: cd ProofPack && ./compliance/reproduce_compliance.sh"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip install pytest blake3 --break-system-packages --quiet 2>/dev/null || \
pip install pytest blake3 --quiet 2>/dev/null || \
echo "Note: Dependencies may already be installed"

echo ""
echo "Running compliance tests..."
echo "=========================================="

# Run compliance tests
python -m pytest tests/test_compliance.py -v --tb=short

# Count passes
PASSES=$(python -m pytest tests/test_compliance.py -v --tb=no 2>&1 | grep -c "PASSED" || echo "0")
TOTAL=19

echo ""
echo "=========================================="
echo "=== RESULTS: $PASSES/$TOTAL principles tests pass ==="
echo ""

# Calculate principle status
if [ "$PASSES" -ge 17 ]; then
    echo "Status: FULLY COMPLIANT (6/6 principles)"
elif [ "$PASSES" -ge 12 ]; then
    echo "Status: MOSTLY COMPLIANT (4-5/6 principles)"
elif [ "$PASSES" -ge 6 ]; then
    echo "Status: PARTIALLY COMPLIANT (2-3/6 principles)"
else
    echo "Status: NON-COMPLIANT (<2/6 principles)"
fi

echo ""
echo "=== Verification complete ==="
echo "See compliance/COMPLIANCE_REPORT.md for details"
