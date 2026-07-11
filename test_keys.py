import sys, re
sys.path.insert(0, 'D:\\SelectBestModule')
import pdf_parser as pp

# Check all keys that parse_specs can set
source = open(pp.__file__, "r", encoding="utf-8").read()

# Words assigned to specs dict
assigns = re.findall(r'specs\["(\w+)"\]', source)
print("=== Keys assigned to specs dict ===")
for k in sorted(set(assigns)):
    print("  {}".format(k))

print()
print("=== price_per_wp search ===")
if 'price' in source.lower():
    for i, line in enumerate(source.split('\n')):
        if 'price' in line.lower():
            print("  Line {}: {}".format(i+1, line.strip()))
else:
    print("  NOT FOUND anywhere in pdf_parser.py")
