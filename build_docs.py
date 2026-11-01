import os
import re
from fpdf import FPDF
from fpdf.fonts import FontFace
import markdown


def erstelle_readme_pdf(ziel_pfad=os.path.join("dist", "README.pdf")):
    """Konvertiert USER_GUIDE.md (Anwender-Handbuch) und DISCLAIMER.md in eine formatierte PDF-Datei für den dist-Ordner."""
    os.makedirs(os.path.dirname(ziel_pfad) or ".", exist_ok=True)

    md_teile = []
    handbuch_datei = "USER_GUIDE.md" if os.path.exists("USER_GUIDE.md") else "README.md"
    if os.path.exists(handbuch_datei):
        with open(handbuch_datei, "r", encoding="utf-8") as f:
            handbuch_text = re.sub(r"[\U00010000-\U0010ffff]", "", f.read())
            handbuch_text = handbuch_text.replace("$\\ge 0\\,\\%$", ">= 0 %")
            md_teile.append(handbuch_text)
    if os.path.exists("DISCLAIMER.md"):
        with open("DISCLAIMER.md", "r", encoding="utf-8") as f:
            disclaimer_text = re.sub(r"[\U00010000-\U0010ffff]", "", f.read())
            md_teile.append("\n\n---\n\n" + disclaimer_text)

    kombinierter_md = "\n".join(md_teile)
    html_body = markdown.markdown(kombinierter_md, extensions=["fenced_code", "tables"])

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    segoe_reg = os.path.join(win_fonts, "segoeui.ttf")
    segoe_bold = os.path.join(win_fonts, "segoeuib.ttf")
    segoe_ital = os.path.join(win_fonts, "segoeuii.ttf")
    segoe_bi = os.path.join(win_fonts, "segoeuiz.ttf")

    tag_styles = {}
    if os.path.exists(segoe_reg):
        pdf.add_font("SegoeUI", style="", fname=segoe_reg)
        pdf.add_font("SegoeUI", style="B", fname=segoe_bold if os.path.exists(segoe_bold) else segoe_reg)
        pdf.add_font("SegoeUI", style="I", fname=segoe_ital if os.path.exists(segoe_ital) else segoe_reg)
        pdf.add_font("SegoeUI", style="BI", fname=segoe_bi if os.path.exists(segoe_bi) else segoe_reg)
        consola_reg = os.path.join(win_fonts, "consola.ttf")
        consola_bold = os.path.join(win_fonts, "consolab.ttf")
        consola_ital = os.path.join(win_fonts, "consolai.ttf")
        code_font = consola_reg if os.path.exists(consola_reg) else segoe_reg
        pdf.add_font("Consolas", style="", fname=code_font)
        pdf.add_font("Consolas", style="B", fname=consola_bold if os.path.exists(consola_bold) else code_font)
        pdf.add_font("Consolas", style="I", fname=consola_ital if os.path.exists(consola_ital) else code_font)
        pdf.set_font("SegoeUI", size=10)
        tag_styles = {
            "code": FontFace(family="Consolas", size_pt=9, fill_color=(240, 244, 248)),
            "pre": FontFace(family="Consolas", size_pt=9, fill_color=(240, 244, 248)),
        }
    else:
        pdf.set_font("Helvetica", size=10)

    pdf.write_html(html_body, tag_styles=tag_styles)
    pdf.output(ziel_pfad)
    print(f"PDF erfolgreich erstellt: {ziel_pfad}")


if __name__ == "__main__":
    erstelle_readme_pdf()

