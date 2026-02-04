# ==============================================================================
# ML Engine Package
# ==============================================================================
# This package contains machine learning components for visual search:
#   - inference.py: YOLOv8 model loading and prediction
#   - embeddings.py: (Future) Vector embedding generation
#   - preprocessing.py: (Future) Image preprocessing utilities
#
# Architecture Overview:
#   1. User uploads an image of a hardware part
#   2. YOLOv8 detects and classifies the part type
#   3. Embedding model generates a vector representation
#   4. pgvector performs similarity search in the database
#   5. Return matching parts with confidence scores
#
# Model Files:
#   - Store model weights in a 'models/' directory (add to .gitignore)
#   - Use environment variables for model paths (see core/config.py)
# ==============================================================================
