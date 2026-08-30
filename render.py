import sys
from pathlib import Path
import pymupdf
doc = pymupdf.open("bruto/TCU_Licitacoes_Contratos_5ed_2025.pdf")
out = Path(r"C:\Users\MATHEU~1\AppData\Local\Temp\claude\C--Users-Matheus-Menegatti\bdac31ff-2b5c-43a7-ade7-2c073e157e52\scratchpad")
for n in [int(x) for x in sys.argv[1:]]:
    pix = doc[n - 1].get_pixmap(dpi=110)
    f = out / f"p{n:04d}.png"
    pix.save(f)
    print(f, pix.width, "x", pix.height)
