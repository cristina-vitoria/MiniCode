#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from minicode.specialization_data import validate_file

if __name__ == "__main__":
    print(json.dumps(validate_file(sys.argv[1]), indent=2, ensure_ascii=False))
