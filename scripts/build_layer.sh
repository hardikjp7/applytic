set -e
 
LAYER_DIR="lambdas/shared_layer"
PYTHON_DIR="${LAYER_DIR}/python"
 
echo "Building Lambda Layer..."
echo "  Target: ${PYTHON_DIR}"
 
pip install \
  -r "${LAYER_DIR}/requirements.txt" \
  -t "${PYTHON_DIR}" \
  --upgrade \
  --quiet \
  --no-user
 
echo ""
echo "✅ Layer build complete. Run 'cdk deploy' to deploy."