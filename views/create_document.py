import re
from datetime import datetime
import flet as ft


def safe_border(width=1, color="#424242"):
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


def safe_icon(name, fallback="arrow_back"):
    for container in (getattr(ft, "Icons", None), getattr(ft, "icons", None)):
        if container and hasattr(container, name):
            val = getattr(container, name)
            if val:
                return val
    return fallback


def parse_float(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(",", ".")
        s = re.sub(r"[^\d.-]", "", s)
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def extract_price(item_dict):
    if not isinstance(item_dict, dict):
        return 0.0
    keys = [
        "prix_ht", "prix_unitaire_ht", "prix_unitaire", "pu_ht", "pu",
        "prix_vente_ht", "prix_vente", "prix", "unit_price", "pv_ht",
        "price", "prix_ttc"
    ]
    for key in keys:
        if key in item_dict and item_dict[key] is not None:
            val = parse_float(item_dict[key], -1.0)
            if val >= 0:
                return val
    return 0.0


def extract_qte(item_dict):
    if not isinstance(item_dict, dict):
        return 1.0
    for key in ["quantite", "qte", "qty", "count"]:
        if key in item_dict and item_dict[key] is not None:
            val = parse_float(item_dict[key], -1.0)
            if val > 0:
                return val
    return 1.0


def extract_tva(item_dict, default=20.0):
    if not isinstance(item_dict, dict):
        return default
    for key in ["taux_tva", "tva", "vat"]:
        if key in item_dict and item_dict[key] is not None:
            val = parse_float(item_dict[key], -1.0)
            if val >= 0:
                return val
    return default


DOC_CONFIGS = {
    "devis": {
        "label": "Devis",
        "entity_type": "client",
        "prefix_key": "prefix_devis",
        "default_prefix": "D-",
        "target_attr": "devis",
        "default_status": "En attente",
    },
    "facture": {
        "label": "Facture",
        "entity_type": "client",
        "prefix_key": "prefix_facture",
        "default_prefix": "F-",
        "target_attr": "factures",
        "default_status": "À payer",
    },
    "bon_commande": {
        "label": "Bon de commande",
        "entity_type": "fournisseur",
        "prefix_key": "prefix_bc",
        "default_prefix": "BC-",
        "target_attr": "bons_commande",
        "default_status": "En cours",
    },
    "bon_livraison": {
        "label": "Bon de livraison",
        "entity_type": "fournisseur",
        "prefix_key": "prefix_bl",
        "default_prefix": "BL-",
        "target_attr": "bons_livraison",
        "default_status": "Reçu",
    },
}

# Alias
DOC_CONFIGS["commande"] = DOC_CONFIGS["bon_commande"]
DOC_CONFIGS["bc"] = DOC_CONFIGS["bon_commande"]
DOC_CONFIGS["BC"] = DOC_CONFIGS["bon_commande"]

DOC_CONFIGS["livraison"] = DOC_CONFIGS["bon_livraison"]
DOC_CONFIGS["bl"] = DOC_CONFIGS["bon_livraison"]
DOC_CONFIGS["BL"] = DOC_CONFIGS["bon_livraison"]


class CreateDocumentView(ft.Container):
    def __init__(self, app, doc_type="devis", doc_to_edit=None, source_doc=None, is_conversion=False):
        super().__init__()
        self.app = app

        # Normalisation du type cible
        raw_type = str(doc_type).lower().strip()
        if raw_type in ["bl", "livraison", "bon_livraison", "bon de livraison"]:
            self.doc_type = "bon_livraison"
        elif raw_type in ["bc", "commande", "bon_commande", "bon de commande"]:
            self.doc_type = "bon_commande"
        elif raw_type in ["facture", "f"]:
            self.doc_type = "facture"
        elif raw_type in ["devis", "d"]:
            self.doc_type = "devis"
        else:
            self.doc_type = raw_type if raw_type in DOC_CONFIGS else "devis"

        self.doc_config = DOC_CONFIGS[self.doc_type]

        self.source_doc = source_doc
        self.doc_to_edit = doc_to_edit

        # Détection de conversion identique à Devis -> Facture
        if self.doc_to_edit and isinstance(self.doc_to_edit, dict):
            src_type = str(
                self.doc_to_edit.get("type")
                or self.doc_to_edit.get("type_doc")
                or self.doc_to_edit.get("type_document")
                or ""
            ).lower()
            src_num = str(self.doc_to_edit.get("numero", "")).upper()

            is_bc_to_bl = (self.doc_type == "bon_livraison") and (
                "bc" in src_type or "commande" in src_type or src_num.startswith("BC")
            )
            is_devis_to_facture = (self.doc_type == "facture") and (
                "devis" in src_type or src_num.startswith("D")
            )

            if is_bc_to_bl or is_devis_to_facture or is_conversion or (src_type and src_type != self.doc_type):
                self.source_doc = self.doc_to_edit
                self.doc_to_edit = None

        self.expand = True
        self.padding = 10

        self.accent_color = (
            getattr(self.app, "entreprise", {}).get("accent_color", "#2B719E")
            if hasattr(self.app, "entreprise")
            else "#2B719E"
        )

        self.lignes = []
        self.main_layout = ft.Column(spacing=15, expand=True, scroll=ft.ScrollMode.AUTO)
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

    def _is_assujetti_tva(self):
        entreprise = getattr(self.app, "entreprise", {}) or {}
        val = entreprise.get("assujetti_tva", True)
        if isinstance(val, str):
            return val.strip().lower() not in ["false", "0", "non", "no", "off"]
        return bool(val)

    def _get_default_tva(self):
        if not self._is_assujetti_tva():
            return 0.0
        entreprise = getattr(self.app, "entreprise", {}) or {}
        return parse_float(
            entreprise.get(
                "tva_par_defaut",
                entreprise.get("taux_tva_defaut", entreprise.get("taux_tva", entreprise.get("tva", 20.0))),
            ),
            20.0,
        )

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
        if hasattr(self.app, "load_data"):
            self.app.load_data()

        self._charger_entites_dropdown()
        self._charger_articles_dropdown()

        if self.doc_to_edit:
            self._charger_document_existant(self.doc_to_edit, is_conversion=False)
        elif self.source_doc:
            self._charger_document_existant(self.source_doc, is_conversion=True)

        self.safe_update()

    def _show_snack(self, message, is_error=False, e=None):
        page = self._get_page(e)
        if not page:
            return
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor="#B91C1C" if is_error else "#15803D",
        )
        try:
            page.open(snack)
        except Exception:
            page.snack_bar = snack
            snack.open = True
            page.update()

    def _build_interface(self):
        label = self.doc_config["label"]
        if self.doc_to_edit:
            title_txt = f"✏️ Modifier {label}"
        elif self.source_doc:
            src_num = self.source_doc.get("numero", "Doc")
            title_txt = f"🔄 Créer {label} (depuis {src_num})"
        else:
            title_txt = f"➕ Nouveau {label}"

        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=safe_icon("ARROW_BACK_ROUNDED", "arrow_back"),
                    icon_color="white",
                    tooltip="Retour",
                    on_click=lambda e: self.app.navigate_to(
                        "Fournisseurs" if self.doc_config["entity_type"] == "fournisseur" else "Facturation"
                    ),
                ),
                ft.Text(title_txt, size=22, weight="bold", color="white"),
            ]
        )

        entity_label = (
            "Sélectionner un Fournisseur"
            if self.doc_config["entity_type"] == "fournisseur"
            else "Sélectionner un Client"
        )

        self.num_field = ft.TextField(
            label="Numéro",
            value=self._generer_numero(),
            bgcolor="#1A1A1C",
            col={"xs": 12, "sm": 4},
        )
        self.date_field = ft.TextField(
            label="Date",
            value=datetime.now().strftime("%d/%m/%Y"),
            bgcolor="#1A1A1C",
            col={"xs": 12, "sm": 4},
        )
        self.entity_dd = ft.Dropdown(
            label=entity_label,
            bgcolor="#1A1A1C",
            col={"xs": 12, "sm": 4},
            options=[],
        )

        doc_info = ft.ResponsiveRow(
            controls=[self.num_field, self.date_field, self.entity_dd],
            spacing=10,
        )

        self.article_dd = ft.Dropdown(
            label="📦 Choisir dans le catalogue",
            bgcolor="#1A1A1C",
            col={"xs": 12, "sm": 6},
            options=[],
        )
        self.article_dd.on_change = self._on_catalogue_select

        self.ref_field = ft.TextField(label="Référence", bgcolor="#1A1A1C", col={"xs": 6, "sm": 3})
        self.nom_field = ft.TextField(label="Désignation", bgcolor="#1A1A1C", col={"xs": 12, "sm": 3})
        self.qte_field = ft.TextField(
            label="Qté",
            value="1",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor="#1A1A1C",
            col={"xs": 4, "sm": 2},
        )
        self.prix_field = ft.TextField(
            label="Prix HT (€)",
            value="0.0",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor="#1A1A1C",
            col={"xs": 4, "sm": 2},
        )
        self.tva_field = ft.TextField(
            label="TVA (%)",
            value=str(self._get_default_tva()),
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor="#1A1A1C",
            col={"xs": 4, "sm": 2},
        )

        add_btn = ft.ElevatedButton(
            "➕ Ajouter la ligne",
            bgcolor=self.accent_color,
            color="white",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._ajouter_ligne,
        )

        article_box = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Ajout d'articles", weight="bold", color="white", size=14),
                    self.article_dd,
                    ft.ResponsiveRow(
                        [self.ref_field, self.nom_field, self.qte_field, self.prix_field, self.tva_field],
                        spacing=10,
                    ),
                    ft.Row([add_btn], alignment=ft.MainAxisAlignment.END),
                ],
                spacing=10,
            ),
            bgcolor="#1E1E22",
            padding=12,
            border_radius=10,
            border=safe_border(1, "#2A2A32"),
        )

        self.table_lignes = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Réf", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Désignation", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Qté", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Prix HT", weight="bold", color="white")),
                ft.DataColumn(ft.Text("TVA", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Total TTC", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Action", weight="bold", color="white")),
            ],
            rows=[],
            heading_row_color="#242426",
        )

        self.table_container = ft.Container(
            content=ft.Column(
                [ft.Row([self.table_lignes], scroll=ft.ScrollMode.AUTO)],
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor="#141416",
            border_radius=10,
            border=safe_border(1, "#2A2A32"),
            padding=8,
            height=220,
        )

        self.total_ht_txt = ft.Text("Total HT : 0,00 €", size=14, color="white", weight="bold")
        self.total_tva_txt = ft.Text("TVA : 0,00 €", size=14, color="white")
        self.total_ttc_txt = ft.Text("Total TTC : 0,00 €", size=16, color="#10B981", weight="bold")

        totals_box = ft.Container(
            content=ft.Column(
                [self.total_ht_txt, self.total_tva_txt, self.total_ttc_txt],
                horizontal_alignment=ft.CrossAxisAlignment.END,
            ),
            alignment=getattr(ft.alignment, "CENTER_RIGHT", getattr(ft.alignment, "center_right", None)),
        )

        save_btn = ft.ElevatedButton(
            "💾 Enregistrer le document",
            bgcolor="#10B981",
            color="white",
            height=45,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=self._enregistrer_document,
        )

        self.main_layout.controls = [
            header,
            doc_info,
            article_box,
            ft.Text("Lignes du document", weight="bold", color="white", size=14),
            self.table_container,
            totals_box,
            ft.Row([save_btn], alignment=ft.MainAxisAlignment.END),
            ft.Container(height=20),
        ]

    def _get_entity_source(self):
        is_fourn = self.doc_config["entity_type"] == "fournisseur"
        raw_source = getattr(self.app, "fournisseurs" if is_fourn else "clients", [])
        if isinstance(raw_source, dict):
            return list(raw_source.values())
        if isinstance(raw_source, list):
            return raw_source
        return []

    def _charger_entites_dropdown(self):
        source = self._get_entity_source()
        is_fourn = self.doc_config["entity_type"] == "fournisseur"

        options = []
        for idx, item in enumerate(source):
            if not isinstance(item, dict):
                continue
            nom = (
                item.get("nom")
                or item.get("entreprise")
                or item.get("raison_sociale")
                or item.get("societe")
                or item.get("nom_client")
                or ""
            ).strip()
            prenom = item.get("prenom", "").strip()
            label = f"{nom} {prenom}".strip() if prenom else nom

            if not label:
                label = f"{'Fournisseur' if is_fourn else 'Client'} #{idx + 1}"

            options.append(ft.dropdown.Option(key=str(idx), text=label))

        self.entity_dd.options = options
        self.safe_update()

    def _get_articles_source(self):
        raw_art = getattr(self.app, "articles", [])
        if isinstance(raw_art, dict):
            return list(raw_art.values())
        if isinstance(raw_art, list):
            return raw_art
        return []

    def _charger_articles_dropdown(self):
        articles = self._get_articles_source()
        options = []
        for idx, art in enumerate(articles):
            if not isinstance(art, dict):
                continue
            ref = art.get("ref") or art.get("reference") or art.get("code") or ""
            nom = art.get("designation") or art.get("nom") or art.get("libelle") or art.get("title") or "Sans nom"
            prix = extract_price(art)
            label_ref = f"[{ref}] " if ref else ""
            options.append(ft.dropdown.Option(key=str(idx), text=f"{label_ref}{nom} — {prix:.2f} € HT"))

        self.article_dd.options = options
        self.safe_update()

    def _on_catalogue_select(self, e=None):
        val = None
        if e and hasattr(e, "control") and e.control:
            val = e.control.value
        if val is None:
            val = self.article_dd.value

        if val is None or str(val).strip() == "":
            return

        try:
            idx = int(val)
            articles = self._get_articles_source()

            if 0 <= idx < len(articles):
                art = articles[idx]
                if not isinstance(art, dict):
                    return

                ref = art.get("ref") or art.get("reference") or art.get("code") or ""
                nom = art.get("designation") or art.get("nom") or art.get("libelle") or art.get("title") or ""

                self.ref_field.value = str(ref)
                self.nom_field.value = str(nom)
                self.prix_field.value = f"{extract_price(art):.2f}"

                if not self._is_assujetti_tva():
                    self.tva_field.value = "0.0"
                else:
                    self.tva_field.value = str(extract_tva(art, self._get_default_tva()))

                self.ref_field.update()
                self.nom_field.update()
                self.prix_field.update()
                self.tva_field.update()
                self.safe_update()
        except Exception as ex:
            print(f"Erreur catalogue : {ex}")

    def _ajouter_ligne(self, e=None):
        nom = self.nom_field.value.strip() if self.nom_field.value else ""
        if not nom:
            return self._show_snack("Veuillez saisir une désignation.", is_error=True, e=e)

        qte = parse_float(self.qte_field.value, 1.0)
        prix_ht = parse_float(self.prix_field.value, 0.0)

        if not self._is_assujetti_tva():
            taux_tva = 0.0
        else:
            taux_tva = parse_float(self.tva_field.value, self._get_default_tva())

        total_ht_ligne = qte * prix_ht
        montant_tva_ligne = total_ht_ligne * (taux_tva / 100)
        total_ttc_ligne = total_ht_ligne + montant_tva_ligne

        ligne = {
            "ref": self.ref_field.value.strip() if self.ref_field.value else "",
            "designation": nom,
            "nom": nom,
            "quantite": qte,
            "qte": qte,
            "prix_ht": prix_ht,
            "pu_ht": prix_ht,
            "prix_unitaire": prix_ht,
            "prix_unitaire_ht": prix_ht,
            "taux_tva": taux_tva,
            "tva": taux_tva,
            "total_ht": total_ht_ligne,
            "montant_ht": total_ht_ligne,
            "montant_tva": montant_tva_ligne,
            "total_ttc": total_ttc_ligne,
            "prix_ttc": total_ttc_ligne,
        }

        self.lignes.append(ligne)

        self.ref_field.value = ""
        self.nom_field.value = ""
        self.qte_field.value = "1"
        self.prix_field.value = "0.0"
        self.article_dd.value = None

        self._refresh_lignes_table()

    def _supprimer_ligne(self, idx):
        if 0 <= idx < len(self.lignes):
            self.lignes.pop(idx)
            self._refresh_lignes_table()

    def _refresh_lignes_table(self):
        self.table_lignes.rows.clear()
        tot_ht = 0.0
        tot_tva = 0.0
        tot_ttc = 0.0

        est_assujetti = self._is_assujetti_tva()

        for idx, l in enumerate(self.lignes):
            if not isinstance(l, dict):
                continue

            qte = extract_qte(l)
            prix_ht = extract_price(l)
            taux_tva = 0.0 if not est_assujetti else extract_tva(l, self._get_default_tva())

            l_ht = qte * prix_ht
            l_tva = l_ht * (taux_tva / 100)
            l_ttc = l_ht + l_tva

            l["prix_ht"] = prix_ht
            l["pu_ht"] = prix_ht
            l["prix_unitaire"] = prix_ht
            l["qte"] = qte
            l["quantite"] = qte
            l["taux_tva"] = taux_tva
            l["tva"] = taux_tva
            l["total_ht"] = l_ht
            l["montant_ht"] = l_ht
            l["montant_tva"] = l_tva
            l["total_ttc"] = l_ttc

            tot_ht += l_ht
            tot_tva += l_tva
            tot_ttc += l_ttc

            def make_delete_handler(i):
                return lambda e: self._supprimer_ligne(i)

            self.table_lignes.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(l.get("ref") or "-", color="white")),
                        ft.DataCell(ft.Text(l.get("designation") or l.get("nom", ""), color="white")),
                        ft.DataCell(ft.Text(str(int(qte)) if qte.is_integer() else f"{qte:.2f}", color="white")),
                        ft.DataCell(ft.Text(f"{prix_ht:.2f} €", color="white")),
                        ft.DataCell(ft.Text(f"{taux_tva:.1f} %", color="white")),
                        ft.DataCell(ft.Text(f"{l_ttc:.2f} €", color="white")),
                        ft.DataCell(
                            ft.IconButton(
                                icon=safe_icon("DELETE_OUTLINED", "delete"),
                                icon_color="#DC2626",
                                on_click=make_delete_handler(idx),
                            )
                        ),
                    ]
                )
            )

        self.total_ht_txt.value = f"Total HT : {tot_ht:.2f} €"
        self.total_tva_txt.value = f"TVA : {tot_tva:.2f} €"
        self.total_ttc_txt.value = f"Total TTC : {tot_ttc:.2f} €"

        self.safe_update()

    def _generer_numero(self):
        if self.doc_to_edit:
            return self.doc_to_edit.get("numero", "")

        entreprise = getattr(self.app, "entreprise", {}) or {}
        prefix = entreprise.get(
            self.doc_config["prefix_key"], f"{self.doc_config['default_prefix']}{datetime.now().year}-"
        )

        target_attr = self.doc_config["target_attr"]
        target_list = getattr(self.app, target_attr, [])
        if isinstance(target_list, dict):
            target_list = list(target_list.values())

        maxi = 0
        for doc in target_list:
            if isinstance(doc, dict):
                m = re.search(r"(\d+)$", str(doc.get("numero", "")))
                if m:
                    maxi = max(maxi, int(m.group(1)))
        return f"{prefix}{maxi + 1:03d}"

    def _charger_document_existant(self, doc, is_conversion=False):
        if not doc or not isinstance(doc, dict):
            return

        if is_conversion:
            # Génération explicite du nouveau numéro (ex: BL-xxx)
            self.num_field.value = self._generer_numero()
            self.date_field.value = datetime.now().strftime("%d/%m/%Y")
        else:
            self.num_field.value = doc.get("numero", self._generer_numero())
            self.date_field.value = doc.get("date_creation", datetime.now().strftime("%d/%m/%Y"))

        entity_key = self.doc_config["entity_type"]
        entity_data = doc.get(entity_key) or doc.get("fournisseur") or doc.get("client") or {}

        source = self._get_entity_source()
        matched_key = None

        if isinstance(entity_data, dict):
            target_nom = (entity_data.get("nom") or entity_data.get("entreprise") or "").strip().lower()
        else:
            target_nom = str(entity_data).strip().lower()

        if target_nom:
            for idx, item in enumerate(source):
                if isinstance(item, dict):
                    item_nom = (
                        item.get("nom")
                        or item.get("entreprise")
                        or item.get("raison_sociale")
                        or ""
                    ).strip().lower()
                    if item_nom and (item_nom == target_nom or target_nom in item_nom or item_nom in target_nom):
                        matched_key = str(idx)
                        break

        if matched_key:
            self.entity_dd.value = matched_key

        raw_lignes = doc.get("lignes") or doc.get("articles") or []
        self.lignes = [dict(l) for l in raw_lignes if isinstance(l, dict)]
        self._refresh_lignes_table()

    def _enregistrer_document(self, e=None):
        if not self.lignes:
            return self._show_snack("Veuillez ajouter au moins une ligne au document.", is_error=True, e=e)

        is_fourn = self.doc_config["entity_type"] == "fournisseur"
        entity_key = "fournisseur" if is_fourn else "client"
        source = self._get_entity_source()

        raw_entity_obj = {}
        selected_key = self.entity_dd.value

        if selected_key is not None and str(selected_key).isdigit():
            idx = int(selected_key)
            if 0 <= idx < len(source):
                raw_entity_obj = source[idx]

        if not raw_entity_obj:
            default_name = "Fournisseur Général" if is_fourn else "Client Passager"
            raw_entity_obj = {"nom": default_name}

        if isinstance(raw_entity_obj, dict):
            clean_entity_obj = dict(raw_entity_obj)
        else:
            clean_entity_obj = {"nom": str(raw_entity_obj)}

        est_assujetti = self._is_assujetti_tva()

        tot_ht = 0.0
        tot_tva = 0.0
        tot_ttc = 0.0

        for l in self.lignes:
            qte = extract_qte(l)
            prix_ht = extract_price(l)
            taux_tva = 0.0 if not est_assujetti else extract_tva(l, self._get_default_tva())

            l_ht = qte * prix_ht
            l_tva = l_ht * (taux_tva / 100)
            l_ttc = l_ht + l_tva

            l["taux_tva"] = taux_tva
            l["tva"] = taux_tva
            l["montant_tva"] = l_tva
            l["total_ttc"] = l_ttc

            tot_ht += l_ht
            tot_tva += l_tva
            tot_ttc += l_ttc

        if not est_assujetti:
            tot_tva = 0.0
            tot_ttc = tot_ht
            mention_tva = "TVA non applicable, art. 293 B du CGI"
        else:
            mention_tva = "TVA non applicable, art. 293 B du CGI" if tot_tva == 0.0 else ""

        entreprise_complete = dict(getattr(self.app, "entreprise", {}) or {})
        doc_label = self.doc_config["label"]

        doc_data = {
            "type": self.doc_type,
            "type_doc": self.doc_type,
            "type_document": doc_label,
            "titre": doc_label,
            "titre_document": doc_label,
            "label": doc_label,
            "numero": self.num_field.value.strip() if self.num_field.value else self._generer_numero(),
            "date_creation": self.date_field.value.strip() if self.date_field.value else datetime.now().strftime("%d/%m/%Y"),
            "entreprise": entreprise_complete,
            entity_key: clean_entity_obj,
            "lignes": self.lignes,
            "articles": self.lignes,
            "total_ht": tot_ht,
            "montant_ht": tot_ht,
            "montant_tva": tot_tva,
            "tva": tot_tva,
            "total_ttc": tot_ttc,
            "montant_ttc": tot_ttc,
            "mention_tva": mention_tva,
            "statut": (
                self.doc_to_edit.get("statut", self.doc_config["default_status"])
                if self.doc_to_edit
                else self.doc_config["default_status"]
            ),
            "urssaf_declare": self.doc_to_edit.get("urssaf_declare", False) if self.doc_to_edit else False,
            "stock_deduit": self.doc_to_edit.get("stock_deduit", False) if self.doc_to_edit else False,
        }

        # Mise à jour du document source
        if self.source_doc:
            doc_data["bc_source_numero"] = self.source_doc.get("numero", "")
            doc_data["doc_source_numero"] = self.source_doc.get("numero", "")

            status_source = "Livré" if self.doc_type == "bon_livraison" else "Facturé"
            self.source_doc["statut"] = status_source

            source_attr = "bons_commande" if self.doc_type == "bon_livraison" else "devis"
            source_list = getattr(self.app, source_attr, [])
            if isinstance(source_list, list):
                for doc_orig in source_list:
                    if isinstance(doc_orig, dict) and doc_orig.get("numero") == self.source_doc.get("numero"):
                        doc_orig["statut"] = status_source
                        break

        if self.doc_type in ["facture", "bon_livraison", "livraison"]:
            try:
                from views.articles import ArticlesView
                gestion_articles = ArticlesView(self.app)
                if hasattr(gestion_articles, "deduire_stock_facture"):
                    gestion_articles.deduire_stock_facture(self.lignes)
            except Exception as ex:
                print(f"Avertissement : Échec de la déduction de stock ({ex})")

        target_attr = self.doc_config["target_attr"]
        if not hasattr(self.app, target_attr) or getattr(self.app, target_attr) is None:
            setattr(self.app, target_attr, [])

        target_list = getattr(self.app, target_attr)

        if self.doc_to_edit and self.doc_to_edit in target_list:
            idx = target_list.index(self.doc_to_edit)
            target_list[idx] = doc_data
        else:
            target_list.append(doc_data)

        if hasattr(self.app, "save_data"):
            self.app.save_data()

        self._show_snack(f"{doc_label} enregistré avec succès !", e=e)
        self.app.navigate_to("Fournisseurs" if is_fourn else "Facturation")