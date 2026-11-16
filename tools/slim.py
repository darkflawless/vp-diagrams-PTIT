"""In XML VP rút gọn: bỏ các thuộc tính nhiễu để đọc cấu trúc."""
import re
import sys
import xml.etree.ElementTree as ET

NOISE = re.compile(r"^(Pm|Quality|Backlog|UserID|Documentation|.*_IsNull$|.*Internal(Height|Width)$|Request|"
                   r"TaggedValue|Teamwork|Show(PM|Allocated))")
root = ET.parse(sys.argv[1]).getroot()
skip_tags = {"ProjectInfo", "DataType", "TaggedValues"}


def dump(e, d=0):
    if e.tag in skip_tags:
        return
    attrs = " ".join(f'{k}="{v}"' for k, v in e.attrib.items() if not NOISE.match(k))
    print("  " * d + f"<{e.tag} {attrs}>")
    for c in e:
        dump(c, d + 1)


for c in root:
    dump(c)
