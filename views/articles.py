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


class ArticlesView(ft.Container):
    """Vue Flet sécurisée et réactive pour la gestion du catalogue d'articles et des stocks."""

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
        self.selected_index = None

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
        try:
            return float(entreprise.get("taux_tva", entreprise.get("tva", 20.0)))
        except (ValueError, TypeError):
            return 20.0

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

        self._refresh_table()

    def _on_page_resize(self, e=None):
        self._refresh_table()

    def _is_mobile(self):
        page = self._get_page()
        return page.width < 768 if (page and page.width) else False

    def _open_dialog(self, dialog, e=None):
        """Ouvre une fenêtre modale de manière universelle."""
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
        """Ferme proprement une fenêtre modale."""
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
                ft.Text("📦 Gestion des Articles & Stocks", size=22, weight="bold", color="white"),
            ]
        )

        button_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))

        top_buttons = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "➕ Nouvel Article",
                    bgcolor=self.accent_color,
                    color="white",
                    height=38,
                    style=button_style,
                    on_click=self.ajouter_article,
                ),
            ],
            spacing=10,
        )

        self.search_entry = ft.TextField(
            hint_text="🔍 Rechercher par référence, désignation, code-barres...",
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
                ft.DataColumn(ft.Text("Réf", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Désignation", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Prix HT", weight="bold", color="white")),
                ft.DataColumn(ft.Text("TVA (%)", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Prix TTC", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Stock", weight="bold", color="white")),
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
                            on_click=self.modifier_article,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 3},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "🗑️ Supprimer",
                            bgcolor="#DC2626",
                            color="white",
                            height=38,
                            style=button_style,
                            on_click=self.supprimer_article,
                        )
                    ],
                    col={"xs": 6, "sm": 4, "md": 3},
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

        query = (
            self.search_entry.value.strip().lower()
            if self.search_entry and self.search_entry.value
            else ""
        )

        articles = getattr(self.app, "articles", [])
        filtered_articles = []

        for idx, art in enumerate(articles):
            ref = str(art.get("ref", "")).lower()
            nom = str(art.get("designation", art.get("nom", ""))).lower()
            cb = str(art.get("code_barre", "")).lower()

            if not query or query in ref or query in nom or query in cb:
                filtered_articles.append((idx, art))

        if self._is_mobile():
            self._render_mobile(filtered_articles)
        else:
            self._render_desktop(filtered_articles)

        self.safe_update()

    def _render_desktop(self, filtered_articles):
        self.table.rows.clear()
        for idx, art in filtered_articles:
            is_selected = self.selected_index == idx

            def make_select_handler(i):
                return lambda e: self._select_article(i)

            prix_ht = float(art.get("prix_ht", art.get("prix", art.get("prix_unitaire", 0.0))))
            taux_tva = float(art.get("taux_tva", art.get("tva", self._get_default_tva())))
            prix_ttc = float(art.get("prix_ttc", prix_ht * (1 + taux_tva / 100)))
            stock = int(art.get("stock", 0))

            row = ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(art.get("ref", "-")), color="white"), on_tap=make_select_handler(idx)),
                    ft.DataCell(ft.Text(str(art.get("designation", art.get("nom", "-"))), color="white"), on_tap=make_select_handler(idx)),
                    ft.DataCell(ft.Text(f"{prix_ht:.2f} €", color="white"), on_tap=make_select_handler(idx)),
                    ft.DataCell(ft.Text(f"{taux_tva:.1f} %", color="white"), on_tap=make_select_handler(idx)),
                    ft.DataCell(ft.Text(f"{prix_ttc:.2f} €", color="white"), on_tap=make_select_handler(idx)),
                    ft.DataCell(
                        ft.Text(
                            str(stock),
                            color="#10B981" if stock > 5 else "#EF4444",
                            weight="bold",
                        ),
                        on_tap=make_select_handler(idx),
                    ),
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

    def _render_mobile(self, filtered_articles):
        cards = []
        for idx, art in filtered_articles:
            is_selected = self.selected_index == idx
            prix_ht = float(art.get("prix_ht", art.get("prix", art.get("prix_unitaire", 0.0))))
            stock = int(art.get("stock", 0))

            def make_select_handler(i):
                return lambda e: self._select_article(i)

            cards.append(
                ft.Container(
                    bgcolor="#2A3A4E" if is_selected else "#1E1E22",
                    border=safe_border(
                        1.5 if is_selected else 1,
                        self.accent_color if is_selected else "#2A2A32",
                    ),
                    border_radius=10,
                    padding=12,
                    on_click=make_select_handler(idx),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        str(art.get("designation", art.get("nom", "-"))),
                                        weight="bold",
                                        color="white",
                                    ),
                                    ft.Text(
                                        f"{prix_ht:.2f} € HT",
                                        color="#10B981",
                                        weight="bold",
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(
                                f"Réf : {art.get('ref', '-')}",
                                color="#AEAEB2",
                                size=12,
                            ),
                            ft.Text(
                                f"Stock : {stock}",
                                size=12,
                                color="#10B981" if stock > 5 else "#EF4444",
                            ),
                        ],
                        spacing=4,
                    ),
                )
            )

        if not cards:
            cards.append(
                ft.Container(
                    content=ft.Text("Aucun article trouvé.", color="#AEAEB2", italic=True),
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

    def _select_article(self, index):
        if self.selected_index == index:
            self.selected_index = None
        else:
            self.selected_index = index
        self._refresh_table()

    def ajouter_article(self, e=None):
        self._ouvrir_formulaire_article(e=e)

    def modifier_article(self, e=None):
        if self.selected_index is None:
            return self._show_snack("Veuillez sélectionner un article.", is_error=True, e=e)

        articles = getattr(self.app, "articles", [])
        if 0 <= self.selected_index < len(articles):
            self._ouvrir_formulaire_article(article=articles[self.selected_index], e=e)

    def _ouvrir_formulaire_article(self, article=None, e=None):
        is_edit = article is not None

        ref_tf = ft.TextField(
            label="Référence",
            value=article.get("ref", "") if is_edit else "",
            bgcolor="#1A1A1C",
        )
        nom_tf = ft.TextField(
            label="Désignation",
            value=article.get("designation", article.get("nom", "")) if is_edit else "",
            bgcolor="#1A1A1C",
        )
        cb_tf = ft.TextField(
            label="Code-barres",
            value=article.get("code_barre", "") if is_edit else "",
            bgcolor="#1A1A1C",
        )
        prix_tf = ft.TextField(
            label="Prix HT (€)",
            value=str(article.get("prix_ht", article.get("prix", article.get("prix_unitaire", 0.0)))) if is_edit else "0.0",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor="#1A1A1C",
        )
        tva_tf = ft.TextField(
            label="TVA (%)",
            value=str(article.get("taux_tva", article.get("tva", self._get_default_tva()))) if is_edit else str(self._get_default_tva()),
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor="#1A1A1C",
        )
        stock_tf = ft.TextField(
            label="Stock",
            value=str(article.get("stock", 0)) if is_edit else "0",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor="#1A1A1C",
        )

        def enregistrer(evt):
            try:
                prix_val = float(prix_tf.value.replace(",", "."))
                tva_val = float(tva_tf.value.replace(",", "."))
                stock_val = int(stock_tf.value)
            except ValueError:
                return self._show_snack("Veuillez entrer des valeurs numériques valides.", is_error=True, e=evt)

            nom_val = nom_tf.value.strip()
            if not nom_val:
                return self._show_snack("La désignation de l'article est obligatoire.", is_error=True, e=evt)

            prix_ttc_val = prix_val * (1 + tva_val / 100)

            # Structure unifiée complète pour compatibilité totale avec la facturation
            data = {
                "ref": ref_tf.value.strip(),
                "designation": nom_val,
                "nom": nom_val,
                "code_barre": cb_tf.value.strip(),
                "prix_ht": prix_val,
                "prix": prix_val,
                "prix_unitaire": prix_val,
                "taux_tva": tva_val,
                "tva": tva_val,
                "prix_ttc": prix_ttc_val,
                "stock": stock_val,
            }

            if not hasattr(self.app, "articles") or not isinstance(self.app.articles, list):
                self.app.articles = []

            if is_edit:
                self.app.articles[self.selected_index] = data
            else:
                self.app.articles.append(data)

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack("Article enregistré avec succès !", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("✏️ Modifier Article" if is_edit else "➕ Nouvel Article"),
            content=ft.Column(
                [ref_tf, nom_tf, cb_tf, prix_tf, tva_tf, stock_tf],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Enregistrer", bgcolor=self.accent_color, color="white", on_click=enregistrer),
            ],
        )
        self._open_dialog(dialog, e=e)

    def supprimer_article(self, e=None):
        if self.selected_index is None:
            return self._show_snack("Veuillez sélectionner un article à supprimer.", is_error=True, e=e)

        articles = getattr(self.app, "articles", [])
        if not (0 <= self.selected_index < len(articles)):
            return

        art = articles[self.selected_index]

        def valider(evt):
            articles.pop(self.selected_index)
            self.selected_index = None

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack("Article supprimé avec succès.", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("🗑️ Suppression"),
            content=ft.Text(f"Supprimer l'article '{art.get('designation', art.get('nom', ''))}' ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Supprimer", bgcolor="#DC2626", color="white", on_click=valider),
            ],
        )
        self._open_dialog(dialog, e=e)

    def deduire_stock_facture(self, items):
        """Déduit la quantité vendue des articles en stock à partir des lignes d'un document."""
        articles_db = getattr(self.app, "articles", [])
        if not articles_db or not items:
            return

        for item in items:
            ref_cible = str(item.get("ref", "")).strip().lower()
            cb_cible = str(item.get("code_barre", "")).strip().lower()
            nom_cible = str(item.get("designation", item.get("nom", ""))).strip().lower()
            qte_vendue = int(item.get("quantite", item.get("qte", 1)))

            for art in articles_db:
                ref_art = str(art.get("ref", "")).strip().lower()
                cb_art = str(art.get("code_barre", "")).strip().lower()
                nom_art = str(art.get("designation", art.get("nom", ""))).strip().lower()

                if (ref_cible and ref_cible == ref_art) or (cb_cible and cb_cible == cb_art) or (nom_cible and nom_cible == nom_art):
                    stock_actuel = int(art.get("stock", 0))
                    art["stock"] = max(0, stock_actuel - qte_vendue)
                    break

        if hasattr(self.app, "save_data"):
            self.app.save_data()
        self._refresh_table()