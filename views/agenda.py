import calendar
from datetime import datetime
import flet as ft


def safe_border(width=1, color="#2A2A32"):
    """Bordure universelle sécurisée compatible Desktop et Mobile."""
    side = ft.BorderSide(width, color)
    return ft.Border(top=side, right=side, bottom=side, left=side)


class AgendaView(ft.Container):
    """Vue Agenda et Planification optimisée pour Smartphone et Desktop."""

    def __init__(self, app):
        super().__init__(expand=True, padding=10)
        self.app = app

        # Récupération de la couleur d'accentuation
        self.entreprise_data = getattr(
            self.app, "entreprise", getattr(self.app, "association", {})
        )
        self.accent_color = self.entreprise_data.get("accent_color", "#2B719E")

        # Synchronisation de la liste d'événements
        agenda_raw = getattr(self.app, "agenda", [])
        if isinstance(agenda_raw, list):
            self.app.agenda_events = agenda_raw
        else:
            self.app.agenda_events = []
            self.app.agenda = self.app.agenda_events

        self.current_date = datetime.now()
        self.selected_date = self.current_date

        self._build_interface()

    def get_page(self):
        """Récupère l'instance active de la page Flet."""
        return self.page or getattr(self.app, "page", None)

    def safe_update(self):
        """Mise à jour sécurisée de l'UI."""
        page_obj = self.get_page()
        if page_obj:
            try:
                page_obj.update()
            except Exception:
                pass

    def did_mount(self):
        """Initialisation lors de l'affichage."""
        self._update_calendar()

    def _build_interface(self):
        icon_back = (
            ft.Icons.ARROW_BACK_ROUNDED
            if hasattr(ft, "Icons")
            else "arrow_back_rounded"
        )
        icon_prev = (
            ft.Icons.CHEVRON_LEFT if hasattr(ft, "Icons") else "chevron_left"
        )
        icon_next = (
            ft.Icons.CHEVRON_RIGHT if hasattr(ft, "Icons") else "chevron_right"
        )

        header = ft.Row(
            controls=[
                ft.IconButton(
                    icon=icon_back,
                    on_click=lambda e: getattr(
                        self.app, "navigate_to", lambda x: None
                    )("Dashboard"),
                ),
                ft.Text("📅 Agenda & Planification", size=20, weight="bold"),
            ],
            alignment=ft.MainAxisAlignment.START,
        )

        self.lbl_selected_date = ft.Text(
            self.selected_date.strftime("%d/%m/%Y"),
            size=13,
            weight="bold",
            color="#38BDF8",
        )

        self.tf_titre = ft.TextField(
            label="Titre du RDV / Tâche *",
            bgcolor="#242426",
            height=45,
            text_size=12,
        )
        self.tf_heure = ft.TextField(
            label="Heure (ex: 14:30)",
            bgcolor="#242426",
            height=45,
            text_size=12,
        )

        self.dd_type = ft.Dropdown(
            label="Type d'événement",
            options=[
                ft.dropdown.Option(key="Client", text="👥 Rdv Client"),
                ft.dropdown.Option(key="Fournisseur", text="📦 Point Fournisseur"),
                ft.dropdown.Option(key="Administratif", text="📝 Administratif"),
                ft.dropdown.Option(key="Autre", text="💡 Autre Tâche"),
            ],
            value="Client",
            height=45,
            text_size=12,
        )

        self.tf_desc = ft.TextField(
            label="Notes / Description",
            bgcolor="#242426",
            multiline=True,
            min_lines=2,
            max_lines=2,
            text_size=12,
        )

        btn_add = ft.ElevatedButton(
            content=ft.Text("➕ Ajouter à l'agenda"),
            bgcolor=self.accent_color,
            color="white",
            on_click=self._ajouter_evenement,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
        )

        form_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "📝 Nouveau Rendez-vous",
                        size=14,
                        weight="bold",
                        color=self.accent_color,
                    ),
                    ft.Row(
                        [
                            ft.Text("Date choisie : ", size=11, color="#AEAEB2"),
                            self.lbl_selected_date,
                        ]
                    ),
                    ft.Divider(height=5, color="#2A2A2E"),
                    self.tf_titre,
                    self.tf_heure,
                    self.dd_type,
                    self.tf_desc,
                    ft.Row([btn_add], alignment=ft.MainAxisAlignment.CENTER),
                ],
                spacing=8,
            ),
            bgcolor="#1A1A1C",
            border_radius=10,
            padding=12,
            border=safe_border(1, "#2A2A2E"),
        )

        self.events_list = ft.Column(spacing=8)

        events_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "📋 Événements de la journée",
                        size=14,
                        weight="bold",
                    ),
                    ft.Divider(height=5, color="#2A2A2E"),
                    self.events_list,
                ],
                spacing=8,
            ),
            bgcolor="#141416",
            border_radius=10,
            padding=12,
            border=safe_border(1, "#2A2A2E"),
        )

        self.calendar_weeks_container = ft.Column(spacing=5)
        self.lbl_month_year = ft.Text("", size=15, weight="bold")

        calendar_header = ft.Row(
            [
                ft.IconButton(icon=icon_prev, on_click=self._prev_month),
                self.lbl_month_year,
                ft.IconButton(icon=icon_next, on_click=self._next_month),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        calendar_card = ft.Container(
            content=ft.Column(
                [
                    calendar_header,
                    self._build_weekday_headers(),
                    self.calendar_weeks_container,
                ],
                spacing=10,
            ),
            bgcolor="#1A1A1C",
            border_radius=12,
            padding=10,
            border=safe_border(1, "#2A2A2E"),
        )

        # Disposition en colonne défilante (Mobile-first)
        self.content = ft.Column(
            [
                header,
                calendar_card,
                form_container,
                events_container,
            ],
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _build_weekday_headers(self):
        jours = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
        return ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        j, size=10, weight="bold", color="#636366"
                    ),
                    alignment=ft.Alignment(0, 0),
                    expand=True,
                )
                for j in jours
            ],
            spacing=2,
        )

    def _update_calendar(self):
        self.calendar_weeks_container.controls.clear()

        mois_noms = [
            "Janvier",
            "Février",
            "Mars",
            "Avril",
            "Mai",
            "Juin",
            "Juillet",
            "Août",
            "Septembre",
            "Octobre",
            "Novembre",
            "Décembre",
        ]
        self.lbl_month_year.value = (
            f"{mois_noms[self.current_date.month - 1]} {self.current_date.year}"
        )
        self.lbl_selected_date.value = self.selected_date.strftime("%d/%m/%Y")

        cal = calendar.monthcalendar(
            self.current_date.year, self.current_date.month
        )
        colors = {
            "Client": "#3B82F6",
            "Fournisseur": "#10B981",
            "Administratif": "#F59E0B",
            "Autre": "#6B7280",
        }

        agenda_events = getattr(self.app, "agenda_events", [])

        for week in cal:
            week_row = ft.Row(expand=True, spacing=2)
            for day in week:
                if day == 0:
                    week_row.controls.append(ft.Container(expand=True))
                else:
                    is_selected = (
                        day == self.selected_date.day
                        and self.current_date.month == self.selected_date.month
                        and self.current_date.year == self.selected_date.year
                    )

                    date_str = f"{self.current_date.year}-{self.current_date.month:02d}-{day:02d}"
                    day_events = [
                        ev
                        for ev in agenda_events
                        if ev.get("date") == date_str
                    ]
                    has_events = len(day_events) > 0

                    bg = self.accent_color if is_selected else "#242426"
                    text_color = (
                        "white"
                        if is_selected
                        else ("#93C5FD" if has_events else "white")
                    )
                    border_color = (
                        "#60A5FA"
                        if (has_events and not is_selected)
                        else "#2A2A2E"
                    )

                    cell_content = ft.Column(
                        controls=[
                            ft.Text(
                                str(day),
                                size=10,
                                color=text_color,
                                weight="bold"
                                if (is_selected or has_events)
                                else "normal",
                            ),
                        ],
                        spacing=2,
                        alignment=ft.MainAxisAlignment.START,
                        horizontal_alignment=ft.CrossAxisAlignment.START,
                    )

                    day_events.sort(key=lambda x: x.get("heure", "00:00"))
                    for ev in day_events[:1]:
                        bg_badge = colors.get(ev.get("type"), "#6B7280")
                        cell_content.controls.append(
                            ft.Container(
                                content=ft.Text(
                                    f"{ev.get('heure')}",
                                    size=7,
                                    color="white",
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=1,
                                    no_wrap=True,
                                ),
                                bgcolor=bg_badge,
                                border_radius=2,
                                padding=1,  # Correction du padding ici
                                alignment=ft.Alignment(-1, 0),
                            )
                        )

                    if len(day_events) > 1:
                        cell_content.controls.append(
                            ft.Text(
                                f"+{len(day_events)-1}",
                                size=7,
                                color="#AEAEB2",
                                italic=True,
                            )
                        )

                    btn_day = ft.Container(
                        content=cell_content,
                        padding=4,
                        bgcolor=bg,
                        border_radius=5,
                        border=safe_border(1, border_color),
                        on_click=lambda e, d=day: self._select_day(d),
                        expand=True,
                    )
                    week_row.controls.append(btn_day)

            self.calendar_weeks_container.controls.append(week_row)

        self._load_events_for_selected_date()
        self.safe_update()

    def _select_day(self, day):
        self.selected_date = datetime(
            self.current_date.year, self.current_date.month, day
        )
        self._update_calendar()

    def _prev_month(self, e):
        month = self.current_date.month - 1
        year = self.current_date.year
        if month == 0:
            month = 12
            year -= 1
        self.current_date = datetime(year, month, 1)
        self._update_calendar()

    def _next_month(self, e):
        month = self.current_date.month + 1
        year = self.current_date.year
        if month == 13:
            month = 1
            year += 1
        self.current_date = datetime(year, month, 1)
        self._update_calendar()

    def _load_events_for_selected_date(self):
        self.events_list.controls.clear()
        date_str = self.selected_date.strftime("%Y-%m-%d")

        agenda_events = getattr(self.app, "agenda_events", [])
        events = [ev for ev in agenda_events if ev.get("date") == date_str]

        if not events:
            self.events_list.controls.append(
                ft.Text(
                    "Aucun événement prévu à cette date.",
                    size=12,
                    italic=True,
                    color="#636366",
                )
            )
            return

        events.sort(key=lambda x: x.get("heure", "00:00"))
        colors = {
            "Client": "#3B82F6",
            "Fournisseur": "#10B981",
            "Administratif": "#F59E0B",
            "Autre": "#6B7280",
        }

        icon_delete = (
            ft.Icons.DELETE_OUTLINE
            if hasattr(ft, "Icons")
            else "delete_outline"
        )

        for ev in events:
            bg_badge = colors.get(ev.get("type"), "#6B7280")

            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            width=4, bgcolor=bg_badge, border_radius=2
                        ),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(
                                            f"⏰ {ev.get('heure', '--:--')}",
                                            size=11,
                                            weight="bold",
                                        ),
                                        ft.Container(
                                            content=ft.Text(
                                                f" {str(ev.get('type')).upper()} ",
                                                size=8,
                                                weight="bold",
                                                color="white",
                                            ),
                                            bgcolor=bg_badge,
                                            border_radius=4,
                                            padding=2,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                ft.Text(
                                    ev.get("titre", "Sans titre"),
                                    size=12,
                                    weight="bold",
                                ),
                                ft.Text(
                                    ev.get("description", ""),
                                    size=10,
                                    color="#AEAEB2",
                                )
                                if ev.get("description")
                                else ft.Container(),
                            ],
                            expand=True,
                            spacing=2,
                        ),
                        ft.IconButton(
                            icon=icon_delete,
                            icon_size=15,
                            icon_color="#F87171",
                            on_click=lambda e, event=ev: self._supprimer_evenement(
                                event
                            ),
                        ),
                    ]
                ),
                bgcolor="#242426",
                border_radius=8,
                padding=8,
                border=safe_border(1, "#3A3A3C"),
            )
            self.events_list.controls.append(card)

    def _ajouter_evenement(self, e):
        titre = self.tf_titre.value.strip() if self.tf_titre.value else ""
        if not titre:
            self._show_snackbar("Le titre du rendez-vous est obligatoire.", is_error=True)
            return

        heure = self.tf_heure.value.strip() if self.tf_heure.value else "--:--"

        ev_data = {
            "date": self.selected_date.strftime("%Y-%m-%d"),
            "heure": heure,
            "titre": titre,
            "type": self.dd_type.value,
            "description": (
                self.tf_desc.value.strip() if self.tf_desc.value else ""
            ),
        }

        if not hasattr(self.app, "agenda_events") or not isinstance(self.app.agenda_events, list):
            self.app.agenda_events = []

        self.app.agenda_events.append(ev_data)
        if hasattr(self.app, "save_data"):
            self.app.save_data()

        self.tf_titre.value = ""
        self.tf_heure.value = ""
        self.tf_desc.value = ""

        self._update_calendar()
        self._show_snackbar("Événement ajouté à l'agenda ! ✔")

    def _supprimer_evenement(self, ev):
        if hasattr(self.app, "agenda_events") and isinstance(self.app.agenda_events, list):
            if ev in self.app.agenda_events:
                self.app.agenda_events.remove(ev)
                if hasattr(self.app, "save_data"):
                    self.app.save_data()
                self._update_calendar()
                self._show_snackbar("Événement supprimé.")

    def _show_snackbar(self, message: str, is_error: bool = False):
        color = "#B91C1C" if is_error else "#15803D"
        page_obj = self.get_page()
        if page_obj:
            snack = ft.SnackBar(content=ft.Text(message), bgcolor=color)
            try:
                page_obj.open(snack)
            except Exception:
                page_obj.snack_bar = snack
                snack.open = True
                page_obj.update()