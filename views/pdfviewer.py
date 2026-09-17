from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser

import flet as ft
import flet.canvas as cv


# ----------------------------------------------------------------------
# Helpers de compatibilité Flet & Système
# ----------------------------------------------------------------------
def safe_border(width=1, color="#374151"):
    try:
        return ft.border.all(width, color)
    except Exception:
        try:
            return ft.Border.all(width, color)
        except Exception:
            side = ft.BorderSide(width, color)
            return ft.Border(top=side, right=side, bottom=side, left=side)


def safe_padding(vertical=0, horizontal=0):
    try:
        return ft.padding.symmetric(vertical=vertical, horizontal=horizontal)
    except Exception:
        try:
            return ft.padding.only(
                left=horizontal, top=vertical, right=horizontal, bottom=vertical
            )
        except Exception:
            return ft.Padding(horizontal, vertical, horizontal, vertical)


def safe_margin(vertical=0, horizontal=0):
    try:
        return ft.margin.symmetric(vertical=vertical, horizontal=horizontal)
    except Exception:
        try:
            return ft.margin.only(
                left=horizontal, top=vertical, right=horizontal, bottom=vertical
            )
        except Exception:
            return ft.Margin(horizontal, vertical, horizontal, vertical)


CENTER = ft.Alignment(0, 0)


def get_download_dir(folder_name="Factures") -> Path:
    system = platform.system()
    if system == "Android" or os.path.exists("/storage/emulated/0/Download"):
        base_download = Path("/storage/emulated/0/Download")
        if not base_download.exists():
            base_download = (
                Path(os.environ.get("EXTERNAL_STORAGE", "/sdcard")) / "Download"
            )
    else:
        base_download = Path.home() / "Downloads"
        if not base_download.exists():
            base_download = Path.home() / "Téléchargements"
            if not base_download.exists():
                base_download = Path.home()

    target_dir = base_download / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


# ----------------------------------------------------------------------
# Helpers d'impression Système & Multiplateforme (Desktop / Android)
# ----------------------------------------------------------------------
def get_system_printers():
    """Détecte la liste des imprimantes installées sur Windows, macOS et Linux."""
    printers = []
    sys_name = platform.system()
    try:
        if sys_name == "Windows":
            cmd = 'powershell -Command "Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name"'
            res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if res.returncode == 0:
                printers = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            if not printers:
                res_wmi = subprocess.run("wmic printer get name", capture_output=True, text=True, shell=True)
                if res_wmi.returncode == 0:
                    printers = [l.strip() for l in res_wmi.stdout.splitlines() if l.strip() and l.strip().lower() != "name"]
        elif sys_name in ["Darwin", "Linux"]:
            res = subprocess.run(["lpstat", "-e"], capture_output=True, text=True)
            if res.returncode == 0:
                printers = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            if not printers:
                res_p = subprocess.run(["lpstat", "-p"], capture_output=True, text=True)
                if res_p.returncode == 0:
                    for line in res_p.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] == "printer":
                            printers.append(parts[1])
    except Exception as ex:
        print(f"Erreur détection imprimantes : {ex}")

    return printers


def print_to_printer(path: Path, printer_name: str = None) -> bool:
    """Envoie le fichier PDF vers l'imprimante spécifiée."""
    sys_name = platform.system()
    try:
        if sys_name == "Windows":
            if printer_name:
                cmd = f'powershell -Command "Start-Process -FilePath \'{path}\' -Verb PrintTo -ArgumentList \'\"{printer_name}\"\'"'
                subprocess.run(cmd, shell=True, check=True)
            else:
                os.startfile(str(path), "print")
            return True
        elif sys_name in ["Darwin", "Linux"]:
            if printer_name:
                subprocess.run(["lpr", "-P", printer_name, str(path)], check=True)
            else:
                subprocess.run(["lpr", str(path)], check=True)
            return True
    except Exception as ex:
        print(f"Erreur impression : {ex}")
        return False


# ----------------------------------------------------------------------
# Extracteurs & Normalisateurs de données
# ----------------------------------------------------------------------
def resolve_document_type(doc_data):
    if not isinstance(doc_data, dict):
        return "DOCUMENT"

    raw_type = str(
        doc_data.get("type_document")
        or doc_data.get("type_document_interne")
        or doc_data.get("type")
        or doc_data.get("type_doc")
        or ""
    ).strip().lower()

    type_map = {
        "bon_livraison": "BON DE LIVRAISON",
        "livraison": "BON DE LIVRAISON",
        "bl": "BON DE LIVRAISON",
        "bon_commande": "BON DE COMMANDE",
        "commande": "BON DE COMMANDE",
        "bc": "BON DE COMMANDE",
        "devis": "DEVIS",
        "facture": "FACTURE",
        "avoir": "AVOIR",
    }

    custom_title = doc_data.get("titre_document") or doc_data.get("label")
    if custom_title:
        return str(custom_title).upper()

    if raw_type in type_map:
        return type_map[raw_type]

    if raw_type:
        return raw_type.replace("_", " ").upper()

    return "DOCUMENT"


def extract_client_info(c_raw):
    if not isinstance(c_raw, dict):
        return {
            "nom": str(c_raw or "CLIENT INCONNU"),
            "adresse": "",
            "cp_ville": "",
            "siret": "",
            "email": "",
            "tel": "",
        }

    nom = (
        c_raw.get("nom")
        or c_raw.get("entreprise")
        or c_raw.get("raison_sociale")
        or c_raw.get("societe")
        or ""
    ).strip()
    prenom = c_raw.get("prenom", "").strip()
    if prenom:
        nom = f"{nom} {prenom}".strip()
    if not nom:
        nom = "CLIENT INCONNU"

    adresse = c_raw.get("adresse") or c_raw.get("rue") or ""
    cp = c_raw.get("code_postal") or c_raw.get("cp") or ""
    ville = c_raw.get("ville") or ""
    cp_ville = f"{cp} {ville}".strip()

    siret = c_raw.get("siret") or c_raw.get("siren") or ""
    email = c_raw.get("email") or c_raw.get("mail") or ""
    tel = c_raw.get("telephone") or c_raw.get("tel") or c_raw.get("phone") or ""

    return {
        "nom": nom,
        "adresse": adresse,
        "cp_ville": cp_ville,
        "siret": siret,
        "email": email,
        "tel": tel,
    }


def extract_entreprise_info(e_raw):
    if not isinstance(e_raw, dict):
        e_raw = {}

    nom = (
        e_raw.get("nom")
        or e_raw.get("nom_entreprise")
        or e_raw.get("raison_sociale")
        or "MON ENTREPRISE"
    ).strip()
    adresse = e_raw.get("adresse") or e_raw.get("rue") or ""
    cp = e_raw.get("code_postal") or e_raw.get("cp") or ""
    ville = e_raw.get("ville") or ""
    cp_ville = f"{cp} {ville}".strip()

    siret = e_raw.get("siret") or "-"
    email = e_raw.get("email") or e_raw.get("mail") or "-"
    tel = e_raw.get("telephone") or e_raw.get("tel") or ""

    assujetti = e_raw.get("assujetti_tva", True)
    if isinstance(assujetti, str):
        assujetti = assujetti.strip().lower() not in ["false", "0", "non", "no", "off"]

    mention_tva = e_raw.get("mention_tva") or "TVA non applicable, art. 293 B du CGI"
    rc_pro = e_raw.get("rc_pro") or ""
    conditions_reglement = e_raw.get("conditions_reglement") or ""

    return {
        "nom": nom,
        "adresse": adresse,
        "cp_ville": cp_ville,
        "siret": siret,
        "email": email,
        "tel": tel,
        "assujetti": bool(assujetti),
        "mention_tva": mention_tva,
        "rc_pro": rc_pro,
        "conditions_reglement": conditions_reglement,
    }


# ----------------------------------------------------------------------
# Moteur PDF Pure Python (Génération Vectorielle)
# ----------------------------------------------------------------------
def generer_pdf_zero_dep(doc_data, target_path, entreprise_data):
    ent = extract_entreprise_info(entreprise_data or doc_data.get("entreprise", {}))
    cli = extract_client_info(doc_data.get("client") or doc_data.get("fournisseur", {}))

    type_doc = resolve_document_type(doc_data)
    num_doc = str(doc_data.get("numero", "N/A"))
    items = doc_data.get("articles", doc_data.get("lignes", []))

    def clean_pdf_str(text):
        return (
            str(text)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
            .encode("latin-1", "replace")
            .decode("latin-1")
        )

    cmds = []

    # En-tête Émetteur
    cmds.append("0.117 0.227 0.541 rg")
    cmds.append(f"BT /F1 12 Tf 40 790 Td ({clean_pdf_str(ent['nom'].upper())}) Tj ET")
    cmds.append("0.419 0.447 0.502 rg")
    y_ent = 778
    if ent["adresse"]:
        cmds.append(f"BT /F1 8 Tf 40 {y_ent} Td ({clean_pdf_str(ent['adresse'])}) Tj ET")
        y_ent -= 10
    if ent["cp_ville"]:
        cmds.append(f"BT /F1 8 Tf 40 {y_ent} Td ({clean_pdf_str(ent['cp_ville'])}) Tj ET")
        y_ent -= 10
    cmds.append(f"BT /F1 8 Tf 40 {y_ent} Td (SIRET : {clean_pdf_str(ent['siret'])}) Tj ET")
    y_ent -= 10
    cmds.append(f"BT /F1 8 Tf 40 {y_ent} Td (Email : {clean_pdf_str(ent['email'])}) Tj ET")

    # Cartouche Destinataire
    cmds.append("0.952 0.956 0.964 rg 330 720 225 80 re f")
    cmds.append("0.117 0.227 0.541 rg BT /F1 8 Tf 340 786 Td (DESTINATAIRE :) Tj ET")
    cmds.append(
        "0.121 0.160 0.215 rg BT /F1 10 Tf 340 772 Td ("
        + clean_pdf_str(cli["nom"][:32])
        + ") Tj ET"
    )

    y_cli = 758
    if cli["adresse"]:
        cmds.append(
            f"0.300 0.300 0.300 rg BT /F1 8 Tf 340 {y_cli} Td ({clean_pdf_str(cli['adresse'][:35])}) Tj ET"
        )
        y_cli -= 10
    if cli["cp_ville"]:
        cmds.append(
            f"0.300 0.300 0.300 rg BT /F1 8 Tf 340 {y_cli} Td ({clean_pdf_str(cli['cp_ville'][:35])}) Tj ET"
        )
        y_cli -= 10
    if cli["siret"]:
        cmds.append(
            f"0.400 0.400 0.400 rg BT /F1 7 Tf 340 {y_cli} Td (SIRET : {clean_pdf_str(cli['siret'])}) Tj ET"
        )

    # Titre du document
    cmds.append("0.117 0.227 0.541 rg 40 685 515 22 re f")
    cmds.append(
        f"1 1 1 rg BT /F1 10 Tf 50 692 Td ({clean_pdf_str(type_doc)} N* {clean_pdf_str(num_doc)}) Tj ET"
    )

    # Entête du tableau
    cmds.append("0.952 0.956 0.964 rg 40 655 515 20 re f")
    cmds.append("0.121 0.160 0.215 rg BT /F1 8 Tf 45 661 Td (Designation) Tj ET")
    cmds.append("BT /F1 8 Tf 320 661 Td (Qte) Tj ET")
    cmds.append("BT /F1 8 Tf 410 661 Td (P.U. HT) Tj ET")
    cmds.append("BT /F1 8 Tf 500 661 Td (Total HT) Tj ET")

    y = 638
    total_ht = 0.0
    total_tva = 0.0

    for item in items:
        desc = str(
            item.get("designation", item.get("nom", item.get("description", "Article")))
        )[:45]
        try:
            qte = float(item.get("quantite", item.get("qte", item.get("qty", 1))))
        except (ValueError, TypeError):
            qte = 1.0
        try:
            pu = float(
                item.get(
                    "prix_ht",
                    item.get("pu_ht", item.get("prix_unitaire_ht", item.get("prix", 0))),
                )
            )
        except (ValueError, TypeError):
            pu = 0.0

        try:
            taux_tva = (
                float(item.get("taux_tva", item.get("tva", 0.0)))
                if ent["assujetti"]
                else 0.0
            )
        except (ValueError, TypeError):
            taux_tva = 0.0

        ligne_ht = qte * pu
        ligne_tva = ligne_ht * (taux_tva / 100.0)

        total_ht += ligne_ht
        total_tva += ligne_tva

        cmds.append(f"BT /F1 8 Tf 45 {y} Td ({clean_pdf_str(desc)}) Tj ET")
        cmds.append(f"BT /F1 8 Tf 320 {y} Td ({qte:g}) Tj ET")
        cmds.append(f"BT /F1 8 Tf 410 {y} Td ({pu:.2f} EUR) Tj ET")
        cmds.append(f"BT /F1 8 Tf 500 {y} Td ({ligne_ht:.2f} EUR) Tj ET")
        cmds.append(f"0.898 0.905 0.921 RG 40 {y-4} m 555 {y-4} l S")
        y -= 18

    tot_ht_doc = float(doc_data.get("total_ht", doc_data.get("montant_ht", total_ht)))
    tot_tva_doc = (
        float(doc_data.get("montant_tva", doc_data.get("tva", total_tva)))
        if ent["assujetti"]
        else 0.0
    )
    tot_ttc_doc = float(
        doc_data.get("total_ttc", doc_data.get("montant_ttc", tot_ht_doc + tot_tva_doc))
    )

    y_blocks = max(y - 15, 180)

    # Totaux
    cmds.append(
        f"0.121 0.160 0.215 rg BT /F1 9 Tf 380 {y_blocks} Td (Total HT : {tot_ht_doc:.2f} EUR) Tj ET"
    )
    cmds.append(
        f"BT /F1 9 Tf 380 {y_blocks-15} Td (TVA : {tot_tva_doc:.2f} EUR) Tj ET"
    )
    cmds.append(
        f"0.117 0.227 0.541 rg BT /F1 10 Tf 380 {y_blocks-32} Td (NET A PAYER : {tot_ttc_doc:.2f} EUR) Tj ET"
    )

    # Bloc Signature & Tracé vectoriel
    sig_lines = doc_data.get("signature_lines", doc_data.get("signature_points", []))
    if sig_lines or doc_data.get("statut") == "Signé":
        date_sig = doc_data.get("date_signature") or datetime.now().strftime(
            "%d/%m/%Y à %H:%M"
        )
        data_to_hash = f"{num_doc}{tot_ttc_doc}{date_sig}{sig_lines}".encode("utf-8")
        doc_hash = hashlib.sha256(data_to_hash).hexdigest()[:16].upper()

        box_x, box_y, box_w, box_h = 40, y_blocks - 65, 220, 65

        cmds.append(f"0.972 0.980 0.988 rg {box_x} {box_y} {box_w} {box_h} re f")
        cmds.append(f"0.796 0.835 0.882 RG 1 w {box_x} {box_y} {box_w} {box_h} re S")

        cmds.append(
            f"0.117 0.227 0.541 rg BT /F1 7 Tf {box_x + 6} {box_y + box_h - 10} Td (SIGNATURE ELECTRONIQUE SIMPLE) Tj ET"
        )
        cmds.append(
            f"0.300 0.300 0.300 rg BT /F1 6 Tf {box_x + 6} {box_y + box_h - 17} Td (Signe le {clean_pdf_str(date_sig)}) Tj ET"
        )

        if sig_lines:
            cmds.append("q")
            cmds.append("0.000 0.000 0.000 RG 1.5 w")
            scale_x = (box_w - 12) / 320.0
            scale_y = (box_h - 26) / 140.0
            top_y = box_y + box_h - 20

            for line in sig_lines:
                if isinstance(line, dict):
                    x1, y1, x2, y2 = (
                        float(line.get("x1", 0)),
                        float(line.get("y1", 0)),
                        float(line.get("x2", 0)),
                        float(line.get("y2", 0)),
                    )
                elif isinstance(line, (list, tuple)) and len(line) == 4:
                    x1, y1, x2, y2 = (
                        float(line[0]),
                        float(line[1]),
                        float(line[2]),
                        float(line[3]),
                    )
                else:
                    continue

                px1 = (box_x + 6) + (x1 * scale_x)
                py1 = top_y - (y1 * scale_y)
                px2 = (box_x + 6) + (x2 * scale_x)
                py2 = top_y - (y2 * scale_y)
                cmds.append(f"{px1:.2f} {py1:.2f} m {px2:.2f} {py2:.2f} l S")
            cmds.append("Q")

        cmds.append(
            f"0.400 0.400 0.400 rg BT /F1 5.5 Tf {box_x + 6} {box_y + 4} Td (ID Preuve : {doc_hash}) Tj ET"
        )

    # Bas de page
    y_leg = 45
    mention_tva_txt = doc_data.get("mention_tva") or ent["mention_tva"]
    if (not ent["assujetti"] or tot_tva_doc == 0) and mention_tva_txt:
        cmds.append(
            f"0.419 0.447 0.502 rg BT /F1 7 Tf 40 {y_leg} Td ({clean_pdf_str(mention_tva_txt)}) Tj ET"
        )
        y_leg -= 10
    if ent["conditions_reglement"]:
        cmds.append(
            f"0.419 0.447 0.502 rg BT /F1 7 Tf 40 {y_leg} Td ({clean_pdf_str(ent['conditions_reglement'])}) Tj ET"
        )
        y_leg -= 10
    if ent["rc_pro"]:
        cmds.append(
            f"0.419 0.447 0.502 rg BT /F1 7 Tf 40 {y_leg} Td ({clean_pdf_str(ent['rc_pro'])}) Tj ET"
        )

    stream_data = "\n".join(cmds).encode("latin-1", "replace")

    objects = []
    offsets = []

    def add_obj(body):
        offsets.append(sum(len(o) for o in objects))
        obj_id = len(offsets)
        objects.append(f"{obj_id} 0 obj\n".encode("latin-1") + body + b"\nendobj\n")
        return obj_id

    objects.append(b"%PDF-1.4\n")
    add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(b"<< /Type /Pages /Kinds [3 0 R] /Count 1 /Kids [3 0 R] >>")
    add_obj(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources 4 0 R /Contents 6 0 R >>"
    )
    add_obj(b"<< /Font << /F1 5 0 R >> >>")
    add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add_obj(
        f"<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1")
        + stream_data
        + b"\nendstream"
    )

    xref_offset = sum(len(o) for o in objects)
    xref = [f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode("latin-1")]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
        "latin-1"
    )

    with open(target_path, "wb") as f:
        for obj in objects:
            f.write(obj)
        for xr in xref:
            f.write(xr)
        f.write(trailer)


# ----------------------------------------------------------------------
# Composant PDFViewer Flet
# ----------------------------------------------------------------------
class PDFViewer(ft.Container):
    def __init__(self, app=None, doc=None, document=None, on_back=None, **kwargs):
        super().__init__()
        self.app = app
        self.on_back_callback = on_back
        self.expand = True
        self.padding = 10

        self.document = doc or document
        self.zoom = 1.0
        self.data_dir = self._resolve_data_dir()

        self.accent_color = "#1E3A8A"
        if (
            self.app
            and hasattr(self.app, "entreprise")
            and isinstance(self.app.entreprise, dict)
        ):
            self.accent_color = self.app.entreprise.get("accent_color", "#1E3A8A")

        self.pdf_pages_column = ft.Column(
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self._build_interface()

    def _resolve_data_dir(self):
        try:
            if self.app and hasattr(self.app, "data_dir"):
                p = Path(self.app.data_dir)
                p.mkdir(parents=True, exist_ok=True)
                return p
        except Exception:
            pass

        base = Path(tempfile.gettempdir()) / "app_data"
        base.mkdir(parents=True, exist_ok=True)
        return base

    @property
    def doc(self):
        return self.document

    @doc.setter
    def doc(self, value):
        self.document = value

    def did_mount(self):
        self._load_document_from_app()

    def retour(self, e=None):
        if callable(self.on_back_callback):
            self.on_back_callback(e)
            return

        if self.app:
            for method in ["navigate_to", "go_back", "retour", "fermer_pdf"]:
                if hasattr(self.app, method) and callable(getattr(self.app, method)):
                    try:
                        func = getattr(self.app, method)
                        func("Facturation") if method == "navigate_to" else func()
                        return
                    except Exception:
                        pass

        self.visible = False
        page = getattr(self, "page", None) or (
            getattr(self.app, "page", None) if self.app else None
        )
        if page:
            if hasattr(page, "views") and len(page.views) > 1:
                page.views.pop()
                page.go(page.views[-1].route or "/")
            else:
                page.update()

    def _open_control(self, control):
        page = getattr(self, "page", None) or (
            getattr(self.app, "page", None) if self.app else None
        )
        if not page:
            return
        try:
            if hasattr(page, "open"):
                page.open(control)
            elif hasattr(page, "dialog"):
                page.dialog = control
                control.open = True
                page.update()
            else:
                if control not in page.overlay:
                    page.overlay.append(control)
                control.open = True
                page.update()
        except Exception as e:
            print(f"Erreur d'ouverture : {e}")

    def _close_control(self, control):
        page = getattr(self, "page", None) or (
            getattr(self.app, "page", None) if self.app else None
        )
        if not page:
            return
        try:
            if hasattr(page, "close"):
                page.close(control)
            else:
                control.open = False
                page.update()
        except Exception as e:
            print(f"Erreur de fermeture : {e}")

    def _load_document_from_app(self):
        if not self.document and self.app:
            self.document = getattr(
                self.app, "current_document", None
            ) or getattr(self.app, "selected_document", None)

        if not self.document:
            self.pdf_pages_column.controls.clear()
            self.pdf_pages_column.controls.append(
                ft.Container(
                    content=ft.Text(
                        "Aucun document chargé.", size=14, color="white"
                    ),
                    alignment=CENTER,
                    padding=40,
                )
            )
            self.update_ui()
            return

        self.display_pdf()

    def update_ui(self):
        try:
            if self.page:
                self.page.update()
            else:
                self.update()
        except Exception:
            pass

    def get_path(self):
        if not self.document:
            return None
        folder = self.data_dir / "pdfs" / "Documents"
        folder.mkdir(parents=True, exist_ok=True)
        num_doc = (
            self.doc.get("numero", "TEMP_DOC")
            if isinstance(self.doc, dict)
            else "TEMP_DOC"
        )
        return folder / f"{num_doc}.pdf"

    def generer_pdf_pro(self, silent=False):
        if not self.doc:
            return None
        path = self.get_path()
        entreprise_data = getattr(self.app, "entreprise", {}) if self.app else {}

        try:
            generer_pdf_zero_dep(self.doc, path, entreprise_data)
            if not silent:
                self.show_snack("Fichier PDF généré avec succès ✔")
            return path
        except Exception as ex:
            self.show_snack(f"Erreur de génération PDF : {ex}", is_error=True)
            return None

    def sauvegarder_dans_telechargements(self, e=None):
        if not self.doc:
            self.show_snack("Aucun document à sauvegarder.", is_error=True)
            return None

        temp_pdf = self.generer_pdf_pro(silent=True)
        if not temp_pdf or not temp_pdf.exists():
            self.show_snack("Échec de la génération du PDF.", is_error=True)
            return None

        try:
            ent = extract_entreprise_info(
                getattr(self.app, "entreprise", {}) if self.app else {}
            )
            nom_entreprise = ent.get("nom", "Factures")
            dossier_clean = (
                "".join(
                    c for c in nom_entreprise if c.isalnum() or c in (" ", "_", "-")
                ).strip()
                or "Factures"
            )

            target_dir = get_download_dir(folder_name=dossier_clean)
            num_doc = self.doc.get("numero", "DOCUMENT")
            dest_path = target_dir / f"{num_doc}.pdf"

            shutil.copy(temp_pdf, dest_path)
            self.show_snack(
                f"Enregistré dans Download/{dossier_clean}/{dest_path.name} ✔"
            )
            return dest_path
        except Exception as ex:
            self.show_snack(f"Erreur d'exportation : {ex}", is_error=True)
            return None

    def ouvrir_pdf_externe(self, e=None):
        path = (
            self.sauvegarder_dans_telechargements()
            or self.generer_pdf_pro(silent=True)
            or self.get_path()
        )
        if path and path.exists():
            try:
                page = getattr(self, "page", None) or (
                    getattr(self.app, "page", None) if self.app else None
                )
                if page:
                    page.launch_url(f"file://{path.absolute()}")
            except Exception as ex:
                self.show_snack(f"Impossible d'ouvrir le fichier : {ex}", is_error=True)

    def imprimer_document(self, e=None):
        """Affiche les imprimantes système ou redirige vers le gestionnaire d'impression Android."""
        path = self.generer_pdf_pro(silent=True) or self.get_path()
        if not path or not path.exists():
            self.show_snack("Fichier non disponible pour impression.", is_error=True)
            return

        is_android = (
            "ANDROID_STORAGE" in os.environ
            or "ANDROID_ROOT" in os.environ
            or hasattr(sys, "getandroidapilevel")
        )

        if is_android:
            # Sur Android, le spool d'impression est géré par la visionneuse système intégrée
            self.ouvrir_pdf_externe()
            self.show_snack("Ouverture du document pour le service d'impression Android ✔")
            return

        printers = get_system_printers()

        if not printers:
            if print_to_printer(path):
                self.show_snack("Document transmis à l'imprimante par défaut ✔")
            else:
                self.ouvrir_pdf_externe()
                self.show_snack("Ouverture dans le lecteur PDF par défaut.", is_error=True)
            return

        dd_printers = ft.Dropdown(
            label="Choisir une imprimante",
            options=[ft.dropdown.Option(p) for p in printers],
            value=printers[0],
            expand=True,
        )

        def lancer_impression(ev):
            selected = dd_printers.value
            self._close_control(print_dialog)
            if selected:
                if print_to_printer(path, selected):
                    self.show_snack(f"Envoyé à l'imprimante '{selected}' ✔")
                else:
                    self.show_snack(f"Erreur d'envoi vers '{selected}'", is_error=True)

        def ouvrir_systeme(ev):
            self._close_control(print_dialog)
            self.ouvrir_pdf_externe()

        print_dialog = ft.AlertDialog(
            title=ft.Text("🖨️ Sélection de l'imprimante", weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("Imprimantes système détectées :", size=12),
                    dd_printers,
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Ouvrir dans le lecteur PDF", on_click=ouvrir_systeme),
                ft.ElevatedButton(
                    "Imprimer",
                    bgcolor=self.accent_color,
                    color="white",
                    on_click=lancer_impression,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self._open_control(print_dialog)

    def envoyer_email(self, e=None):
        """Transmet le PDF généré vers le module MailsView avec la pièce jointe."""
        path = (
            self.sauvegarder_dans_telechargements()
            or self.generer_pdf_pro(silent=True)
            or self.get_path()
        )
        doc = self.document or {}
        cli = extract_client_info(doc.get("client") or doc.get("fournisseur", {}))

        type_doc = resolve_document_type(doc)
        num_doc = doc.get("numero", "N/A")
        email_dest = cli.get("email", "").strip()

        sujet = f"{type_doc} N° {num_doc}"
        corps = (
            f"Bonjour,\n\n"
            f"Veuillez trouver ci-joint votre {type_doc.lower()} N° {num_doc}.\n\n"
            f"Cordialement,"
        )

        if self.app:
            self.app.pending_email = {
                "email": email_dest,
                "sujet": sujet,
                "corps": corps,
                "attachment": path,
            }

            if hasattr(self.app, "mails_view") and self.app.mails_view:
                self.app.mails_view.check_pending_email()

            navigated = False
            for method in ["navigate_to", "go_to", "ouvrir_page", "change_view"]:
                if hasattr(self.app, method) and callable(getattr(self.app, method)):
                    try:
                        getattr(self.app, method)("Mails")
                        navigated = True
                        break
                    except Exception:
                        pass

            if navigated:
                self.show_snack("Redirection vers le module Mail avec la pièce jointe ✔")
                return

        mailto_url = (
            f"mailto:{email_dest}?"
            f"subject={urllib.parse.quote(sujet)}&"
            f"body={urllib.parse.quote(corps)}"
        )

        opened = False
        page = getattr(self, "page", None) or (
            getattr(self.app, "page", None) if self.app else None
        )

        if page and hasattr(page, "launch_url"):
            try:
                page.launch_url(mailto_url)
                opened = True
            except Exception:
                opened = False

        if not opened:
            try:
                webbrowser.open(mailto_url)
                opened = True
            except Exception:
                opened = False

        if opened:
            filename = path.name if path else f"{num_doc}.pdf"
            self.show_snack(
                f"Messagerie externe ouverte ({email_dest or 'sans destinataire'}). Fichier : {filename}"
            )
        else:
            self.show_snack("Impossible d'ouvrir l'application mail.", is_error=True)

    def _safe_float(self, val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _render_flet_preview(self):
        doc = self.document or {}
        ent = extract_entreprise_info(
            doc.get("entreprise")
            or (getattr(self.app, "entreprise", {}) if self.app else {})
        )
        cli = extract_client_info(doc.get("client") or doc.get("fournisseur", {}))

        base_width = int(595 * self.zoom)
        base_height = int(842 * self.zoom)

        num_doc = doc.get("numero", "N/A")
        type_doc = resolve_document_type(doc)

        items = doc.get("articles", doc.get("lignes", []))
        total_ht = 0.0
        total_tva = 0.0
        rows = []

        for item in items:
            desc = str(
                item.get("designation", item.get("nom", item.get("description", "Article")))
            )
            qte = self._safe_float(item.get("quantite", item.get("qte", 1)), 1.0)
            pu = self._safe_float(
                item.get("prix_ht", item.get("pu_ht", item.get("prix", 0))), 0.0
            )
            taux_tva = (
                self._safe_float(item.get("taux_tva", 0.0), 0.0)
                if ent["assujetti"]
                else 0.0
            )

            ligne_ht = qte * pu
            ligne_tva = ligne_ht * (taux_tva / 100.0)

            total_ht += ligne_ht
            total_tva += ligne_tva

            rows.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(desc[:40], size=11, expand=True, color="#1F2937"),
                            ft.Text(
                                f"{qte:g}",
                                size=11,
                                width=40,
                                text_align=ft.TextAlign.CENTER,
                                color="#1F2937",
                            ),
                            ft.Text(
                                f"{pu:.2f} €",
                                size=11,
                                width=70,
                                text_align=ft.TextAlign.RIGHT,
                                color="#1F2937",
                            ),
                            ft.Text(
                                f"{ligne_ht:.2f} €",
                                size=11,
                                width=80,
                                text_align=ft.TextAlign.RIGHT,
                                color="#1F2937",
                            ),
                        ]
                    ),
                    border=safe_border(1, "#E5E7EB"),
                    padding=safe_padding(vertical=4),
                )
            )

        tot_ht_doc = float(doc.get("total_ht", total_ht))
        tot_tva_doc = (
            float(doc.get("montant_tva", total_tva)) if ent["assujetti"] else 0.0
        )
        tot_ttc_doc = float(doc.get("total_ttc", tot_ht_doc + tot_tva_doc))

        sig_lines = doc.get("signature_lines", doc.get("signature_points", []))
        date_sig = doc.get("date_signature") or datetime.now().strftime(
            "%d/%m/%Y à %H:%M"
        )

        if sig_lines:
            data_to_hash = f"{num_doc}{tot_ttc_doc}{date_sig}{sig_lines}".encode(
                "utf-8"
            )
            doc_hash = hashlib.sha256(data_to_hash).hexdigest()[:16].upper()

            preview_shapes = []
            scale_x = 150.0 / 320.0
            scale_y = 35.0 / 140.0

            for line in sig_lines:
                if isinstance(line, dict):
                    x1, y1, x2, y2 = (
                        float(line["x1"]),
                        float(line["y1"]),
                        float(line["x2"]),
                        float(line["y2"]),
                    )
                elif isinstance(line, (list, tuple)) and len(line) == 4:
                    x1, y1, x2, y2 = (
                        float(line[0]),
                        float(line[1]),
                        float(line[2]),
                        float(line[3]),
                    )
                else:
                    continue

                preview_shapes.append(
                    cv.Line(
                        x1 * scale_x,
                        y1 * scale_y,
                        x2 * scale_x,
                        y2 * scale_y,
                        paint=ft.Paint(
                            stroke_width=2.0,
                            color="#000000",
                            stroke_cap=ft.StrokeCap.ROUND,
                            style=ft.PaintingStyle.STROKE,
                        ),
                    )
                )

            sig_canvas = cv.Canvas(shapes=preview_shapes, width=150, height=35)

            sig_control = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "SIGNATURE ÉLECTRONIQUE SIMPLE",
                            size=6.5,
                            weight=ft.FontWeight.BOLD,
                            color=self.accent_color or "#1E3A8A",
                        ),
                        ft.Text(f"Signé le {date_sig}", size=6, color="#4B5563"),
                        sig_canvas,
                        ft.Text(f"ID Preuve : {doc_hash}", size=5.5, color="#6B7280"),
                    ],
                    spacing=1,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                width=165,
                height=75,
                border=safe_border(1, "#CBD5E1"),
                bgcolor="#F8FAFC",
                border_radius=4,
                padding=3,
            )
        else:
            sig_control = ft.Container(
                content=ft.Text(
                    "Non signé", size=9, italic=True, color="#9CA3AF"
                ),
                width=165,
                height=50,
                border=safe_border(1, "#E5E7EB"),
                border_radius=4,
                alignment=CENTER,
            )

        entreprise_controls = [
            ft.Text(
                ent["nom"].upper(),
                weight=ft.FontWeight.BOLD,
                size=13,
                color=self.accent_color,
            ),
        ]
        if ent["adresse"]:
            entreprise_controls.append(
                ft.Text(ent["adresse"], size=9, color="#4B5563")
            )
        if ent["cp_ville"]:
            entreprise_controls.append(
                ft.Text(ent["cp_ville"], size=9, color="#4B5563")
            )
        entreprise_controls.append(
            ft.Text(f"SIRET : {ent['siret']}", size=9, color="#6B7280")
        )
        entreprise_controls.append(
            ft.Text(f"Email : {ent['email']}", size=9, color="#6B7280")
        )

        client_controls = [
            ft.Text(
                "DESTINATAIRE :",
                weight=ft.FontWeight.BOLD,
                size=9,
                color=self.accent_color,
            ),
            ft.Text(
                cli["nom"], weight=ft.FontWeight.BOLD, size=10, color="#1F2937"
            ),
        ]
        if cli["adresse"]:
            client_controls.append(ft.Text(cli["adresse"], size=9, color="#4B5563"))
        if cli["cp_ville"]:
            client_controls.append(ft.Text(cli["cp_ville"], size=9, color="#4B5563"))

        legal_controls = []
        mention_tva_txt = doc.get("mention_tva") or ent["mention_tva"]
        if (not ent["assujetti"] or tot_tva_doc == 0) and mention_tva_txt:
            legal_controls.append(
                ft.Text(mention_tva_txt, size=8, color="#6B7280", italic=True)
            )
        if ent["conditions_reglement"]:
            legal_controls.append(
                ft.Text(
                    f"Conditions : {ent['conditions_reglement']}",
                    size=8,
                    color="#6B7280",
                )
            )
        if ent["rc_pro"]:
            legal_controls.append(
                ft.Text(f"RC Pro : {ent['rc_pro']}", size=8, color="#6B7280")
            )

        footer_legal = ft.Column(
            controls=[
                ft.Divider(height=1, color="#CBD5E1"),
                *legal_controls,
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        a4_sheet = ft.Container(
            width=base_width,
            height=base_height,
            bgcolor="white",
            padding=int(25 * self.zoom),
            border_radius=4,
            shadow=ft.BoxShadow(blur_radius=10, color="#40000000"),
            content=ft.Column(
                [
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Column(entreprise_controls, spacing=2),
                                    ft.Container(
                                        content=ft.Column(client_controls, spacing=2),
                                        bgcolor="#F3F4F6",
                                        padding=8,
                                        border_radius=4,
                                        width=200,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(height=10),
                            ft.Container(
                                content=ft.Text(
                                    f"{type_doc} N° {num_doc}",
                                    weight=ft.FontWeight.BOLD,
                                    color="white",
                                    size=12,
                                ),
                                bgcolor=self.accent_color,
                                padding=safe_padding(horizontal=10, vertical=5),
                                border_radius=4,
                            ),
                            ft.Container(height=10),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Text(
                                            "Désignation",
                                            weight=ft.FontWeight.BOLD,
                                            size=10,
                                            expand=True,
                                            color="#1F2937",
                                        ),
                                        ft.Text(
                                            "Qté",
                                            weight=ft.FontWeight.BOLD,
                                            size=10,
                                            width=40,
                                            text_align=ft.TextAlign.CENTER,
                                            color="#1F2937",
                                        ),
                                        ft.Text(
                                            "P.U. HT",
                                            weight=ft.FontWeight.BOLD,
                                            size=10,
                                            width=70,
                                            text_align=ft.TextAlign.RIGHT,
                                            color="#1F2937",
                                        ),
                                        ft.Text(
                                            "Total HT",
                                            weight=ft.FontWeight.BOLD,
                                            size=10,
                                            width=80,
                                            text_align=ft.TextAlign.RIGHT,
                                            color="#1F2937",
                                        ),
                                    ]
                                ),
                                bgcolor="#F3F4F6",
                                padding=6,
                            ),
                            ft.Column(controls=rows, spacing=0),
                            ft.Container(height=15),
                            ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(
                                                "Signature client :",
                                                weight=ft.FontWeight.BOLD,
                                                size=9,
                                                color=self.accent_color,
                                            ),
                                            sig_control,
                                        ],
                                        spacing=4,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Text(
                                                        "Total HT :",
                                                        size=10,
                                                        color="#1F2937",
                                                    ),
                                                    ft.Text(
                                                        f"{tot_ht_doc:.2f} €",
                                                        size=10,
                                                        weight=ft.FontWeight.BOLD,
                                                        color="#1F2937",
                                                    ),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                width=180,
                                            ),
                                            ft.Row(
                                                [
                                                    ft.Text(
                                                        "TVA :",
                                                        size=10,
                                                        color="#1F2937",
                                                    ),
                                                    ft.Text(
                                                        f"{tot_tva_doc:.2f} €",
                                                        size=10,
                                                        color="#1F2937",
                                                    ),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                width=180,
                                            ),
                                            ft.Divider(height=1),
                                            ft.Row(
                                                [
                                                    ft.Text(
                                                        "NET À PAYER :",
                                                        size=11,
                                                        weight=ft.FontWeight.BOLD,
                                                        color=self.accent_color,
                                                    ),
                                                    ft.Text(
                                                        f"{tot_ttc_doc:.2f} €",
                                                        size=11,
                                                        weight=ft.FontWeight.BOLD,
                                                        color=self.accent_color,
                                                    ),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                width=180,
                                            ),
                                        ],
                                        spacing=3,
                                        horizontal_alignment=ft.CrossAxisAlignment.END,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                            ),
                        ],
                    ),
                    ft.Container(height=20),
                    footer_legal,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

        self.pdf_pages_column.controls.append(
            ft.Container(
                content=a4_sheet,
                alignment=CENTER,
                margin=safe_margin(vertical=10),
            )
        )

    def display_pdf(self):
        self.pdf_pages_column.controls.clear()
        try:
            self._render_flet_preview()
        except Exception as err:
            self.pdf_pages_column.controls.append(
                ft.Container(
                    content=ft.Text(
                        f"Erreur d'affichage : {err}", color="red", size=12
                    ),
                    padding=20,
                    bgcolor="#FEF2F2",
                    border_radius=6,
                )
            )
        self.update_ui()

    def _build_interface(self):
        toolbar = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "⬅️ Retour",
                    bgcolor="#475569",
                    color="white",
                    on_click=self.retour,
                ),
                ft.ElevatedButton(
                    "💾 Enregistrer (Download)",
                    bgcolor=self.accent_color,
                    color="white",
                    on_click=self.sauvegarder_dans_telechargements,
                ),
                ft.ElevatedButton(
                    "📄 Exporter PDF",
                    bgcolor="#2563EB",
                    color="white",
                    on_click=lambda _: self.generer_pdf_pro(silent=False),
                ),
                ft.ElevatedButton(
                    "👁️ Ouvrir",
                    bgcolor="#4B5563",
                    color="white",
                    on_click=self.ouvrir_pdf_externe,
                ),
                ft.ElevatedButton(
                    "✍️ Signer",
                    bgcolor="#8E44AD",
                    color="white",
                    on_click=self.lancer_signature_pad,
                ),
                ft.ElevatedButton(
                    "✉️ Mail",
                    bgcolor="#0284C7",
                    color="white",
                    on_click=self.envoyer_email,
                ),
                ft.ElevatedButton(
                    "🖨️ Imprimer",
                    bgcolor="#0D9488",
                    color="white",
                    on_click=self.imprimer_document,
                ),
                ft.ElevatedButton(
                    "🔍 +",
                    bgcolor="#2C3E50",
                    color="white",
                    on_click=lambda _: self.ajuster_zoom(0.2),
                ),
                ft.ElevatedButton(
                    "🔍 -",
                    bgcolor="#2C3E50",
                    color="white",
                    on_click=lambda _: self.ajuster_zoom(-0.2),
                ),
            ],
            wrap=True,
            spacing=8,
        )

        viewer_area = ft.Container(
            content=self.pdf_pages_column,
            alignment=CENTER,
            bgcolor="#1E293B",
            border_radius=8,
            padding=10,
            expand=True,
        )

        self.content = ft.Column(
            controls=[toolbar, viewer_area], spacing=10, expand=True
        )

    def ajuster_zoom(self, delta):
        self.zoom = max(0.6, min(2.5, self.zoom + delta))
        self.display_pdf()

    def lancer_signature_pad(self, e):
        canvas_w, canvas_h = 320, 140
        canvas_control = cv.Canvas(width=canvas_w, height=canvas_h, shapes=[])

        state = {"last_x": None, "last_y": None, "raw_lines": []}

        def on_pan_start(ev: ft.DragStartEvent):
            x = getattr(ev, "local_x", None) or getattr(ev, "x", 0.0)
            y = getattr(ev, "local_y", None) or getattr(ev, "y", 0.0)
            state["last_x"] = max(0.0, min(float(canvas_w), float(x)))
            state["last_y"] = max(0.0, min(float(canvas_h), float(y)))

        def on_pan_update(ev: ft.DragUpdateEvent):
            lx = getattr(ev, "local_x", None)
            ly = getattr(ev, "local_y", None)

            if lx is not None and ly is not None:
                cur_x, cur_y = float(lx), float(ly)
            elif state["last_x"] is not None and state["last_y"] is not None:
                dx = getattr(ev, "delta_x", 0.0) or 0.0
                dy = getattr(ev, "delta_y", 0.0) or 0.0
                cur_x = state["last_x"] + float(dx)
                cur_y = state["last_y"] + float(dy)
            else:
                return

            cur_x = max(0.0, min(float(canvas_w), cur_x))
            cur_y = max(0.0, min(float(canvas_h), cur_y))

            if state["last_x"] is not None and state["last_y"] is not None:
                line_shape = cv.Line(
                    state["last_x"],
                    state["last_y"],
                    cur_x,
                    cur_y,
                    paint=ft.Paint(
                        stroke_width=2.5,
                        color="#000000",
                        stroke_cap=ft.StrokeCap.ROUND,
                        style=ft.PaintingStyle.STROKE,
                    ),
                )
                canvas_control.shapes.append(line_shape)
                state["raw_lines"].append(
                    {
                        "x1": state["last_x"],
                        "y1": state["last_y"],
                        "x2": cur_x,
                        "y2": cur_y,
                    }
                )
                canvas_control.update()

            state["last_x"], state["last_y"] = cur_x, cur_y

        def on_pan_end(ev: ft.DragEndEvent):
            state["last_x"], state["last_y"] = None, None

        def clear_canvas(ev):
            canvas_control.shapes.clear()
            state["raw_lines"].clear()
            canvas_control.update()

        def valider_signature(ev):
            if not state["raw_lines"]:
                self.show_snack("Veuillez apposer une signature.", is_error=True)
                return

            date_str = datetime.now().strftime("%d/%m/%Y à %H:%M")

            if isinstance(self.doc, dict):
                self.doc["statut"] = "Signé"
                self.doc["date_signature"] = date_str
                self.doc["signature_lines"] = list(state["raw_lines"])

            if self.app:
                for attr in [
                    "current_document",
                    "selected_document",
                    "facture_active",
                ]:
                    if hasattr(self.app, attr) and isinstance(
                        getattr(self.app, attr), dict
                    ):
                        doc_target = getattr(self.app, attr)
                        doc_target["statut"] = "Signé"
                        doc_target["date_signature"] = date_str
                        doc_target["signature_lines"] = list(state["raw_lines"])

                for save_func in [
                    "save_data",
                    "sauvegarder_document",
                    "save_document",
                    "enregistrer_facture",
                ]:
                    if hasattr(self.app, save_func) and callable(
                        getattr(self.app, save_func)
                    ):
                        try:
                            func = getattr(self.app, save_func)
                            func(self.doc) if getattr(
                                func, "__code__", None
                            ) and func.__code__.co_argcount > 1 else func()
                        except Exception:
                            pass

            self._close_control(sig_dialog)
            self.display_pdf()
            self.sauvegarder_dans_telechargements()
            self.show_snack("Document signé et enregistré ✔")

        gesture_detector = ft.GestureDetector(
            content=ft.Container(
                content=canvas_control,
                width=canvas_w,
                height=canvas_h,
                bgcolor="#FFFFFF",
                border=safe_border(1, "#D1D5DB"),
                border_radius=6,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
            ),
            on_pan_start=on_pan_start,
            on_pan_update=on_pan_update,
            on_pan_end=on_pan_end,
        )

        sig_dialog = ft.AlertDialog(
            title=ft.Text(
                "✍️ Signature Électronique", size=15, weight=ft.FontWeight.BOLD
            ),
            content=ft.Column(
                [ft.Text("Signez ci-dessous :", size=12), gesture_detector],
                tight=True,
                spacing=8,
            ),
            actions=[
                ft.ElevatedButton(
                    "Effacer",
                    bgcolor="#EF4444",
                    color="white",
                    on_click=clear_canvas,
                ),
                ft.ElevatedButton(
                    "Valider",
                    bgcolor="#16A34A",
                    color="white",
                    on_click=valider_signature,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self._open_control(sig_dialog)

    def show_snack(self, message, is_error=False):
        snack = ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor="#B91C1C" if is_error else "#15803D",
            duration=3000,
        )
        self._open_control(snack)


# ----------------------------------------------------------------------
# Exécution de Démonstration Autonome
# ----------------------------------------------------------------------
def demo_main(page: ft.Page):
    page.title = "Aperçu & Signature PDF"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10

    doc_demo = {
        "numero": "BL-2026-001",
        "type": "bon_livraison",
        "client": {
            "nom": "ACME Industries SAS",
            "adresse": "12 Rue des Entreprises",
            "code_postal": "75001",
            "ville": "Paris",
            "siret": "987 654 321 00019",
            "email": "comptabilite@acme.fr",
        },
        "articles": [
            {
                "designation": "Matériel réseau et baies",
                "quantite": 2,
                "prix_unitaire_ht": 450.0,
            },
            {
                "designation": "Prestation d'installation",
                "quantite": 1,
                "prix_unitaire_ht": 1200.0,
            },
        ],
        "total_ht": 2100.0,
        "montant_tva": 0.0,
        "total_ttc": 2100.0,
    }

    class AppMock:
        def __init__(self):
            self.page = page
            self.data_dir = tempfile.gettempdir()
            self.entreprise = {
                "nom": "MON ENTREPRISE DEMO",
                "adresse": "5 Avenue du Général de Gaulle",
                "code_postal": "35000",
                "ville": "Rennes",
                "siret": "123 456 789 00012",
                "email": "contact@demo.fr",
                "assujetti_tva": False,
                "mention_tva": "TVA non applicable, art. 293 B du CGI",
                "conditions_reglement": "Paiement à 30 jours",
                "rc_pro": "Assurance AXA N° 12345678",
                "accent_color": "#1E3A8A",
            }

        def go_back(self):
            print("Retour déclenché !")

    app_mock = AppMock()
    viewer = PDFViewer(app=app_mock, doc=doc_demo)
    page.add(viewer)


if __name__ == "__main__":
    ft.app(target=demo_main)