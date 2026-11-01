import os
import re
import subprocess
from datetime import datetime
from fpdf import FPDF
from fpdf.fonts import FontFace
import markdown


def aktualisiere_build_info(pfad="build_info.py"):
    """Erhöht automatisch die Build-Nummer, liest Version aus pyproject.toml sowie den aktuellen Git-Commit."""
    version = "0.1.0"
    if os.path.exists("pyproject.toml"):
        with open("pyproject.toml", "r", encoding="utf-8") as f:
            m_ver = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), flags=re.MULTILINE)
            if m_ver:
                version = m_ver.group(1)

    bisherige_nummer = 0
    if os.path.exists(pfad):
        with open(pfad, "r", encoding="utf-8") as f:
            m_num = re.search(r"^BUILD_NUMBER\s*=\s*(\d+)", f.read(), flags=re.MULTILINE)
            if m_num:
                bisherige_nummer = int(m_num.group(1))

    neue_nummer = bisherige_nummer + 1
    build_datum = datetime.now().strftime("%Y-%m-%d %H:%M")

    git_commit = "unknown"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            git_commit = res.stdout.strip()
    except Exception:
        pass

    inhalt = (
        "# Automatisch generierte Build-Informationen (wird durch build_docs.py beim Build aktualisiert)\n"
        f'VERSION = "{version}"\n'
        f"BUILD_NUMBER = {neue_nummer}\n"
        f'BUILD_DATE = "{build_datum}"\n'
        f'GIT_COMMIT = "{git_commit}"\n'
        'BUILD_LABEL = f"v{VERSION} | Build #{BUILD_NUMBER} ({BUILD_DATE}, {GIT_COMMIT})"\n'
    )
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(inhalt)

    label = f"v{version} | Build #{neue_nummer} ({build_datum}, {git_commit})"
    print(f"Build-Info aktualisiert: {label}")
    return label


def erstelle_readme_pdf(build_label="", ziel_pfad=os.path.join("dist", "README.pdf")):
    """Konvertiert USER_GUIDE.md (Anwender-Handbuch) und DISCLAIMER.md in eine formatierte PDF-Datei für den dist-Ordner."""
    os.makedirs(os.path.dirname(ziel_pfad) or ".", exist_ok=True)

    md_teile = []
    handbuch_datei = "USER_GUIDE.md" if os.path.exists("USER_GUIDE.md") else "README.md"
    if os.path.exists(handbuch_datei):
        with open(handbuch_datei, "r", encoding="utf-8") as f:
            handbuch_text = re.sub(r"[\U00010000-\U0010ffff]", "", f.read())
            handbuch_text = handbuch_text.replace("$\\ge 0\\,\\%$", ">= 0 %")
            if build_label:
                handbuch_text = f"*{build_label}*\n\n" + handbuch_text
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
    aktuelles_label = aktualisiere_build_info()
    erstelle_readme_pdf(aktuelles_label)
