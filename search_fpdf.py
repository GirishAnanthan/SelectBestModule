import fpdf, os
path = os.path.dirname(fpdf.__file__)
import glob
for fpath in glob.glob(os.path.join(path, "*.py")):
    with open(fpath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if "Undefined font" in line:
                print(f"{os.path.basename(fpath)}:{i+1}: {line.strip()}")
