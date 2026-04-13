import numpy as np
import pandas as pd
from pathlib import Path

def convert_to_serializable(obj):
    """
    Recursively convert numpy/pandas types to JSON-serializable Python types.

    Handles:
    - numpy integers/floats → Python int/float
    - numpy booleans → Python bool
    - pandas Series/DataFrame → dict
    - numpy arrays → list
    """
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_to_serializable(v) for v in obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (pd.Series, pd.DataFrame)):
        return obj.to_dict()
    elif isinstance(obj, pd.Period):
        return str(obj)
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, (Path, np.str_)):
        return str(obj)
    return obj