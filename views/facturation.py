import csv
from datetime import datetime
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
    """Convertit n'importe quel type (str avec virgule/symbole, int, float) en float sécurisé."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        clean_str = str(val).replace("€", "").replace(" ", "").replace(",", ".").strip()
        return float(clean_str)
    except (ValueError, TypeError):
        return default


def extract_client_name(client_data):
    """Extrait le nom du client depuis un dictionnaire ou une chaîne."""
    if isinstance(client_data, dict):
        return (
            client_data.get("nom")
            or client_data.get("contact_nom")
            or client_data.get("entreprise")
            or "Inconnu"
        )
    if isinstance(client_data, str) and client_data.strip():
        return client_data.strip()
    return "Inconnu"


def calculate_doc_ttc(doc):
    """Calcule le montant total TTC d'un document de façon robuste, même si les clés sont tronquées."""
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
            prix = parse_float(item.get("prix_ht", item.get("pu_ht", item.get("prix", 0))))
            tva = parse_float(item.get("taux_tva", item.get("tva", 20.0)))
            total_ttc += qte * prix * (1 + tva / 100)

    if total_ttc > 0:
        return total_ttc

    return parse_float(doc.get("total_ht", doc.get("montant_ht", 0.0)))


def calculate_doc_ht(doc):
    """Calcule le montant total HT d'un document."""
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
            prix = parse_float(item.get("prix_ht", item.get("pu_ht", item.get("prix", 0))))
            total_ht += qte * prix

    return total_ht


class FacturationView(ft.Container):
    """Vue Flet sécurisée et réactive pour la gestion des factures et devis."""

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
        self.selected_key = None

        self.has_file_picker = False
        self.file_picker = None

        self.display_container = ft.Container(expand=True)
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

    def _get_default_tva(self):
        entreprise = getattr(self.app, "entreprise", {}) or {}
        return parse_float(entreprise.get("taux_tva", entreprise.get("tva", 20.0)), 20.0)

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
            try:
                if not self._is_mobile():
                    if not self.file_picker:
                        self.file_picker = ft.FilePicker(on_result=self._on_csv_picked)
                    if self.file_picker not in page.overlay:
                        page.overlay.append(self.file_picker)
                    self.has_file_picker = True
                else:
                    self.has_file_picker = False
            except Exception:
                self.has_file_picker = False

            page.on_resized = self._on_page_resize
            page.update()

        if hasattr(self.app, "load_data"):
            self.app.load_data()

        self._refresh_table()

    def _on_page_resize(self, e=None):
        self._refresh_table()

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

    def _build_interface(self):
        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=safe_icon("ARROW_BACK_ROUNDED", "arrow_back"),
                    icon_color="white",
                    tooltip="Retour",
                    on_click=lambda e: self.app.navigate_to("Dashboard"),
                ),
                ft.Text("📂 Gestion des Documents", size=22, weight="bold", color="white"),
            ]
        )

        button_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))

        top_buttons = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "➕ Nouveau Devis",
                    bgcolor=self.accent_color,
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self._creer_document("devis"),
                ),
                ft.ElevatedButton(
                    "➕ Nouvelle Facture",
                    bgcolor=self.accent_color,
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=lambda e: self._creer_document("facture"),
                ),
            ],
            spacing=10,
            wrap=True,
        )

        self.search_entry = ft.TextField(
            hint_text="🔍 Rechercher par numéro, client, statut...",
            bgcolor="#1A1A1C",
            height=42,
            text_size=13,
            content_padding=10,
            border_color="#2A2A32",
            focused_border_color=self.accent_color,
            text_style=ft.TextStyle(color="white"),
            on_change=self._refresh_table,
        )

        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Type", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Numéro", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Client", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Total TTC", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Statut", weight="bold", color="white")),
                ft.DataColumn(ft.Text("URSSAF", weight="bold", color="white")),
            ],
            rows=[],
            heading_row_color="#242426",
            show_checkbox_column=False,
        )

        actions = ft.ResponsiveRow(
            controls=[
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "✏️ Modifier",
                            bgcolor="#F59E0B",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.modifier_selectionne,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 2},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "💶 Marquer Payée",
                            bgcolor="#10B981",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.marquer_payee,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 2},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "✅ Déclarer URSSAF",
                            bgcolor="#16A34A",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.declarer_urssaf,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 2},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "🔄 Convertir",
                            bgcolor="#0EA5E9",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.convertir_devis_en_facture,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 2},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "📊 Exporter CSV",
                            bgcolor="#4F46E5",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.exporter_csv,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 2},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "🗑️ Supprimer",
                            bgcolor="#DC2626",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.supprimer_selectionne,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 2},
                ),
            ],
            spacing=8,
        )

        self.main_layout.controls = [
            header,
            top_buttons,
            self.search_entry,
            self.display_container,
            actions,
        ]

    def _refresh_table(self, e=None):
        if hasattr(self.app, "load_data"):
            self.app.load_data()

        self.documents.clear()
        query = (
            self.search_entry.value.strip().lower()
            if self.search_entry and self.search_entry.value
            else ""
        )

        filtered_docs = []

        for devis in getattr(self.app, "devis", []):
            if self._match_query(devis, "devis", query):
                num = str(devis.get("numero", ""))
                self.documents[("devis", num)] = devis
                filtered_docs.append(("devis", num, devis))

        for facture in getattr(self.app, "factures", []):
            if self._match_query(facture, "facture", query):
                num = str(facture.get("numero", ""))
                self.documents[("facture", num)] = facture
                filtered_docs.append(("facture", num, facture))

        if self._is_mobile():
            self._render_mobile(filtered_docs)
        else:
            self._render_desktop(filtered_docs)

        self.safe_update()

    def _match_query(self, doc, type_doc, query):
        if not query:
            return True
        num = str(doc.get("numero", "")).lower()
        client_nom = extract_client_name(doc.get("client", {})).lower()
        statut = str(doc.get("statut", "")).lower()
        return query in num or query in client_nom or query in statut or query in type_doc

    def _render_desktop(self, filtered_docs):
        self.table.rows.clear()
        for type_doc, num, doc in filtered_docs:
            key = (type_doc, num)
            is_selected = self.selected_key == key

            def make_select_handler(k):
                return lambda e: self._select_document(k)

            def make_double_click_handler(d):
                return lambda e: self.ouvrir_pdf(d)

            nom = extract_client_name(doc.get("client", {}))
            montant = calculate_doc_ttc(doc)

            statut = doc.get("statut", "-")
            if statut == "Payée" and doc.get("date_paiement"):
                statut = f"Payée ({doc.get('date_paiement')})"

            urssaf_txt = "Oui" if doc.get("urssaf_declare") else "Non"

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(type_doc.capitalize(), color="white"), on_tap=make_select_handler(key)),
                    ft.DataCell(
                        ft.Text(str(num), color="white", weight="bold"),
                        on_tap=make_select_handler(key),
                        on_double_tap=make_double_click_handler(doc),
                    ),
                    ft.DataCell(ft.Text(nom, color="white"), on_tap=make_select_handler(key)),
                    ft.DataCell(ft.Text(f"{montant:.2f} €", color="white"), on_tap=make_select_handler(key)),
                    ft.DataCell(
                        ft.Text(
                            str(statut),
                            color=(
                                "#34D399"
                                if "payée" in str(statut).lower() or "déclarée" in str(statut).lower()
                                else "#FBBF24"
                            ),
                        ),
                        on_tap=make_select_handler(key),
                    ),
                    ft.DataCell(ft.Text(urssaf_txt, color="white"), on_tap=make_select_handler(key)),
                ],
                selected=is_selected,
            )

            self.table.rows.append(row)

        self.display_container.content = ft.Container(
            content=ft.Column(
                [ft.Row([self.table], scroll=ft.ScrollMode.AUTO)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            bgcolor="#141416",
            border_radius=10,
            border=safe_border(1, "#2A2A32"),
            padding=8,
            expand=True,
        )

    def _render_mobile(self, filtered_docs):
        cards = []
        for type_doc, num, doc in filtered_docs:
            key = (type_doc, num)
            is_selected = self.selected_key == key

            nom = extract_client_name(doc.get("client", {}))
            montant = calculate_doc_ttc(doc)
            statut = doc.get("statut", "-")

            def make_select_handler(k):
                return lambda e: self._select_document(k)

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
                                    ft.Text(
                                        f"[{type_doc.upper()}] {num}",
                                        weight="bold",
                                        color="white",
                                    ),
                                    ft.Text(
                                        f"{montant:.2f} €",
                                        color="#10B981",
                                        weight="bold",
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(f"Client : {nom}", color="white", size=12),
                            ft.Text(f"Statut : {statut}", size=11, color="#AEAEB2"),
                        ],
                        spacing=4,
                    ),
                )
            )

        if not cards:
            cards.append(
                ft.Container(
                    content=ft.Text("Aucun document trouvé.", color="#AEAEB2", italic=True),
                    padding=10,
                )
            )

        self.display_container.content = ft.Container(
            content=ft.ListView(controls=cards, spacing=8, expand=True),
            bgcolor="#141416",
            border_radius=10,
            border=safe_border(1, "#2A2A32"),
            padding=8,
            expand=True,
        )

    def _select_document(self, key):
        if self.selected_key == key:
            self.selected_key = None
        else:
            self.selected_key = key
        self._refresh_table()

    def _selected_document(self):
        if not self.selected_key or self.selected_key not in self.documents:
            self._show_snack("Veuillez sélectionner un document dans le tableau.", is_error=True)
            return None, None
        type_doc, num = self.selected_key
        return type_doc, self.documents.get(self.selected_key)

    def _creer_document(self, doc_type="devis"):
        if hasattr(self.app, "navigate_to"):
            self.app.navigate_to("create_document", doc_type=doc_type)

    def ouvrir_pdf(self, doc=None):
        if not doc:
            _, doc = self._selected_document()
        if doc and hasattr(self.app, "navigate_to"):
            self.app.navigate_to("PDFViewer", doc=doc)

    def modifier_selectionne(self, e=None):
        type_doc, doc = self._selected_document()
        if doc and hasattr(self.app, "navigate_to"):
            self.app.navigate_to("create_document", doc_type=type_doc, doc_to_edit=doc)

    def marquer_payee(self, e=None):
        type_doc, doc = self._selected_document()
        if not doc:
            return

        if type_doc != "facture":
            return self._show_snack("Seules les factures peuvent être marquées comme payées.", is_error=True, e=e)

        if doc.get("statut") == "Payée":
            return self._show_snack(f"Cette facture a déjà été réglée le {doc.get('date_paiement', 'inconnue')}.", e=e)

        date_aujourdhui = datetime.now().strftime("%d/%m/%Y")

        def valider(evt):
            doc["statut"] = "Payée"
            doc["date_paiement"] = date_aujourdhui

            self._deduire_stock_pour_facture(doc)

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack(f"Facture {doc['numero']} enregistrée comme 'Payée' !", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("💶 Encaissement"),
            content=ft.Text(f"Confirmer l'encaissement de la facture n°{doc['numero']} le {date_aujourdhui} ?\n(Mise à jour des stocks et des articles)"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Confirmer", bgcolor="#10B981", color="white", on_click=valider),
            ],
        )
        self._open_dialog(dialog, e=e)

    def declarer_urssaf(self, e=None):
        type_doc, doc = self._selected_document()
        if not doc:
            return

        if type_doc != "facture":
            return self._show_snack("Seules les factures peuvent être déclarées à l'URSSAF.", is_error=True, e=e)

        if doc.get("urssaf_declare"):
            return self._show_snack("Cette facture a déjà été déclarée à l'URSSAF.", e=e)

        def valider(evt):
            doc["urssaf_declare"] = True
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack("Facture marquée comme déclarée à l'URSSAF. ✅", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("✅ Déclaration URSSAF"),
            content=ft.Text(f"Marquer la facture n°{doc['numero']} comme déclarée à l'URSSAF ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Confirmer", bgcolor="#16A34A", color="white", on_click=valider),
            ],
        )
        self._open_dialog(dialog, e=e)

    def convertir_devis_en_facture(self, e=None):
        type_doc, doc = self._selected_document()
        if not doc:
            return

        if type_doc != "devis":
            return self._show_snack("Vous devez sélectionner un devis pour effectuer cette action.", is_error=True, e=e)

        if doc.get("statut") != "Signé":
            return self._show_snack("Le devis doit être au statut 'Signé' pour être converti en facture.", is_error=True, e=e)

        tot_ht = calculate_doc_ht(doc)
        tot_ttc = calculate_doc_ttc(doc)
        tot_tva = max(0.0, tot_ttc - tot_ht)

        nouvelle_facture = {
            "type": "facture",
            "type_doc": "facture",
            "type_document": "Facture",
            "titre_document": "Facture",
            "label": "Facture",
            "numero": self._next_invoice_number(),
            "client": doc.get("client"),
            "articles": list(doc.get("articles", doc.get("lignes", []))),
            "lignes": list(doc.get("lignes", doc.get("articles", []))),
            "total_ht": tot_ht,
            "montant_ht": tot_ht,
            "montant_tva": tot_tva,
            "total_ttc": tot_ttc,
            "montant_ttc": tot_ttc,
            "date_creation": datetime.now().strftime("%d/%m/%Y"),
            "statut": "À payer",
            "urssaf_declare": False,
            "stock_deduit": False,
        }

        if not hasattr(self.app, "factures") or not isinstance(self.app.factures, list):
            self.app.factures = []

        self.app.factures.append(nouvelle_facture)
        doc["statut"] = "Accepté / Converti"

        if hasattr(self.app, "save_data"):
            self.app.save_data()

        self._refresh_table()
        self._show_snack(f"Facture {nouvelle_facture['numero']} créée avec succès à partir du devis.", e=e)

    def supprimer_selectionne(self, e=None):
        type_doc, doc = self._selected_document()
        if not doc:
            return

        def valider(evt):
            if type_doc == "devis" and hasattr(self.app, "devis"):
                self.app.devis.remove(doc)
            elif type_doc == "facture" and hasattr(self.app, "factures"):
                self.app.factures.remove(doc)

            self.selected_key = None
            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack("Le document a été supprimé avec succès.", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("🗑️ Suppression"),
            content=ft.Text(f"Êtes-vous sûr de vouloir supprimer le {type_doc} n°{doc.get('numero')} ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Supprimer", bgcolor="#DC2626", color="white", on_click=valider),
            ],
        )
        self._open_dialog(dialog, e=e)

    def _deduire_stock_pour_facture(self, doc):
        """Déduit le stock des articles d'une facture payée."""
        if doc.get("stock_deduit"):
            return

        items = doc.get("lignes") or doc.get("articles") or []
        if not items:
            return

        if not hasattr(self.app, "articles") or not isinstance(self.app.articles, list):
            self.app.articles = []

        articles_db = self.app.articles
        tva_defaut = self._get_default_tva()

        for item in items:
            ref_cible = str(item.get("ref", "")).strip().lower()
            cb_cible = str(item.get("code_barre", "")).strip().lower()
            nom_cible = str(
                item.get("designation", item.get("nom", item.get("description", "Article Sans Nom")))
            ).strip()

            qte_vendue = int(parse_float(item.get("quantite", item.get("qte", 1)), 1))

            trouve = False
            for art in articles_db:
                ref_art = str(art.get("ref", "")).strip().lower()
                cb_art = str(art.get("code_barre", "")).strip().lower()
                nom_art = str(art.get("designation", art.get("nom", ""))).strip().lower()

                if (
                    (ref_cible and ref_cible == ref_art)
                    or (cb_cible and cb_cible == cb_art)
                    or (nom_cible.lower() == nom_art)
                ):
                    stock_actuel = int(parse_float(art.get("stock", 0)))
                    art["stock"] = max(0, stock_actuel - qte_vendue)
                    trouve = True
                    break

            if not trouve:
                prix_ht = parse_float(item.get("prix_ht", item.get("pu_ht", item.get("pu", item.get("prix", 0.0)))))
                taux_tva_art = parse_float(item.get("taux_tva", item.get("tva", tva_defaut)))
                prix_ttc_art = prix_ht * (1 + taux_tva_art / 100)

                nouveau_produit = {
                    "ref": item.get("ref", f"REF-{len(articles_db)+1:03d}"),
                    "designation": nom_cible,
                    "nom": nom_cible,
                    "code_barre": item.get("code_barre", ""),
                    "prix_ht": prix_ht,
                    "prix": prix_ht,
                    "prix_unitaire": prix_ht,
                    "taux_tva": taux_tva_art,
                    "tva": taux_tva_art,
                    "prix_ttc": prix_ttc_art,
                    "stock": 0,
                }
                articles_db.append(nouveau_produit)

        if hasattr(self.app, "save_data"):
            self.app.save_data()

        doc["stock_deduit"] = True

    def _next_invoice_number(self):
        entreprise = getattr(self.app, "entreprise", {}) if hasattr(self.app, "entreprise") else {}
        prefix = entreprise.get("prefix_facture", f"F{datetime.now().year}-")
        maxi = 0
        for f in getattr(self.app, "factures", []):
            m = re.search(r"(\d+)$", str(f.get("numero", "")))
            if m:
                maxi = max(maxi, int(m.group(1)))
        return f"{prefix}{maxi + 1:03d}"

    def _write_csv_data(self, filepath):
        with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Type Document",
                "Numéro",
                "Client",
                "Total HT (€)",
                "Total TTC (€)",
                "Statut",
                "Déclaré URSSAF",
                "Date Création",
                "Date Paiement",
            ])

            for devis in getattr(self.app, "devis", []):
                nom_c = extract_client_name(devis.get("client", {}))
                writer.writerow([
                    "Devis",
                    devis.get("numero", ""),
                    nom_c,
                    f"{calculate_doc_ht(devis):.2f}",
                    f"{calculate_doc_ttc(devis):.2f}",
                    devis.get("statut", "-"),
                    "Non applicable",
                    devis.get("date_creation", ""),
                    "-",
                ])

            for facture in getattr(self.app, "factures", []):
                nom_c = extract_client_name(facture.get("client", {}))
                writer.writerow([
                    "Facture",
                    facture.get("numero", ""),
                    nom_c,
                    f"{calculate_doc_ht(facture):.2f}",
                    f"{calculate_doc_ttc(facture):.2f}",
                    facture.get("statut", "-"),
                    "Oui" if facture.get("urssaf_declare") else "Non",
                    facture.get("date_creation", ""),
                    facture.get("date_paiement", "-"),
                ])

    def exporter_csv(self, e=None):
        page = self._get_page(e)

        if self._is_mobile() or not self.has_file_picker:
            temp_dir = Path(tempfile.gettempdir())
            filename = temp_dir / "historique_comptable.csv"
            try:
                self._write_csv_data(str(filename))
                self._show_snack(f"Export CSV sauvegardé : {filename.name}", e=e)
            except Exception as err:
                self._show_snack(f"Erreur d'exportation : {err}", is_error=True, e=e)
            return

        if self.file_picker and page:
            try:
                self.file_picker.save_file(
                    dialog_title="Exporter l'historique comptable",
                    file_name="historique_comptable.csv",
                    allowed_extensions=["csv"],
                )
                return
            except Exception:
                pass

        temp_dir = Path(tempfile.gettempdir())
        filename = temp_dir / "historique_comptable.csv"
        try:
            self._write_csv_data(str(filename))
            self._show_snack(f"Export CSV sauvegardé : {filename.name}", e=e)
        except Exception as err:
            self._show_snack(f"Erreur d'exportation : {err}", is_error=True, e=e)

    def _on_csv_picked(self, e: ft.FilePickerResultEvent):
        if not e.path:
            return
        filepath = e.path
        try:
            self._write_csv_data(filepath)
            self._show_snack(f"Export CSV réussi : {filepath}", e=e)
        except Exception as err:
            self._show_snack(f"Erreur d'exportation : {err}", is_error=True, e=e)