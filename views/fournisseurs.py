import csv
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
import tempfile
import flet as ft


def safe_border(width=1, color="#424242"):
    """Bordure universelle sécurisée."""
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def safe_icon(name, fallback="arrow_back"):
    """Récupère une icône de manière sécurisée quelle que soit la version de Flet."""
    for container in (getattr(ft, "Icons", None), getattr(ft, "icons", None)):
        if container and hasattr(container, name):
            val = getattr(container, name)
            if val:
                return val
    return fallback


def parse_float(val, default=0.0):
    """Convertit n'importe quel type en float sécurisé."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        clean_str = str(val).replace("€", "").replace(" ", "").replace(",", ".").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default


def extract_fournisseur_name(fourn_data):
    """Extrait le nom du fournisseur depuis un dictionnaire ou une chaîne."""
    if isinstance(fourn_data, dict):
        return (
            fourn_data.get("nom")
            or fourn_data.get("entreprise")
            or fourn_data.get("contact_nom")
            or "Inconnu"
        )
    if isinstance(fourn_data, str) and fourn_data.strip():
        return fourn_data.strip()
    return "Inconnu"


def calculate_doc_ttc(doc):
    """Calcule le montant total TTC d'un document fournisseur."""
    for key in ["total_ttc", "montant_ttc"]:
        if key in doc and doc[key] is not None:
            val = parse_float(doc[key], -1.0)
            if val > 0:
                return val

    items = doc.get("lignes") or doc.get("articles") or []
    total_ttc = 0.0
    for item in items:
        tot_ligne = parse_float(item.get("total_ttc", item.get("prix_ttc")), -1.0)
        if tot_ligne >= 0:
            total_ttc += tot_ligne
        else:
            qte = parse_float(item.get("quantite", item.get("qte", 1)))
            prix = parse_float(item.get("prix_unitaire", item.get("pu", item.get("prix_ht", item.get("pu_ht", 0)))))
            tva = parse_float(item.get("taux_tva", item.get("tva", 20.0)))
            total_ttc += qte * prix * (1 + tva / 100)

    if total_ttc > 0:
        return total_ttc

    return parse_float(doc.get("total_ht", doc.get("montant_ht", 0.0)))


def calculate_doc_ht(doc):
    """Calcule le montant total HT d'un document fournisseur."""
    for key in ["total_ht", "montant_ht"]:
        if key in doc and doc[key] is not None:
            val = parse_float(doc[key], -1.0)
            if val > 0:
                return val

    items = doc.get("lignes") or doc.get("articles") or []
    total_ht = 0.0
    for item in items:
        tot_l = parse_float(item.get("total_ht"), -1.0)
        if tot_l >= 0:
            total_ht += tot_l
        else:
            qte = parse_float(item.get("quantite", item.get("qte", 1)))
            prix = parse_float(item.get("prix_unitaire", item.get("pu", item.get("prix_ht", item.get("pu_ht", 0)))))
            total_ht += qte * prix

    return total_ht


# ----------------------------------------------------------------------
# Moteur PDF Pure Python (Zéro Dépendance ReportLab)
# ----------------------------------------------------------------------
def generer_pdf_zero_dep(doc_data, target_path, entreprise_data):
    ent = {
        "nom": entreprise_data.get("nom", "MON ENTREPRISE") if isinstance(entreprise_data, dict) else "MON ENTREPRISE",
        "adresse": entreprise_data.get("adresse", "") if isinstance(entreprise_data, dict) else "",
        "cp_ville": f"{entreprise_data.get('code_postal', '')} {entreprise_data.get('ville', '')}".strip() if isinstance(entreprise_data, dict) else "",
        "siret": entreprise_data.get("siret", "-") if isinstance(entreprise_data, dict) else "-",
        "email": entreprise_data.get("email", "-") if isinstance(entreprise_data, dict) else "-",
        "assujetti": True,
        "mention_tva": "TVA non applicable, art. 293 B du CGI",
        "conditions_reglement": entreprise_data.get("conditions_reglement", "") if isinstance(entreprise_data, dict) else "",
        "rc_pro": entreprise_data.get("rc_pro", "") if isinstance(entreprise_data, dict) else "",
    }
    
    fourn = doc_data.get("fournisseur", {})
    cli = {
        "nom": extract_fournisseur_name(fourn),
        "adresse": fourn.get("adresse", "") if isinstance(fourn, dict) else "",
        "cp_ville": f"{fourn.get('code_postal', '')} {fourn.get('ville', '')}".strip() if isinstance(fourn, dict) else "",
        "siret": fourn.get("siret", "") if isinstance(fourn, dict) else "",
    }

    type_doc = "BON DE COMMANDE" if doc_data.get("type") == "bon_commande" else "BON DE LIVRAISON"
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

    # Cartouche Fournisseur / Destinataire
    cmds.append("0.952 0.956 0.964 rg 330 720 225 80 re f")
    cmds.append("0.117 0.227 0.541 rg BT /F1 8 Tf 340 786 Td (FOURNISSEUR :) Tj ET")
    cmds.append(
        "0.121 0.160 0.215 rg BT /F1 10 Tf 340 772 Td ("
        + clean_pdf_str(cli["nom"][:32])
        + ") Tj ET"
    )

    y_cli = 758
    if cli["adresse"]:
        cmds.append(f"0.300 0.300 0.300 rg BT /F1 8 Tf 340 {y_cli} Td ({clean_pdf_str(cli['adresse'][:35])}) Tj ET")
        y_cli -= 10
    if cli["cp_ville"]:
        cmds.append(f"0.300 0.300 0.300 rg BT /F1 8 Tf 340 {y_cli} Td ({clean_pdf_str(cli['cp_ville'][:35])}) Tj ET")
        y_cli -= 10
    if cli["siret"]:
        cmds.append(f"0.400 0.400 0.400 rg BT /F1 7 Tf 340 {y_cli} Td (SIRET : {clean_pdf_str(cli['siret'])}) Tj ET")

    # Titre du document
    cmds.append("0.117 0.227 0.541 rg 40 685 515 22 re f")
    cmds.append(f"1 1 1 rg BT /F1 10 Tf 50 692 Td ({clean_pdf_str(type_doc)} N* {clean_pdf_str(num_doc)}) Tj ET")

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
        desc = str(item.get("designation", item.get("nom", "Article")))[:45]
        qte = parse_float(item.get("quantite", item.get("qte", 1)), 1.0)
        pu = parse_float(item.get("prix_unitaire", item.get("pu", item.get("prix_ht", 0))), 0.0)
        taux_tva = parse_float(item.get("taux_tva", item.get("tva", 20.0)), 20.0)

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

    tot_ht_doc = calculate_doc_ht(doc_data)
    tot_ttc_doc = calculate_doc_ttc(doc_data)
    tot_tva_doc = max(0.0, tot_ttc_doc - tot_ht_doc)

    y_blocks = max(y - 15, 180)

    # Totaux
    cmds.append(f"0.121 0.160 0.215 rg BT /F1 9 Tf 380 {y_blocks} Td (Total HT : {tot_ht_doc:.2f} EUR) Tj ET")
    cmds.append(f"BT /F1 9 Tf 380 {y_blocks-15} Td (TVA : {tot_tva_doc:.2f} EUR) Tj ET")
    cmds.append(f"0.117 0.227 0.541 rg BT /F1 10 Tf 380 {y_blocks-32} Td (NET A PAYER : {tot_ttc_doc:.2f} EUR) Tj ET")

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
    add_obj(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources 4 0 R /Contents 6 0 R >>")
    add_obj(b"<< /Font << /F1 5 0 R >> >>")
    add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    add_obj(f"<< /Length {len(stream_data)} >>\nstream\n".encode("latin-1") + stream_data + b"\nendstream")

    xref_offset = sum(len(o) for o in objects)
    xref = [f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode("latin-1")]
    for off in offsets:
        xref.append(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")

    with open(target_path, "wb") as f:
        for obj in objects:
            f.write(obj)
        for xr in xref:
            f.write(xr)
        f.write(trailer)


class FournisseursView(ft.Container):
    """Vue Flet autonome et sécurisée pour la gestion des fournisseurs et documents (BC/BL)."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 10

        self.accent_color = (
            getattr(self.app, "entreprise", {}).get("accent_color", "#2B719E")
            if hasattr(self.app, "entreprise")
            else "#2B719E"
        )

        self.documents = {}
        self.selected_doc_key = None
        self.selected_fournisseur = None
        self.current_tab_index = 0

        self.display_container_fourn = ft.Container(expand=True)
        self.display_container_docs = ft.Container(expand=True)

        self.main_layout = ft.Column(spacing=10, expand=True)
        self.content = self.main_layout
        self._build_interface()

    def _get_page(self, e=None):
        if e and hasattr(e, "control") and e.control and getattr(e.control, "page", None):
            return e.control.page
        if e and hasattr(e, "page") and getattr(e, "page", None):
            return e.page
        if self.page:
            return self.page
        return getattr(self.app, "page", None)

    def safe_update(self):
        page = self._get_page()
        if page:
            try:
                page.update()
            except Exception:
                try:
                    self.update()
                except Exception:
                    pass

    def did_mount(self):
        page = self._get_page()
        if page:
            page.on_resized = self._on_page_resize
            page.update()

        if hasattr(self.app, "load_data"):
            self.app.load_data()

        self._refresh_fournisseurs_table()
        self._refresh_documents_table()

    def _on_page_resize(self, e=None):
        self._refresh_fournisseurs_table()
        self._refresh_documents_table()

    def _is_mobile(self):
        page = self._get_page()
        if not page or not page.width:
            return True
        return page.width < 768

    def _open_dialog(self, dialog, e=None):
        page = self._get_page(e)
        if not page:
            return
        try:
            if hasattr(page, "open"):
                page.open(dialog)
            else:
                if dialog not in page.overlay:
                    page.overlay.append(dialog)
                dialog.open = True
                page.update()
        except Exception:
            pass

    def _close_dialog(self, dialog, e=None):
        page = self._get_page(e)
        if not page:
            return
        try:
            if hasattr(page, "close"):
                page.close(dialog)
            else:
                dialog.open = False
                if dialog in page.overlay:
                    page.overlay.remove(dialog)
                page.update()
        except Exception:
            pass

    def _show_snack(self, message, is_error=False, e=None):
        page = self._get_page(e)
        if not page:
            return
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor="#B91C1C" if is_error else "#15803D",
        )
        try:
            if hasattr(page, "open"):
                page.open(snack)
            else:
                page.overlay.append(snack)
                snack.open = True
                page.update()
        except Exception:
            pass

    def _ouvrir_creation_doc(self, type_doc, doc_to_edit=None):
        try:
            if hasattr(self.app, "navigate_to"):
                self.app.navigate_to(
                    "create_document",
                    doc_type=type_doc,
                    doc_to_edit=doc_to_edit,
                )
            elif hasattr(self.app, "content_area") and self.app.content_area:
                from views.create_document import CreateDocumentView
                self.app.content_area.content = CreateDocumentView(
                    app=self.app, doc_type=type_doc, doc_to_edit=doc_to_edit
                )
                self.app.page.update()
        except Exception as ex:
            self._show_snack(f"Erreur d'ouverture : {ex}", is_error=True)

    def _build_interface(self):
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=safe_icon("ARROW_BACK_ROUNDED", "arrow_back"),
                    icon_color="white",
                    tooltip="Retour",
                    on_click=lambda e: self.app.navigate_to("Dashboard") if hasattr(self.app, "navigate_to") else None,
                ),
                ft.Text(
                    "🚚 Espace Fournisseurs & Logistique",
                    size=22,
                    weight="bold",
                    color="white",
                ),
            ]
        )

        button_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))

        # ONGLET 1 : FOURNISSEURS
        fourn_toolbar = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "➕ Ajouter un Fournisseur",
                    bgcolor=self.accent_color,
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self.ouvrir_dialogue_fournisseur(e=e),
                ),
            ]
        )

        self.fourn_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nom / Entreprise", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Téléphone", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Email", weight="bold", color="white")),
                ft.DataColumn(ft.Text("SIRET", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Adresse", weight="bold", color="white")),
            ],
            rows=[],
            heading_row_color="#242426",
            show_checkbox_column=False,
        )

        fourn_actions = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "✏️ Modifier la fiche",
                    bgcolor="#F59E0B",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self.modifier_fournisseur_selectionne(e=e),
                ),
                ft.ElevatedButton(
                    "🗑️ Supprimer le fournisseur",
                    bgcolor="#DC2626",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self.supprimer_fournisseur_selectionne(e=e),
                ),
            ],
            spacing=10,
        )

        self.tab_fournisseurs_view = ft.Column(
            controls=[fourn_toolbar, self.display_container_fourn, fourn_actions],
            spacing=15,
            expand=True,
        )

        # ONGLET 2 : DOCUMENTS
        doc_toolbar = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "➕ Nouveau Bon de Commande",
                    bgcolor=self.accent_color,
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self._ouvrir_creation_doc("bon_commande"),
                ),
                ft.ElevatedButton(
                    "➕ Nouveau Bon de Livraison",
                    bgcolor=self.accent_color,
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self._ouvrir_creation_doc("bon_livraison"),
                ),
            ],
            spacing=10,
            wrap=True,
        )

        self.search_entry = ft.TextField(
            hint_text="🔍 Rechercher par numéro, fournisseur, statut...",
            bgcolor="#1A1A1C",
            height=42,
            text_size=13,
            content_padding=10,
            border_color="#2A2A32",
            focused_border_color=self.accent_color,
            text_style=ft.TextStyle(color="white"),
            on_change=self._refresh_documents_table,
        )

        self.doc_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Type", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Numéro", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Fournisseur", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Total TTC", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Statut", weight="bold", color="white")),
            ],
            rows=[],
            heading_row_color="#242426",
            show_checkbox_column=False,
        )

        doc_actions = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "👁️ Voir PDF",
                    bgcolor="#2B719E",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=self.ouvrir_pdf_selectionne,
                ),
                ft.ElevatedButton(
                    "💾 Exporter PDF",
                    bgcolor="#8B5CF6",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=self.exporter_pdf_organise,
                ),
                ft.ElevatedButton(
                    "✏️ Modifier",
                    bgcolor="#F59E0B",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=self.modifier_doc_selectionne,
                ),
                ft.ElevatedButton(
                    "🔄 Convertir BC en BL",
                    bgcolor="#0EA5E9",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=self.convertir_bc_en_bl,
                ),
                ft.ElevatedButton(
                    "🗑️ Supprimer",
                    bgcolor="#DC2626",
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=self.supprimer_doc_selectionne,
                ),
            ],
            spacing=8,
            wrap=True,
        )

        self.tab_documents_view = ft.Column(
            controls=[
                doc_toolbar,
                self.search_entry,
                self.display_container_docs,
                doc_actions,
            ],
            spacing=15,
            expand=True,
        )

        self.lbl_tab_fourn = ft.Text("👥 Fiches Fournisseurs", weight="bold", color="white")
        self.lbl_tab_docs = ft.Text("📄 Documents (BC & BL)", weight="bold", color="#AEAEB2")

        self.btn_tab_fourn = ft.Container(
            content=self.lbl_tab_fourn,
            padding=ft.Padding(left=16, top=10, right=16, bottom=10),
            bgcolor=self.accent_color,
            border_radius=8,
            on_click=lambda e: self._switch_tab(0),
        )

        self.btn_tab_docs = ft.Container(
            content=self.lbl_tab_docs,
            padding=ft.Padding(left=16, top=10, right=16, bottom=10),
            bgcolor="#1A1A1C",
            border_radius=8,
            on_click=lambda e: self._switch_tab(1),
        )

        tabs_header = ft.Row(
            controls=[self.btn_tab_fourn, self.btn_tab_docs],
            spacing=8,
        )

        self.tab_body = ft.Container(
            content=self.tab_fournisseurs_view,
            expand=True,
        )

        self.main_layout.controls = [header, tabs_header, self.tab_body]

    def _switch_tab(self, index):
        self.current_tab_index = index
        if index == 0:
            self.btn_tab_fourn.bgcolor = self.accent_color
            self.lbl_tab_fourn.color = "white"
            self.btn_tab_docs.bgcolor = "#1A1A1C"
            self.lbl_tab_docs.color = "#AEAEB2"
            self.tab_body.content = self.tab_fournisseurs_view
        else:
            self.btn_tab_fourn.bgcolor = "#1A1A1C"
            self.lbl_tab_fourn.color = "#AEAEB2"
            self.btn_tab_docs.bgcolor = self.accent_color
            self.lbl_tab_docs.color = "white"
            self.tab_body.content = self.tab_documents_view
        self.safe_update()

    # --- FOURNISSEURS ---

    def _refresh_fournisseurs_table(self):
        if hasattr(self.app, "load_data"):
            self.app.load_data()

        fourn_list = getattr(self.app, "fournisseurs", [])
        self.fourn_table.rows.clear()

        if self._is_mobile():
            cards = []
            for f in fourn_list:
                is_sel = (self.selected_fournisseur == f)
                def make_sel(fd):
                    return lambda e: self._select_fournisseur_row(fd)
                cards.append(
                    ft.Container(
                        bgcolor="#2A3A4E" if is_sel else "#1E1E22",
                        border=safe_border(1.5 if is_sel else 1, self.accent_color if is_sel else "#2A2A32"),
                        border_radius=10,
                        padding=12,
                        on_click=make_sel(f),
                        content=ft.Column([
                            ft.Text(f.get("nom", "Inconnu"), weight="bold", color="white"),
                            ft.Text(f"Tél : {f.get('telephone', '-')}", color="white", size=12),
                            ft.Text(f"Email : {f.get('email', '-')}", color="white", size=12),
                            ft.Text(f"SIRET : {f.get('siret', '-')}", color="#AEAEB2", size=11),
                        ], spacing=4)
                    )
                )
            self.display_container_fourn.content = ft.Container(
                content=ft.ListView(controls=cards, spacing=8, expand=True),
                bgcolor="#141416",
                border_radius=10,
                border=safe_border(1, "#2A2A32"),
                padding=8,
                expand=True,
            )
        else:
            for f in fourn_list:
                def make_select_callback(fourn_dict):
                    return lambda e: self._select_fournisseur_row(fourn_dict)

                row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f.get("nom", "Inconnu"), weight="bold", color="white")),
                        ft.DataCell(ft.Text(f.get("telephone", "-"), color="white")),
                        ft.DataCell(ft.Text(f.get("email", "-"), color="white")),
                        ft.DataCell(ft.Text(f.get("siret", "-"), color="white")),
                        ft.DataCell(ft.Text(f.get("adresse", "-"), color="white")),
                    ],
                    selected=(self.selected_fournisseur == f),
                    on_select_changed=make_select_callback(f),
                )
                self.fourn_table.rows.append(row)

            self.display_container_fourn.content = ft.Container(
                content=ft.Column([ft.Row([self.fourn_table], scroll=ft.ScrollMode.AUTO)], scroll=ft.ScrollMode.AUTO, expand=True),
                bgcolor="#141416",
                border_radius=10,
                border=safe_border(1, "#2A2A32"),
                padding=8,
                expand=True,
            )
        self.safe_update()

    def _select_fournisseur_row(self, fourn_dict):
        if self.selected_fournisseur == fourn_dict:
            self.selected_fournisseur = None
        else:
            self.selected_fournisseur = fourn_dict
        self._refresh_fournisseurs_table()

    def ouvrir_dialogue_fournisseur(self, fourn_to_edit=None, e=None):
        nom_tf = ft.TextField(label="Nom / Entreprise *", value=fourn_to_edit.get("nom", "") if fourn_to_edit else "")
        tel_tf = ft.TextField(label="Téléphone", value=fourn_to_edit.get("telephone", "") if fourn_to_edit else "")
        email_tf = ft.TextField(label="Email", value=fourn_to_edit.get("email", "") if fourn_to_edit else "")
        siret_tf = ft.TextField(label="SIRET", value=fourn_to_edit.get("siret", "") if fourn_to_edit else "")
        adresse_tf = ft.TextField(label="Adresse", multiline=True, min_lines=2, value=fourn_to_edit.get("adresse", "") if fourn_to_edit else "")

        def valider_enregistrement(evt):
            if not nom_tf.value or not nom_tf.value.strip():
                self._show_snack("Le nom du fournisseur est obligatoire.", is_error=True, e=evt)
                return

            data = {
                "nom": nom_tf.value.strip(),
                "telephone": tel_tf.value.strip() if tel_tf.value else "",
                "email": email_tf.value.strip() if email_tf.value else "",
                "siret": siret_tf.value.strip() if siret_tf.value else "",
                "adresse": adresse_tf.value.strip() if adresse_tf.value else "",
            }

            if fourn_to_edit:
                fourn_to_edit.update(data)
                self._show_snack("Fiche fournisseur mise à jour.", e=evt)
            else:
                if not hasattr(self.app, "fournisseurs") or self.app.fournisseurs is None:
                    self.app.fournisseurs = []
                self.app.fournisseurs.append(data)
                self._show_snack("Fournisseur enregistré.", e=evt)

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self.selected_fournisseur = None
            self._refresh_fournisseurs_table()

        dialog = ft.AlertDialog(
            title=ft.Text("🏢 Fiche Fournisseur" if fourn_to_edit else "➕ Nouveau Fournisseur"),
            content=ft.Column([nom_tf, tel_tf, email_tf, siret_tf, adresse_tf], tight=True, spacing=10),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Enregistrer", bgcolor=self.accent_color, color="white", on_click=valider_enregistrement),
            ],
        )
        self._open_dialog(dialog, e=e)

    def modifier_fournisseur_selectionne(self, e=None):
        if not self.selected_fournisseur:
            self._show_snack("Veuillez sélectionner un fournisseur dans le tableau.", is_error=True, e=e)
            return
        self.ouvrir_dialogue_fournisseur(self.selected_fournisseur, e=e)

    def supprimer_fournisseur_selectionne(self, e=None):
        if not self.selected_fournisseur:
            self._show_snack("Veuillez sélectionner un fournisseur à supprimer.", is_error=True, e=e)
            return

        target_nom = self.selected_fournisseur.get("nom")
        target_siret = self.selected_fournisseur.get("siret")

        def confirmer(evt):
            if hasattr(self.app, "fournisseurs") and self.app.fournisseurs:
                self.app.fournisseurs = [
                    f for f in self.app.fournisseurs
                    if not (f.get("nom") == target_nom and f.get("siret") == target_siret)
                ]

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self.selected_fournisseur = None
            self._close_dialog(dialog, e=evt)
            self._refresh_fournisseurs_table()
            self._show_snack("Fournisseur supprimé avec succès.", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("🚨 Confirmation de suppression"),
            content=ft.Text(f"Supprimer définitivement {target_nom or 'ce fournisseur'} ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.TextButton("Supprimer", on_click=confirmer, style=ft.ButtonStyle(color="#DC2626")),
            ],
        )
        self._open_dialog(dialog, e=e)

    # --- DOCUMENTS ---

    def _refresh_documents_table(self, e=None):
        if hasattr(self.app, "load_data"):
            self.app.load_data()

        self.documents.clear()
        query = (
            self.search_entry.value.strip().lower()
            if self.search_entry and self.search_entry.value
            else ""
        )

        filtered_docs = []
        bc_list = getattr(self.app, "bons_commande", [])
        bl_list = getattr(self.app, "bons_livraison", [])

        for bc in bc_list:
            if self._match_query(bc, "bon_commande", query):
                num = str(bc.get("numero", ""))
                self.documents[("bon_commande", num)] = bc
                filtered_docs.append(("bon_commande", num, bc))

        for bl in bl_list:
            if self._match_query(bl, "bon_livraison", query):
                num = str(bl.get("numero", ""))
                self.documents[("bon_livraison", num)] = bl
                filtered_docs.append(("bon_livraison", num, bl))

        if self._is_mobile():
            self._render_documents_mobile(filtered_docs)
        else:
            self._render_documents_desktop(filtered_docs)

        self.safe_update()

    def _render_documents_desktop(self, filtered_docs):
        self.doc_table.rows.clear()
        for type_doc, num, doc in filtered_docs:
            key = (type_doc, num)
            is_selected = (self.selected_doc_key == key)

            def make_select_handler(k):
                return lambda e: self._select_doc_row(k)

            nom_f = extract_fournisseur_name(doc.get("fournisseur", {}))
            montant = calculate_doc_ttc(doc)
            statut = doc.get("statut", "-")
            label_type = "Bon de commande" if type_doc == "bon_commande" else "Bon de livraison"
            badge_color = "#8B5CF6" if type_doc == "bon_commande" else "#0EA5E9"

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(label_type, weight="bold", color=badge_color)),
                    ft.DataCell(ft.Text(str(num), color="white", weight="bold")),
                    ft.DataCell(ft.Text(nom_f, color="white")),
                    ft.DataCell(ft.Text(f"{montant:.2f} €", color="white")),
                    ft.DataCell(
                        ft.Text(
                            str(statut),
                            color=(
                                "#34D399"
                                if any(s in str(statut).lower() for s in ["reçu", "livré", "validé", "payé"])
                                else "#FBBF24"
                            ),
                        )
                    ),
                ],
                selected=is_selected,
                on_select_changed=make_select_handler(key),
            )
            self.doc_table.rows.append(row)

        self.display_container_docs.content = ft.Container(
            content=ft.Column(
                [ft.Row([self.doc_table], scroll=ft.ScrollMode.AUTO)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            bgcolor="#141416",
            border_radius=10,
            border=safe_border(1, "#2A2A32"),
            padding=8,
            expand=True,
        )

    def _render_documents_mobile(self, filtered_docs):
        cards = []
        for type_doc, num, doc in filtered_docs:
            key = (type_doc, num)
            is_selected = (self.selected_doc_key == key)

            nom_f = extract_fournisseur_name(doc.get("fournisseur", {}))
            montant = calculate_doc_ttc(doc)
            statut = doc.get("statut", "-")
            label_type = "BC" if type_doc == "bon_commande" else "BL"

            def make_select_handler(k):
                return lambda e: self._select_doc_row(k)

            cards.append(
                ft.Container(
                    bgcolor="#2A3A4E" if is_selected else "#1E1E22",
                    border=safe_border(
                        1.5 if is_selected else 1,
                        self.accent_color if is_selected else "#2A2A32",
                    ),
                    border_radius=10,
                    padding=12,
                    on_click=make_select_handler(key),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"[{label_type}] {num}", weight="bold", color="white"),
                                    ft.Text(f"{montant:.2f} €", color="#10B981", weight="bold"),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(f"Fournisseur : {nom_f}", color="white", size=12),
                            ft.Text(f"Statut : {statut}", size=11, color="#AEAEB2"),
                        ],
                        spacing=4,
                    ),
                )
            )

        if not cards:
            cards.append(ft.Container(content=ft.Text("Aucun document trouvé.", color="#AEAEB2", italic=True), padding=10))

        self.display_container_docs.content = ft.Container(
            content=ft.ListView(controls=cards, spacing=8, expand=True),
            bgcolor="#141416",
            border_radius=10,
            border=safe_border(1, "#2A2A32"),
            padding=8,
            expand=True,
        )

    def _select_doc_row(self, key):
        if self.selected_doc_key == key:
            self.selected_doc_key = None
        else:
            self.selected_doc_key = key
        self._refresh_documents_table()

    def _match_query(self, doc, type_doc, query):
        if not query:
            return True
        num = str(doc.get("numero", "")).lower()
        nom = extract_fournisseur_name(doc.get("fournisseur", {})).lower()
        statut = str(doc.get("statut", "")).lower()
        readable_type = "bon de commande" if type_doc == "bon_commande" else "bon de livraison"
        return query in num or query in nom or query in statut or query in readable_type

    def _selected_document(self):
        if not self.selected_doc_key or self.selected_doc_key not in self.documents:
            self._show_snack("Veuillez sélectionner un document dans la liste.", is_error=True)
            return None, None
        type_doc, num = self.selected_doc_key
        return type_doc, self.documents.get(self.selected_doc_key)

    def ouvrir_pdf_selectionne(self, e=None):
        type_doc, doc = self._selected_document()
        if doc:
            self.exporter_pdf_direct(type_doc, doc, ouvrir_apres=True)

    def exporter_pdf_organise(self, e=None):
        type_doc, doc = self._selected_document()
        if doc:
            self.exporter_pdf_direct(type_doc, doc, ouvrir_apres=False)

    def exporter_pdf_direct(self, type_doc, doc, ouvrir_apres=False):
        date_str = doc.get("date_creation", datetime.now().strftime("%d/%m/%Y"))
        try:
            parts = date_str.split("/")
            j, m, a = parts[0], parts[1], parts[2]
        except Exception:
            now = datetime.now()
            j, m, a = f"{now.day:02d}", f"{now.month:02d}", f"{now.year}"

        base_dir = os.path.join(os.path.dirname(getattr(self.app, "database", ".")), "Documents_PDF")
        folder_path = os.path.join(base_dir, type_doc.capitalize(), a, m)

        try:
            os.makedirs(folder_path, exist_ok=True)
            file_name = f"{doc.get('numero', 'SANS_NUMERO')}.pdf"
            full_path = os.path.join(folder_path, file_name)

            self._generate_pdf_file(type_doc, doc, full_path)

            doc["pdf_path"] = full_path
            doc["pdf_to_load"] = full_path
            doc["type_doc_interne"] = type_doc

            if ouvrir_apres:
                self.app.current_doc = doc
                if hasattr(self.app, "navigate_to"):
                    self.app.navigate_to("PDFViewer", doc=doc)
            else:
                self._show_snack(f"PDF enregistré sous : {full_path}")
        except Exception as ex:
            self._show_snack(f"Erreur PDF : {ex}", is_error=True)

    def _generate_pdf_file(self, type_doc, doc, file_path):
        entreprise_data = getattr(self.app, "entreprise", {}) if self.app else {}
        generer_pdf_zero_dep(doc, file_path, entreprise_data)

    def modifier_doc_selectionne(self, e=None):
        type_doc, doc = self._selected_document()
        if doc:
            self._ouvrir_creation_doc(type_doc, doc_to_edit=doc)

    def supprimer_doc_selectionne(self, e=None):
        type_doc, doc = self._selected_document()
        if not doc:
            return

        num_target = str(doc.get("numero", ""))

        def confirmation_action(evt):
            if type_doc == "bon_commande" and hasattr(self.app, "bons_commande"):
                self.app.bons_commande = [
                    d for d in self.app.bons_commande if str(d.get("numero")) != num_target
                ]
            elif hasattr(self.app, "bons_livraison"):
                self.app.bons_livraison = [
                    d for d in self.app.bons_livraison if str(d.get("numero")) != num_target
                ]

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self.selected_doc_key = None
            self._close_dialog(dialog, e=evt)
            self._refresh_documents_table()
            self._show_snack(f"Document n°{num_target} supprimé.", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("🚨 Confirmation de suppression"),
            content=ft.Text(f"Supprimer définitivement le document n°{num_target} ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.TextButton("Confirmer", on_click=confirmation_action, style=ft.ButtonStyle(color="#DC2626")),
            ],
        )
        self._open_dialog(dialog, e=e)

    def convertir_bc_en_bl(self, e=None):
        type_doc, doc = self._selected_document()
        if not doc:
            return

        if type_doc != "bon_commande":
            self._show_snack("Veuillez sélectionner un Bon de Commande.", is_error=True)
            return

        bl_list = getattr(self.app, "bons_livraison", [])
        num_bl = f"BL-{datetime.now().year}-{len(bl_list) + 1:03d}"

        tot_ht = calculate_doc_ht(doc)
        tot_ttc = calculate_doc_ttc(doc)
        tot_tva = max(0.0, tot_ttc - tot_ht)

        articles = list(doc.get("articles", doc.get("lignes", [])))
        nouveau_bl = {
            "type": "bon_livraison",
            "doc_type": "bon_livraison",
            "type_doc": "bon_livraison",
            "numero": num_bl,
            "fournisseur": doc.get("fournisseur"),
            "client": doc.get("fournisseur"),
            "articles": articles,
            "lignes": articles,
            "total_ht": tot_ht,
            "montant_ht": tot_ht,
            "montant_tva": tot_tva,
            "tva": tot_tva,
            "total_ttc": tot_ttc,
            "montant_ttc": tot_ttc,
            "date_creation": datetime.now().strftime("%d/%m/%Y"),
            "statut": "Reçu",
            "bc_origine": doc.get("numero"),
        }

        if not hasattr(self.app, "bons_livraison") or not isinstance(self.app.bons_livraison, list):
            self.app.bons_livraison = []

        self.app.bons_livraison.append(nouveau_bl)
        doc["statut"] = "Livré"

        if hasattr(self.app, "save_data"):
            self.app.save_data()

        self.selected_doc_key = ("bon_livraison", num_bl)
        self._refresh_documents_table()
        self._show_snack(f"Bon de Livraison {num_bl} généré avec succès !")