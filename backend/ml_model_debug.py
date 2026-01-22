import joblib
import os
from typing import Optional

# Debug model loading
print("Current working directory:", os.getcwd())
print("Script directory:", os.path.dirname(__file__))

# Load the trained scikit-learn model once
# Try database-trained model first, fallback to CSV-trained model
_MODEL_PATH_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'model', 'water_model.pkl'))
_MODEL_PATH_CSV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'model', 'water_model_csv_legacy.pkl'))

print("Model DB path:", _MODEL_PATH_DB)
print("Model CSV path:", _MODEL_PATH_CSV)
print("DB model exists:", os.path.exists(_MODEL_PATH_DB))
print("CSV model exists:", os.path.exists(_MODEL_PATH_CSV))

_MODEL_PATH = _MODEL_PATH_DB if os.path.exists(_MODEL_PATH_DB) else _MODEL_PATH_CSV
_model = None

try:
    if os.path.exists(_MODEL_PATH):
        print(f"Loading model from: {_MODEL_PATH}")
        _model = joblib.load(_MODEL_PATH)
        print("Model loaded successfully!")
        print("Model type:", type(_model))
    else:
        raise FileNotFoundError(f"Model file not found at {_MODEL_PATH}")
except Exception as e:
    print(f"Error loading model: {e}")
    _model = None
