import flet as ft
from datetime import datetime

def safe_float(val):
    """Convertit proprement n'importe quelle chaîne financière en float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace("€", "").replace(" ", "").replace("\xa0", "").replace(",", ".").strip()
        return float(s) if s else 0.0
    except ValueError:
        return 0.0

def safe_border(width=1, color="#2A2A2E"):
    """Bordure universelle sécurisée."""
    try:
        side = ft.BorderSide(width, color)
        return ft.Border(top=side, right=side, bottom=side, left=side)
    except Exception:
        return None

def safe_padding(h=0, v=0):
    """Padding universel tolérant toutes les versions de Flet."""
    try:
        return ft.padding.symmetric(horizontal=h, vertical=v)
    except Exception:
        try:
            return ft.padding.only(left=h, top=v, right=h, bottom=v)
        except Exception:
            return v if h == v else h

def safe_weight(bold=True):
    try:
        return ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL
    except Exception:
        return "bold" if bold else "normal"

def safe_text_align(align="left"):
    try:
        if align == "center":
            return ft.TextAlign.CENTER
        elif align == "right":
            return ft.TextAlign.RIGHT
        return ft.TextAlign.LEFT
    except Exception:
        return align

def safe_main_align(align="start"):
    try:
        if align == "spaceBetween":
            return ft.MainAxisAlignment.SPACE_BETWEEN
        elif align == "center":
            return ft.MainAxisAlignment.CENTER
        return ft.MainAxisAlignment.START
    except Exception:
        return align

def safe_cross_align(align="start"):
    try:
        if align == "center":
            return ft.CrossAxisAlignment.CENTER
        return ft.CrossAxisAlignment.START
    except Exception:
        return align

def safe_scroll():
    try:
        return ft.ScrollMode.AUTO
    except Exception:
        return "auto"

def safe_button(text, on_click, bgcolor="#388E3C", color="white", height=40):
    """Bouton universel incassable indépendant des évolutions d'ElevatedButton."""
    return ft.Container(
        content=ft.Text(
            text, 
            color=color, 
            weight=safe_weight(True),
            text_align=safe_text_align("center")
        ),
        bgcolor=bgcolor,
        height=height,
        border_radius=8,
        alignment=getattr(ft, "alignment", None) and getattr(ft.alignment, "center", None),
        on_click=on_click,
        ink=True,
        padding=safe_padding(10, 5)
    )


class ComptabiliteView(ft.Container):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 10
        self.selected_tab_index = 0

        self.accent_color = (
            getattr(self.app, "entreprise", {}).get("accent_color", "#2B719E")
            if hasattr(self.app, "entreprise") and isinstance(self.app.entreprise, dict)
            else "#2B719E"
        )

        if not hasattr(self.app, "charges") or not isinstance(self.app.charges, list):
            self.app.charges = []

        self.setup_ui()

    def safe_update(self):
        """Met à jour le composant uniquement s'il est déjà rattaché à l'écran."""
        if self.page is not None:
            try:
                self.update()
            except Exception:
                pass

    def _is_mobile(self):
        """Détecte si l'écran est en mode mobile (< 768px)."""
        try:
            p = self.page or getattr(self.app, "page", None)
            return p.width < 768 if (p and getattr(p, "width", None)) else False
        except Exception:
            return False

    def did_mount(self):
        """Déclenché par Flet quand le composant est monté."""
        if hasattr(self.app, "load_data"):
            try:
                self.app.load_data()
            except Exception:
                pass

    def _build_custom_tabs(self):
        """Génère une barre d'onglets personnalisée universelle."""
        labels = [
            "📊 Synthèse & KPIs",
            "💸 Registre des Charges",
            "🏛️ Assistant CA3"
        ]
        
        tab_buttons = []
        for idx, label in enumerate(labels):
            is_active = (idx == self.selected_tab_index)
            btn = ft.Container(
                content=ft.Text(
                    label,
                    size=12 if self._is_mobile() else 13,
                    weight=safe_weight(is_active),
                    color="white" if is_active else "#A0A0A5"
                ),
                bgcolor=self.accent_color if is_active else "#242426",
                padding=safe_padding(12, 8),
                border_radius=8,
                border=safe_border(1, self.accent_color if is_active else "#3A3A3E"),
                on_click=lambda e, i=idx: self._change_tab(i),
                ink=True
            )
            tab_buttons.append(btn)

        return ft.Row(
            controls=tab_buttons,
            scroll=safe_scroll(),
            spacing=8
        )

    def _change_tab(self, index):
        """Change d'onglet et rafraîchit la vue."""
        self.selected_tab_index = index
        self.tabs_container.content = self._build_custom_tabs()
        self._render_current_tab()
        self.safe_update()

    def setup_ui(self):
        """Crée la structure adaptative complète."""
        is_mob = self._is_mobile()

        title_text = ft.Text(
            "📈 Comptabilité & TVA",
            size=18 if is_mob else 20,
            weight=safe_weight(True),
            color="white"
        )

        self.combo_periode = ft.Dropdown(
            value="Trimestre en cours",
            options=[
                ft.dropdown.Option("Mois en cours"),
                ft.dropdown.Option("Trimestre en cours"),
                ft.dropdown.Option("Année complète")
            ],
            width=180 if is_mob else 200,
            height=40 if is_mob else 45,
            text_size=12 if is_mob else 14
        )
        self.combo_periode.on_change = self._mettre_a_jour_tout

        header = ft.Row(
            controls=[title_text, self.combo_periode],
            alignment=safe_main_align("spaceBetween"),
            wrap=True,
            spacing=10
        )

        self.main_container = ft.Container(
            expand=True,
            bgcolor="#1E1E20",
            border_radius=12,
            border=safe_border(1, "#2A2A2E"),
            padding=10 if is_mob else 15
        )

        self.tabs_container = ft.Container(
            content=self._build_custom_tabs()
        )

        self.content = ft.Column(
            controls=[
                header,
                self.tabs_container,
                self.main_container
            ],
            expand=True,
            spacing=10
        )

        self._afficher_synthese()

    def _render_current_tab(self):
        """Reconstruit le contenu du conteneur selon l'onglet actif."""
        if self.selected_tab_index == 0:
            self._afficher_synthese()
        elif self.selected_tab_index == 1:
            self._afficher_registre_charges()
        elif self.selected_tab_index == 2:
            self._afficher_assistant_ca3()

    def _mettre_a_jour_tout(self, e):
        self._render_current_tab()
        self.safe_update()

    def _calculer_metriques_financieres(self):
        factures = getattr(self.app, "factures", [])

        factures_valides = [
            f for f in factures
            if str(f.get("statut", "")).lower() in ["payée", "validée", "encaissée", "payee", "encaissee", "payé", "valide"]
        ]

        ca_ht, tva_20, tva_10, tva_5 = 0.0, 0.0, 0.0, 0.0

        for f in factures_valides:
            total_ttc = safe_float(f.get("total_ttc", f.get("montant_ttc", f.get("ttc", 0))))
            total_ht = safe_float(f.get("total_ht", f.get("montant_ht", f.get("ht", 0))))
            tva_totale = total_ttc - total_ht
            ca_ht += total_ht

            taux = safe_float(f.get("taux_tva", 20))
            if taux == 20:
                tva_20 += tva_totale
            elif taux == 10:
                tva_10 += tva_totale
            else:
                tva_5 += tva_totale

        tva_collectee_totale = tva_20 + tva_10 + tva_5
        tva_deductible_totale, tva_autoliquidee, total_charges_ht = 0.0, 0.0, 0.0

        for c in getattr(self.app, "charges", []):
            ht = safe_float(c.get("ht", 0))
            taux_tva = safe_float(c.get("taux", 20))
            coef_recup = safe_float(c.get("coef_recup", 100)) / 100.0
            est_autoliquide = c.get("autoliquide", False)
            tva_theorique = ht * (taux_tva / 100.0)
            total_charges_ht += ht

            if est_autoliquide:
                tva_autoliquidee += tva_theorique
                tva_deductible_totale += tva_theorique * coef_recup
            else:
                tva_deductible_totale += tva_theorique * coef_recup

        return {
            "ca_ht": ca_ht,
            "tva_collectee": tva_collectee_totale + tva_autoliquidee,
            "tva_20": tva_20,
            "tva_10": tva_10,
            "tva_5": tva_5,
            "tva_autoliquidee": tva_autoliquidee,
            "total_charges_ht": total_charges_ht,
            "tva_deductible": tva_deductible_totale,
            "solde_tva": (tva_collectee_totale + tva_autoliquidee) - tva_deductible_totale
        }

    def _afficher_synthese(self):
        data = self._calculer_metriques_financieres()
        is_mob = self._is_mobile()

        cards = []
        for title, val, color in [
            ("Chiffre d'Affaires global (HT)", f"{data['ca_ht']:.2f} €", "white"),
            ("Total TVA Collectée (Brute)", f"{data['tva_collectee']:.2f} €", self.accent_color),
            ("TVA Récupérable (Déductible)", f"{data['tva_deductible']:.2f} €", "#66BB6A")
        ]:
            card = ft.Container(
                expand=not is_mob,
                bgcolor="#242426",
                border_radius=10,
                border=safe_border(1, "#3A3A3E"),
                padding=10 if is_mob else 12,
                content=ft.Column(
                    controls=[
                        ft.Text(title, size=11, color="#A0A0A5", text_align=safe_text_align("center")),
                        ft.Text(val, size=18 if is_mob else 20, weight=safe_weight(True), color=color, text_align=safe_text_align("center"))
                    ],
                    horizontal_alignment=safe_cross_align("center"),
                    alignment=safe_main_align("center")
                )
            )
            cards.append(card)

        cards_container = (
            ft.Column(controls=cards, spacing=8)
            if is_mob
            else ft.Row(controls=cards, spacing=12, alignment=safe_main_align("spaceBetween"))
        )

        solde_positif = data['solde_tva'] >= 0
        bg_solde = "#1C2826" if solde_positif else "#2D1A1A"
        color_solde = "#66BB6A" if solde_positif else "#EF5350"
        txt_solde = f"TVA À REVERSER : {data['solde_tva']:.2f} €" if solde_positif else f"CRÉDIT DE TVA : {abs(data['solde_tva']):.2f} €"

        solde_frame = ft.Container(
            bgcolor=bg_solde,
            border_radius=10,
            padding=10 if is_mob else 12,
            alignment=getattr(ft, "alignment", None) and getattr(ft.alignment, "center", None),
            content=ft.Text(
                f"État du solde estimé : {txt_solde}",
                size=12 if is_mob else 15,
                weight=safe_weight(True),
                color=color_solde,
                text_align=safe_text_align("center")
            )
        )

        detail_controls = [
            ft.Text("📌 Détails analytiques des ventilations", size=13 if is_mob else 14, weight=safe_weight(True)),
            ft.Divider(height=8, color="transparent")
        ]

        details_list = [
            ("TVA Collectée standard (20%)", f"{data['tva_20']:.2f} €"),
            ("TVA Collectée intermédiaire (10%)", f"{data['tva_10']:.2f} €"),
            ("TVA Collectée 1ère nécessité (5.5%)", f"{data['tva_5']:.2f} €"),
            ("TVA Auto-liquidation Intracomm.", f"{data['tva_autoliquidee']:.2f} €"),
            ("Volume des charges (HT)", f"{data['total_charges_ht']:.2f} €")
        ]

        for libelle, val in details_list:
            detail_controls.append(
                ft.Row(
                    controls=[
                        ft.Text(libelle, size=11 if is_mob else 12, color="#CCCCCC", expand=True),
                        ft.Text(val, size=11 if is_mob else 12, weight=safe_weight(True), text_align=safe_text_align("right"))
                    ],
                    alignment=safe_main_align("spaceBetween")
                )
            )

        detail_box = ft.Container(
            bgcolor="#141416",
            border_radius=10,
            padding=12,
            expand=not is_mob,
            content=ft.Column(
                controls=detail_controls,
                scroll=None if is_mob else safe_scroll(),
                spacing=8
            )
        )

        self.main_container.content = ft.Column(
            controls=[
                cards_container,
                solde_frame,
                detail_box
            ],
            expand=True,
            spacing=10,
            scroll=safe_scroll() if is_mob else None
        )

    def _afficher_registre_charges(self):
        is_mob = self._is_mobile()

        e_desc = ft.TextField(label="Désignation", hint_text="ex: Abonnement Serveur", text_size=12 if is_mob else 14)
        e_ht = ft.TextField(label="Montant HT (€)", hint_text="0.00", text_size=12 if is_mob else 14)

        combo_taux = ft.Dropdown(
            label="Taux TVA (%)",
            value="20",
            options=[
                ft.dropdown.Option("20"),
                ft.dropdown.Option("10"),
                ft.dropdown.Option("5.5"),
                ft.dropdown.Option("2.1")
            ],
            text_size=12 if is_mob else 14
        )

        e_coef = ft.TextField(label="Coeff. Récupération (%)", value="100", text_size=12 if is_mob else 14)
        var_auto = ft.Checkbox(label="Auto-liquidée (Intracomm.)", value=False)

        def ajouter_charge(e):
            try:
                desc = e_desc.value.strip() if e_desc.value else ""
                ht = safe_float(e_ht.value)
                taux = safe_float(combo_taux.value)
                coef = safe_float(e_coef.value) if e_coef.value else 100.0
                if not desc or ht <= 0:
                    raise ValueError()

                self.app.charges.append({
                    "date": datetime.now().strftime("%d/%m/%Y"),
                    "description": desc,
                    "ht": ht,
                    "taux": taux,
                    "coef_recup": coef,
                    "autoliquide": var_auto.value
                })
                if hasattr(self.app, "save_data"):
                    self.app.save_data()

                self.show_snack("Charge enregistrée avec succès. ✔", e=e)
                self._afficher_registre_charges()
                self.safe_update()
            except Exception:
                self.show_snack("Erreur : Saisie incorrecte.", is_error=True, e=e)

        btn_save = safe_button(
            text="💾 Enregistrer la charge",
            on_click=ajouter_charge,
            bgcolor="#388E3C",
            color="white",
            height=40
        )

        form_box = ft.Container(
            expand=4 if not is_mob else None,
            bgcolor="#141416",
            border_radius=10,
            padding=12 if is_mob else 15,
            content=ft.Column(
                controls=[
                    ft.Text("➕ Nouvelle Charge", size=14, weight=safe_weight(True)),
                    e_desc,
                    e_ht,
                    combo_taux,
                    e_coef,
                    var_auto,
                    ft.Divider(height=5, color="transparent"),
                    btn_save
                ],
                spacing=8,
                scroll=None if is_mob else safe_scroll()
            )
        )

        list_controls = []
        if not getattr(self.app, "charges", []):
            list_controls.append(
                ft.Container(
                    alignment=getattr(ft, "alignment", None) and getattr(ft.alignment, "center", None),
                    padding=20,
                    content=ft.Text("Aucune charge enregistrée.", color="#636366", size=12)
                )
            )
        else:
            for c in reversed(self.app.charges):
                try:
                    c_ht = safe_float(c.get("ht", 0))
                    c_taux = safe_float(c.get("taux", 20))
                    c_coef = safe_float(c.get("coef_recup", 100)) / 100.0
                    tva_recup = (c_ht * (c_taux / 100.0)) * c_coef
                    c_desc = c.get("description", "Sans nom")
                    c_date = c.get("date", datetime.now().strftime("%d/%m/%Y"))
                except Exception:
                    c_ht, c_taux, tva_recup, c_desc, c_date = 0.0, 20.0, 0.0, "Donnée corrompue", "--/--/----"

                txt_l = f"📅 {c_date} - {c_desc}\nBase HT: {c_ht:.2f} € | Taux: {c_taux}%"

                card = ft.Container(
                    bgcolor="#242426",
                    border_radius=8,
                    padding=8 if is_mob else 10,
                    content=ft.Row(
                        controls=[
                            ft.Text(txt_l, size=11 if is_mob else 12, expand=True),
                            ft.Text(f"TVA Récup.\n{tva_recup:.2f} €", size=11 if is_mob else 12, weight=safe_weight(True), color="#66BB6A", text_align=safe_text_align("right"))
                        ],
                        alignment=safe_main_align("spaceBetween")
                    )
                )
                list_controls.append(card)

        scroll_list = ft.Container(
            expand=6 if not is_mob else None,
            bgcolor="#141416",
            border_radius=10,
            padding=12 if is_mob else 15,
            content=ft.Column(
                controls=list_controls,
                scroll=None if is_mob else safe_scroll(),
                spacing=8
            )
        )

        if is_mob:
            self.main_container.content = ft.Column(
                controls=[
                    form_box,
                    ft.Text("📋 Charges Enregistrées", size=14, weight=safe_weight(True), color="white"),
                    scroll_list
                ],
                spacing=10,
                scroll=safe_scroll(),
                expand=True
            )
        else:
            self.main_container.content = ft.Row(
                controls=[form_box, scroll_list],
                spacing=12,
                expand=True
            )

    def _afficher_assistant_ca3(self):
        data = self._calculer_metriques_financieres()
        is_mob = self._is_mobile()

        ca3_lines = [
            ("Ligne 01 : Ventes, Prestations (Base HT)", f"{data['ca_ht']:.2f} €"),
            ("Ligne 02 : Auto-liquidation Intracomm.", f"{data['tva_autoliquidee']:.2f} €"),
            ("Ligne 08 : Taux Normal (20%)", f"{data['tva_20']:.2f} €"),
            ("Ligne 09 : Taux Réduit (10%)", f"{data['tva_10']:.2f} €"),
            ("Ligne 19 : TVA brute totale due", f"{data['tva_collectee']:.2f} €"),
            ("Ligne 20 : TVA déductible sur biens/services", f"{data['tva_deductible']:.2f} €"),
        ]

        rows = []
        for code, mnt in ca3_lines:
            row_item = ft.Container(
                bgcolor="#1E1E20",
                padding=8 if is_mob else 10,
                border_radius=8,
                content=ft.Row(
                    controls=[
                        ft.Text(code, size=11 if is_mob else 12, expand=True),
                        ft.Text(mnt, size=12 if is_mob else 13, weight=safe_weight(True), color="#F5A623", font_family="Courier New")
                    ],
                    alignment=safe_main_align("spaceBetween")
                )
            )
            rows.append(row_item)

        self.main_container.content = ft.Container(
            bgcolor="#141416",
            border_radius=10,
            padding=12 if is_mob else 15,
            expand=True,
            content=ft.Column(controls=rows, scroll=safe_scroll(), spacing=8)
        )

    def show_snack(self, message, is_error=False, e=None):
        page = getattr(self, "page", None) or getattr(self.app, "page", None)
        if not page:
            return
        snack = ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor="#D32F2F" if is_error else "#388E3C",
            dismiss_direction=getattr(ft, "DismissDirection", None) and getattr(ft.DismissDirection, "HORIZONTAL", "horizontal") or "horizontal"
        )
        try:
            page.open(snack)
        except Exception:
            try:
                page.snack_bar = snack
                snack.open = True
                page.update()
            except Exception:
                pass
