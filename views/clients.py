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


class ClientsView(ft.Container):
    """Vue Flet sécurisée et réactive pour la gestion du répertoire clients."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.expand = True
        self.padding = 10
        self.selected_client_index = None

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
                ft.Text("👥 Répertoire Clients", size=20, weight="bold", color="white"),
            ]
        )

        self.search_entry = ft.TextField(
            hint_text="🔍 Rechercher un client...",
            bgcolor="#1A1A1C",
            height=45,
            text_size=13,
            content_padding=10,
            border_color="#2A2A32",
            focused_border_color="#2B719E",
            text_style=ft.TextStyle(color="white"),
            on_change=self._refresh_table,
        )

        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Nom / Entreprise", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Email", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Téléphone", weight="bold", color="white")),
                ft.DataColumn(ft.Text("Ville", weight="bold", color="white")),
            ],
            rows=[],
            heading_row_color="#242426",
            show_checkbox_column=False,
        )

        button_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))

        actions = ft.ResponsiveRow(
            controls=[
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "➕ Nouveau Client",
                            bgcolor="#2B719E",
                            color="white",
                            height=40,
                            style=button_style,
                            on_click=self.ajouter_client,
                        )
                    ],
                    col={"xs": 12, "sm": 4},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "✏️ Modifier",
                            bgcolor="#F59E0B",
                            color="white",
                            height=40,
                            style=button_style,
                            on_click=self.modifier_client,
                        )
                    ],
                    col={"xs": 6, "sm": 4},
                ),
                ft.Column(
                    [
                        ft.ElevatedButton(
                            "🗑️ Supprimer",
                            bgcolor="#DC2626",
                            color="white",
                            height=40,
                            style=button_style,
                            on_click=self.supprimer_client,
                        )
                    ],
                    col={"xs": 6, "sm": 4},
                ),
            ],
            spacing=10,
        )

        self.main_layout.controls = [header, self.search_entry, actions, self.display_container]

    def _refresh_table(self, e=None):
        if hasattr(self.app, "load_data"):
            self.app.load_data()

        query = (
            self.search_entry.value.strip().lower()
            if self.search_entry and self.search_entry.value
            else ""
        )
        clients = getattr(self.app, "clients", [])

        filtered = []
        for i, cli in enumerate(clients):
            nom = cli.get("nom", "") if isinstance(cli, dict) else str(cli)
            email = cli.get("email", "") if isinstance(cli, dict) else ""
            if query in nom.lower() or query in email.lower():
                filtered.append((i, cli))

        if self._is_mobile():
            self._render_mobile(filtered)
        else:
            self._render_desktop(filtered)

        self.safe_update()

    def _render_desktop(self, clients):
        self.table.rows.clear()
        for idx, cli in clients:
            row = ft.DataRow(cells=[], selected=(self.selected_client_index == idx))

            def make_select_handler(real_idx):
                return lambda e: self._select_client(real_idx)

            nom = cli.get("nom", "Inconnu") if isinstance(cli, dict) else str(cli)
            email = cli.get("email", "-") if isinstance(cli, dict) else "-"
            tel = cli.get("telephone", cli.get("tel", "-")) if isinstance(cli, dict) else "-"
            ville = cli.get("ville", "-") if isinstance(cli, dict) else "-"

            row.cells = [
                ft.DataCell(ft.Text(nom, color="white"), on_tap=make_select_handler(idx)),
                ft.DataCell(ft.Text(email, color="white"), on_tap=make_select_handler(idx)),
                ft.DataCell(ft.Text(tel, color="white"), on_tap=make_select_handler(idx)),
                ft.DataCell(ft.Text(ville, color="white"), on_tap=make_select_handler(idx)),
            ]

            self.table.rows.append(row)

        self.display_container.content = ft.Container(
            content=ft.Column(
                [ft.Row([self.table], scroll=ft.ScrollMode.AUTO)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            bgcolor="#141416",
            border_radius=10,
            border=safe_border(1, "#2A2A2E"),
            padding=8,
            expand=True,
        )

    def _render_mobile(self, clients):
        cards = []
        for idx, cli in clients:
            is_sel = self.selected_client_index == idx
            nom = cli.get("nom", "Inconnu") if isinstance(cli, dict) else str(cli)
            email = cli.get("email", "-") if isinstance(cli, dict) else "-"

            def make_select_handler(real_idx):
                return lambda e: self._select_client(real_idx)

            cards.append(
                ft.Container(
                    bgcolor="#2A3A4E" if is_sel else "#1E1E22",
                    border=safe_border(1.5 if is_sel else 1, "#2B719E" if is_sel else "#2A2A32"),
                    border_radius=10,
                    padding=12,
                    on_click=make_select_handler(idx),
                    content=ft.Column(
                        [
                            ft.Text(nom, weight="bold", color="white"),
                            ft.Text(email, size=11, color="#AEAEB2"),
                        ],
                        spacing=4,
                    ),
                )
            )

        self.display_container.content = ft.ListView(controls=cards, spacing=8, expand=True)

    def _select_client(self, real_idx):
        if self.selected_client_index == real_idx:
            self.selected_client_index = None
        else:
            self.selected_client_index = real_idx
        self._refresh_table()

    def ajouter_client(self, e=None):
        self._ouvrir_formulaire_client(e=e)

    def modifier_client(self, e=None):
        if self.selected_client_index is None or not hasattr(self.app, "clients"):
            return self._show_snack("Veuillez sélectionner un client à modifier.", is_error=True, e=e)

        clients = getattr(self.app, "clients", [])
        if 0 <= self.selected_client_index < len(clients):
            self._ouvrir_formulaire_client(client=clients[self.selected_client_index], e=e)

    def _ouvrir_formulaire_client(self, client=None, e=None):
        is_edit = client is not None

        nom_field = ft.TextField(
            label="Nom / Entreprise",
            value=client.get("nom", "") if is_edit else "",
            autofocus=True,
            bgcolor="#1A1A1C",
        )
        email_field = ft.TextField(
            label="Email",
            value=client.get("email", "") if is_edit else "",
            bgcolor="#1A1A1C",
        )
        tel_field = ft.TextField(
            label="Téléphone",
            value=client.get("telephone", client.get("tel", "")) if is_edit else "",
            bgcolor="#1A1A1C",
        )
        adresse_field = ft.TextField(
            label="Adresse",
            value=client.get("adresse", "") if is_edit else "",
            bgcolor="#1A1A1C",
        )
        cp_field = ft.TextField(
            label="Code Postal",
            value=client.get("code_postal", client.get("cp", "")) if is_edit else "",
            bgcolor="#1A1A1C",
        )
        ville_field = ft.TextField(
            label="Ville",
            value=client.get("ville", "") if is_edit else "",
            bgcolor="#1A1A1C",
        )

        def valider(evt):
            nom_val = nom_field.value.strip()
            if not nom_val:
                return self._show_snack("Le nom du client est obligatoire.", is_error=True, e=evt)

            data = {
                "nom": nom_val,
                "email": email_field.value.strip(),
                "telephone": tel_field.value.strip(),
                "tel": tel_field.value.strip(),
                "adresse": adresse_field.value.strip(),
                "code_postal": cp_field.value.strip(),
                "cp": cp_field.value.strip(),
                "ville": ville_field.value.strip(),
            }

            if not hasattr(self.app, "clients") or not isinstance(self.app.clients, list):
                self.app.clients = []

            if is_edit:
                self.app.clients[self.selected_client_index] = data
            else:
                self.app.clients.append(data)

            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack("Client enregistré avec succès.", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("✏️ Modifier le client" if is_edit else "➕ Nouveau Client"),
            content=ft.Column(
                [nom_field, email_field, tel_field, adresse_field, cp_field, ville_field],
                tight=True,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Enregistrer", bgcolor="#2B719E", color="white", on_click=valider),
            ],
        )
        self._open_dialog(dialog, e=e)

    def supprimer_client(self, e=None):
        if self.selected_client_index is None or not hasattr(self.app, "clients"):
            return self._show_snack("Veuillez sélectionner un client à supprimer.", is_error=True, e=e)

        clients = getattr(self.app, "clients", [])
        if not (0 <= self.selected_client_index < len(clients)):
            return

        cli = clients[self.selected_client_index]
        nom = cli.get("nom", "ce client") if isinstance(cli, dict) else str(cli)

        def valider(evt):
            self.app.clients.pop(self.selected_client_index)
            self.selected_client_index = None
            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._close_dialog(dialog, e=evt)
            self._refresh_table()
            self._show_snack("Client supprimé.", e=evt)

        dialog = ft.AlertDialog(
            title=ft.Text("🗑️ Suppression"),
            content=ft.Text(f"Supprimer le client « {nom} » ?"),
            actions=[
                ft.TextButton("Annuler", on_click=lambda evt: self._close_dialog(dialog, e=evt)),
                ft.ElevatedButton("Supprimer", bgcolor="#DC2626", color="white", on_click=valider),
            ],
        )
        self._open_dialog(dialog, e=e)