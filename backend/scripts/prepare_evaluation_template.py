"""Build deployment assets once from a rendered DOCX; not used on the request path."""
import argparse
from pathlib import Path
import shutil

import fitz
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', required=True, type=Path)
    parser.add_argument('--font', required=True, type=Path)
    parser.add_argument('--license', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = fitz.open(args.pdf)
    result = fitz.open(); result.insert_pdf(source, from_page=0, to_page=0)
    page = result[0]
    # Clear only editable lines and score placeholders; keep vector borders and observations.
    rectangles = [(44, 73, 568, 90), (44, 96, 568, 156), (44, 551, 568, 681), (44, 758, 570, 780)]
    rectangles += [(349, 205+i*37, 381, 239+i*37) for i in range(8)]
    for box in rectangles:
        page.add_redact_annot(fitz.Rect(box), fill=(1, 1, 1))
    page.apply_redactions(images=0, graphics=0)
    result.set_metadata({})
    result.save(args.output / 'first-page.pdf', garbage=4, deflate=True)
    font = TTFont(args.font)
    if 'fvar' in font:
        font = instantiateVariableFont(font, {'wght': 400}, inplace=False)
    font.save(args.output / 'NotoSansSC-Regular.ttf')
    shutil.copyfile(args.license, args.output / 'OFL.txt')


if __name__ == '__main__':
    main()
