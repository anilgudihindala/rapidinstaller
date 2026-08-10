"""
Native GTK3 GUI Application Dashboard & Management Interface for AppLaunch Engine.

Provides an enterprise macOS-style Application Manager featuring application discovery,
disk usage analytics, background installer progress, and one-click uninstallation.
"""

import os
import shutil
import subprocess
import threading
import sys
from typing import List, Optional
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from applaunch.core.installer import AppInstallerEngine
from applaunch.utils.logger import logger
from applaunch.utils.sys_info import (
    get_environment_info,
    get_installed_apps,
    is_default_installer,
    refresh_desktop_database,
    set_as_default_installer,
)

# Custom GTK CSS Design System
CSS_THEME = """
window {
    background-color: #0f141c;
    color: #e2e8f0;
    font-family: 'Inter', 'Segoe UI', 'Ubuntu', sans-serif;
}

headerbar {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-bottom: 1px solid #334155;
    padding: 6px 12px;
}

.title-header {
    font-size: 16px;
    font-weight: 700;
    color: #38bdf8;
}

.subtitle-header {
    font-size: 11px;
    color: #94a3b8;
}

.card-overview {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px 20px;
    margin: 12px 16px;
}

.stat-label {
    font-size: 11px;
    font-weight: bold;
    color: #94a3b8;
}

.stat-value {
    font-size: 22px;
    font-weight: 800;
    color: #38bdf8;
}

.app-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    margin: 6px 16px;
    padding: 12px 16px;
    transition: all 200ms ease-in-out;
}

.app-card:hover {
    background-color: #24334a;
    border-color: #38bdf8;
}

.app-title {
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
}

.app-subtitle {
    font-size: 12px;
    color: #94a3b8;
}

.badge-size {
    background-color: #0284c7;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    border-radius: 12px;
    padding: 2px 10px;
}

.btn-primary {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    border: none;
    padding: 8px 16px;
}

.btn-primary:hover {
    background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%);
}

.btn-default-installer {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    border: none;
    padding: 6px 12px;
    margin-left: 8px;
}

.btn-default-installer:hover {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.badge-default-active {
    background-color: #065f46;
    color: #34d399;
    font-size: 11px;
    font-weight: 700;
    border-radius: 12px;
    padding: 4px 10px;
    margin-left: 8px;
}

.btn-launch {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 6px;
    border: none;
    padding: 6px 14px;
}

.btn-launch:hover {
    background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
}

.btn-uninstall {
    background-color: transparent;
    color: #f87171;
    border: 1px solid #ef4444;
    font-weight: 600;
    border-radius: 6px;
    padding: 6px 12px;
}

.btn-uninstall:hover {
    background-color: #7f1d1d;
    color: #ffffff;
}

.empty-title {
    font-size: 18px;
    font-weight: 700;
    color: #cbd5e1;
}

.empty-desc {
    font-size: 13px;
    color: #64748b;
}

.search-entry {
    margin: 8px 16px;
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 8px;
}
"""


def load_css_theme() -> None:
    """Injects custom GTK CSS design provider into screen."""
    css_provider = Gtk.CssProvider()
    try:
        css_provider.load_from_data(CSS_THEME.encode("utf-8"))
        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
    except Exception as err:
        logger.warning(f"Could not load custom GTK CSS theme: {err}")


def uninstall_app_backend(app_id: str) -> bool:
    """Backend routine to uninstall application and clean desktop files."""
    env = get_environment_info()
    opt_path = os.path.join(env["opt_dir"], app_id)
    desktop_path = os.path.join(env["apps_dir"], f"{app_id}.desktop")
    user_desktop_path = os.path.expanduser(f"~/Desktop/{app_id}.desktop")

    if os.path.isdir(opt_path):
        shutil.rmtree(opt_path, ignore_errors=True)

    if os.path.isfile(desktop_path):
        try:
            os.remove(desktop_path)
        except Exception:
            pass

    if os.path.isfile(user_desktop_path):
        try:
            os.remove(user_desktop_path)
        except Exception:
            pass

    # Remove icon
    icons_dir = env["icons_dir"]
    if os.path.isdir(icons_dir):
        for f in os.listdir(icons_dir):
            if f.startswith(app_id):
                try:
                    os.remove(os.path.join(icons_dir, f))
                except Exception:
                    pass

    refresh_desktop_database()
    return True


class AppLaunchManagerWindow(Gtk.Window):
    """Main GTK Dashboard Window for Rapid Installer."""

    def __init__(self, initial_archive: Optional[str] = None) -> None:
        super().__init__(title="Rapid Installer")
        self.set_default_size(880, 640)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Enable Drag and Drop for package archive files
        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new("text/uri-list", 0, 0)],
            Gdk.DragAction.COPY,
        )
        self.connect("drag-data-received", self._on_drag_data_received)

        load_css_theme()
        self.env = get_environment_info()
        self._setup_headerbar()
        self._build_main_ui()

        # If launched with archive file, run installer dialog
        if initial_archive and os.path.isfile(initial_archive):
            GLib.idle_add(self._trigger_installation_flow, initial_archive)

    def _on_drag_data_received(self, widget, context, x, y, data, info, time) -> None:
        """Handles drag-and-drop of package archives onto window."""
        uris = data.get_uris()
        if uris:
            for uri in uris:
                parsed = urlparse(uri)
                filepath = unquote(parsed.path)
                if os.path.isfile(filepath):
                    self._trigger_installation_flow(filepath)
                    break
        context.finish(True, False, time)

    def _setup_headerbar(self) -> None:
        """Constructs modern GTK HeaderBar."""
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)

        # Title & Subtitle box
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lbl_title = Gtk.Label(label="Rapid Installer")
        lbl_title.get_style_context().add_class("title-header")

        lbl_sub = Gtk.Label(label="Smart Application Manager & Package Installer")
        lbl_sub.get_style_context().add_class("subtitle-header")

        title_box.pack_start(lbl_title, False, False, 0)
        title_box.pack_start(lbl_sub, False, False, 0)
        header.set_custom_title(title_box)

        # App Icon on header
        app_icon_path = os.path.expanduser("~/.local/share/icons/rapid-installer.jpg")
        if os.path.isfile(app_icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    app_icon_path, 28, 28, True
                )
                img = Gtk.Image.new_from_pixbuf(pixbuf)
                header.pack_start(img)
            except Exception:
                pass

        # Check Default Installer Status Widget Box
        self.default_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._update_default_installer_widget()
        header.pack_start(self.default_box)

        # Install Package Button
        btn_install = Gtk.Button(label="+ Install Package...")
        btn_install.get_style_context().add_class("btn-primary")
        btn_install.connect("clicked", self._on_install_clicked)
        header.pack_end(btn_install)

        # Settings Preferences Button
        btn_settings = Gtk.Button()
        img_settings = Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON)
        btn_settings.set_image(img_settings)
        btn_settings.set_tooltip_text("Rapid Installer Preferences")
        btn_settings.connect("clicked", lambda w: self._on_settings_clicked())
        header.pack_end(btn_settings)

        # Refresh Button
        btn_refresh = Gtk.Button()
        img_refresh = Gtk.Image.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        btn_refresh.set_image(img_refresh)
        btn_refresh.set_tooltip_text("Refresh installed applications")
        btn_refresh.connect("clicked", lambda w: self.refresh_apps_list())
        header.pack_end(btn_refresh)

        self.set_titlebar(header)

    def _update_default_installer_widget(self) -> None:
        """Updates default installer status badge or button on HeaderBar."""
        for c in self.default_box.get_children():
            self.default_box.remove(c)

        if is_default_installer():
            badge = Gtk.Label(label="✓ Default System Installer")
            badge.get_style_context().add_class("badge-default-active")
            self.default_box.pack_start(badge, False, False, 8)
        else:
            btn_def = Gtk.Button(label="★ Set as Default Installer")
            btn_def.get_style_context().add_class("btn-default-installer")
            btn_def.set_tooltip_text("Set Rapid Installer as your default handler for .tar.gz, .zip, .deb, .rpm, .AppImage archives")
            btn_def.connect("clicked", self._on_set_default_clicked)
            self.default_box.pack_start(btn_def, False, False, 8)

        self.default_box.show_all()

    def _on_set_default_clicked(self, widget: Gtk.Widget) -> None:
        """Registers Rapid Installer as system default installer."""
        success = set_as_default_installer()
        if success:
            self._update_default_installer_widget()
            toast = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Default Installer Configured!",
            )
            toast.format_secondary_text(
                "Rapid Installer is now registered as your default application installer for all Linux package archives (.tar.gz, .zip, .deb, .rpm, .7z, .AppImage)."
            )
            toast.run()
            toast.destroy()

    def _build_main_ui(self) -> None:
        """Assembles overview metrics banner and application cards container."""
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(main_vbox)

        # --- Overview Cards Banner ---
        overview_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        overview_card.get_style_context().add_class("card-overview")

        # Stat 1: Installed Apps
        stat1_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_s1_title = Gtk.Label(label="INSTALLED APPLICATIONS")
        lbl_s1_title.get_style_context().add_class("stat-label")
        lbl_s1_title.set_xalign(0)

        self.lbl_stat_count = Gtk.Label(label="0")
        self.lbl_stat_count.get_style_context().add_class("stat-value")
        self.lbl_stat_count.set_xalign(0)

        stat1_box.pack_start(lbl_s1_title, False, False, 0)
        stat1_box.pack_start(self.lbl_stat_count, False, False, 0)

        # Stat 2: Total Disk Storage
        stat2_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_s2_title = Gtk.Label(label="MANAGED STORAGE")
        lbl_s2_title.get_style_context().add_class("stat-label")
        lbl_s2_title.set_xalign(0)

        self.lbl_stat_size = Gtk.Label(label="0 MB")
        self.lbl_stat_size.get_style_context().add_class("stat-value")
        self.lbl_stat_size.set_xalign(0)

        stat2_box.pack_start(lbl_s2_title, False, False, 0)
        stat2_box.pack_start(self.lbl_stat_size, False, False, 0)

        # Stat 3: Target Directory
        stat3_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_s3_title = Gtk.Label(label="DEPLOYMENT LOCATION")
        lbl_s3_title.get_style_context().add_class("stat-label")
        lbl_s3_title.set_xalign(0)

        lbl_s3_val = Gtk.Label(label=self.env["opt_dir"])
        lbl_s3_val.get_style_context().add_class("stat-value")
        lbl_s3_val.set_xalign(0)

        stat3_box.pack_start(lbl_s3_title, False, False, 0)
        stat3_box.pack_start(lbl_s3_val, False, False, 0)

        overview_card.pack_start(stat1_box, True, True, 0)
        overview_card.pack_start(stat2_box, True, True, 0)
        overview_card.pack_start(stat3_box, True, True, 0)

        main_vbox.pack_start(overview_card, False, False, 0)

        # --- Search Bar ---
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search installed applications...")
        self.search_entry.get_style_context().add_class("search-entry")
        self.search_entry.connect("search-changed", lambda w: self.refresh_apps_list())
        main_vbox.pack_start(self.search_entry, False, False, 0)

        # --- Scrollable Application List ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_vbox.pack_start(scrolled, True, True, 0)

        self.apps_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.add(self.apps_vbox)

        self.refresh_apps_list()

    def refresh_apps_list(self) -> None:
        """Queries installed apps and re-populates the list rows."""
        # Clear existing children
        for child in self.apps_vbox.get_children():
            self.apps_vbox.remove(child)

        apps = get_installed_apps()
        self.lbl_stat_count.set_text(str(len(apps)))

        total_mb = sum(a["size_mb"] for a in apps)
        if total_mb > 1024:
            self.lbl_stat_size.set_text(f"{round(total_mb / 1024, 2)} GB")
        else:
            self.lbl_stat_size.set_text(f"{total_mb} MB")

        # Filter by search entry text if typed
        query = self.search_entry.get_text().strip().lower() if hasattr(self, "search_entry") else ""
        if query:
            apps = [a for a in apps if query in a["display_name"].lower() or query in a["app_id"].lower()]

        if not apps:
            self._render_empty_state()
            return

        for app in apps:
            card_row = self._create_app_card_row(app)
            self.apps_vbox.pack_start(card_row, False, False, 0)

        self.apps_vbox.show_all()

    def _render_empty_state(self) -> None:
        """Displays friendly placeholder when no applications are installed."""
        empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty_box.set_valign(Gtk.Align.CENTER)
        empty_box.set_margin_top(48)
        empty_box.set_margin_bottom(48)

        img_empty = Gtk.Image.new_from_icon_name("system-software-install", Gtk.IconSize.DIALOG)
        img_empty.set_pixel_size(64)

        lbl_title = Gtk.Label(label="No Managed Applications Found")
        lbl_title.get_style_context().add_class("empty-title")

        lbl_desc = Gtk.Label(
            label="Drag and drop compressed archive packages (.tar.gz, .zip) or click below to install."
        )
        lbl_desc.get_style_context().add_class("empty-desc")

        btn_install = Gtk.Button(label="Install Application Package")
        btn_install.get_style_context().add_class("btn-primary")
        btn_install.set_halign(Gtk.Align.CENTER)
        btn_install.connect("clicked", self._on_install_clicked)

        empty_box.pack_start(img_empty, False, False, 0)
        empty_box.pack_start(lbl_title, False, False, 0)
        empty_box.pack_start(lbl_desc, False, False, 0)
        empty_box.pack_start(btn_install, False, False, 6)

        self.apps_vbox.pack_start(empty_box, True, True, 0)
        self.apps_vbox.show_all()

    def _create_app_card_row(self, app: dict) -> Gtk.Widget:
        """Constructs row card widget for single installed application."""
        card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        card_box.get_style_context().add_class("app-card")

        # Icon widget
        icon_path = app["icon_path"]
        if icon_path and os.path.isfile(icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    icon_path, 48, 48, True
                )
                img_icon = Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                img_icon = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DND)
                img_icon.set_pixel_size(48)
        else:
            img_icon = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DND)
            img_icon.set_pixel_size(48)

        card_box.pack_start(img_icon, False, False, 0)

        # Meta Text Box
        meta_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        meta_vbox.set_valign(Gtk.Align.CENTER)

        lbl_name = Gtk.Label(label=app["display_name"])
        lbl_name.get_style_context().add_class("app-title")
        lbl_name.set_xalign(0)

        lbl_path = Gtk.Label(label=app["path"])
        lbl_path.get_style_context().add_class("app-subtitle")
        lbl_path.set_xalign(0)

        meta_vbox.pack_start(lbl_name, False, False, 0)
        meta_vbox.pack_start(lbl_path, False, False, 0)

        card_box.pack_start(meta_vbox, True, True, 0)

        # Size badge
        lbl_size = Gtk.Label(label=f"{app['size_mb']} MB")
        lbl_size.get_style_context().add_class("badge-size")
        lbl_size.set_valign(Gtk.Align.CENTER)
        card_box.pack_start(lbl_size, False, False, 8)

        # Action Buttons Box
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions_box.set_valign(Gtk.Align.CENTER)

        # Launch Button
        btn_launch = Gtk.Button(label="🚀 Launch")
        btn_launch.get_style_context().add_class("btn-launch")
        btn_launch.connect("clicked", lambda w, a=app: self._on_launch_app(a))

        # Uninstall Button
        btn_uninstall = Gtk.Button(label="🗑 Uninstall")
        btn_uninstall.get_style_context().add_class("btn-uninstall")
        btn_uninstall.connect("clicked", lambda w, a=app: self._on_uninstall_app(a))

        actions_box.pack_start(btn_launch, False, False, 0)
        actions_box.pack_start(btn_uninstall, False, False, 0)

        card_box.pack_start(actions_box, False, False, 0)

        return card_box

    def _on_launch_app(self, app: dict) -> None:
        """Launches application executable using desktop entry Exec command or DirectoryScanner."""
        app_id = app.get("app_id")
        opt_path = app.get("path")
        exec_cmd = app.get("exec_cmd")

        # 1. Check desktop file Exec command line
        if not exec_cmd and app_id:
            desktop_path = os.path.expanduser(f"~/.local/share/applications/{app_id}.desktop")
            if os.path.isfile(desktop_path):
                try:
                    with open(desktop_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("Exec="):
                                exec_cmd = line.strip().split("=", 1)[1]
                                break
                except Exception:
                    pass

        if exec_cmd:
            clean_cmd = (
                exec_cmd.replace("%F", "")
                .replace("%f", "")
                .replace("%U", "")
                .replace("%u", "")
                .strip()
            )
            try:
                subprocess.Popen(clean_cmd, shell=True)
                logger.info(f"Launched application via Exec string: {clean_cmd}")
                return
            except Exception as e:
                logger.error(f"Failed to launch app via Exec: {e}")

        # 2. Fallback using DirectoryScanner with score heuristics
        if opt_path and os.path.isdir(opt_path):
            from applaunch.core.scanner import DirectoryScanner
            display_name = app.get("display_name", "")
            scanner = DirectoryScanner(root_dir=opt_path, app_search_slug=display_name)
            candidates = scanner.find_entry_points()
            if candidates:
                cand_path = candidates[0].full_path
                # Check for Electron --no-sandbox flag
                app_dir = os.path.dirname(cand_path)
                sandbox_path = os.path.join(app_dir, "chrome-sandbox")
                cmd_run = f'"{cand_path}" --no-sandbox' if os.path.isfile(sandbox_path) else f'"{cand_path}"'
                subprocess.Popen(cmd_run, shell=True)
                logger.info(f"Launched scanned candidate binary: {cmd_run}")
                return

        logger.warning(f"Could not find valid executable launcher for app: {app}")

    def _on_uninstall_app(self, app: dict) -> None:
        """Presents GTK confirmation dialog and uninstalls application."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Uninstall {app['display_name']}?",
        )
        dialog.format_secondary_text(
            f"This action will permanently delete:\n• Directory: {app['path']}\n• Desktop shortcuts & menu icons.\n\nAre you sure you want to proceed?"
        )

        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            success = uninstall_app_backend(app["app_id"])
            if success:
                self.refresh_apps_list()
                toast = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Application Uninstalled",
                )
                toast.format_secondary_text(f"Successfully uninstalled '{app['display_name']}'.")
                toast.run()
                toast.destroy()

    def _on_install_clicked(self, widget: Gtk.Widget) -> None:
        """Opens GTK FileChooserDialog to select an application archive."""
        chooser = Gtk.FileChooserDialog(
            title="Select Application Archive Package",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT
        )

        # File Filter
        filter_archives = Gtk.FileFilter()
        filter_archives.set_name("Application Archives (*.tar.gz, *.tgz, *.zip, *.7z, *.tar.xz)")
        filter_archives.add_mime_type("application/x-compressed-tar")
        filter_archives.add_mime_type("application/x-gzip")
        filter_archives.add_mime_type("application/zip")
        filter_archives.add_mime_type("application/x-tar")
        filter_archives.add_mime_type("application/x-xz")
        filter_archives.add_mime_type("application/x-7z-compressed")
        filter_archives.add_pattern("*.tar.gz")
        filter_archives.add_pattern("*.tgz")
        filter_archives.add_pattern("*.zip")
        filter_archives.add_pattern("*.tar.xz")
        filter_archives.add_pattern("*.7z")
        chooser.add_filter(filter_archives)

        response = chooser.run()
        selected_file = chooser.get_filename()
        chooser.destroy()

        if response == Gtk.ResponseType.ACCEPT and selected_file:
            self._trigger_installation_flow(selected_file)

    def _trigger_installation_flow(self, archive_path: str) -> None:
        """Executes installation pipeline inside background thread with GTK Progress Dialog."""
        temp_engine = AppInstallerEngine(archive_path=archive_path, force_cli=True)
        if os.path.exists(temp_engine.dest_dir):
            app_title = temp_engine.name_info["display_name"]
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.NONE,
                text=f"'{app_title}' is Already Installed!",
            )
            dialog.format_secondary_text(
                f"Installed Location: {temp_engine.dest_dir}\n"
                f"Package Archive: {os.path.basename(archive_path)}\n\n"
                f"What would you like to do?"
            )
            dialog.add_button("🚀 Launch Existing App", 101)
            dialog.add_button("🔄 Reinstall / Upgrade", 102)
            dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)

            res = dialog.run()
            dialog.destroy()

            if res == 101:
                # Launch existing app with full app_id metadata
                self._on_launch_app({
                    "app_id": temp_engine.name_info["app_id"],
                    "path": temp_engine.dest_dir,
                    "display_name": app_title,
                })
                return
            elif res != 102:
                # Cancelled by user
                return

        progress_dialog = Gtk.Dialog(
            title="AppLaunch Smart Installer",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        progress_dialog.set_default_size(450, 160)

        vbox = progress_dialog.get_content_area()
        vbox.set_spacing(12)
        vbox.set_border_width(16)

        lbl_status = Gtk.Label(label=f"Installing {os.path.basename(archive_path)}...")
        lbl_status.set_xalign(0)
        pbar = Gtk.ProgressBar()
        pbar.set_fraction(0.05)
        pbar.set_show_text(True)
        pbar.set_text("Starting installation engine...")

        vbox.pack_start(lbl_status, False, False, 0)
        vbox.pack_start(pbar, False, False, 0)
        progress_dialog.show_all()

        def update_ui(pct: float, text: str) -> None:
            pbar.set_fraction(pct)
            pbar.set_text(text)

        def worker() -> None:
            try:
                engine = AppInstallerEngine(archive_path=archive_path, force_cli=True)

                GLib.idle_add(update_ui, 0.2, "Extracting application archive...")
                metrics = engine.run_installation(auto_confirm=True)

                if metrics.get("status") == "SUCCESS":
                    GLib.idle_add(update_ui, 1.0, "Installation complete!")
                    GLib.idle_add(progress_dialog.destroy)
                    GLib.idle_add(self.refresh_apps_list)
                    GLib.idle_add(self._show_success_dialog, archive_path)
                else:
                    err_msg = metrics.get("error_msg", "Unknown error")
                    GLib.idle_add(progress_dialog.destroy)
                    GLib.idle_add(self._show_error_dialog, err_msg)
            except Exception as e:
                GLib.idle_add(progress_dialog.destroy)
                GLib.idle_add(self._show_error_dialog, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _show_success_dialog(self, archive_path: str) -> None:
        """Displays completion success dialog with macOS-style Move to Trash prompt."""
        config = load_config()
        archive_name = os.path.basename(archive_path)

        # Check if auto-trash setting is enabled
        if config.get("auto_trash_installer"):
            move_to_trash(archive_path)
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Installation Successful!",
            )
            dialog.format_secondary_text(
                f"Successfully installed '{archive_name}'.\n\n"
                f"🗑 Installer archive was automatically moved to Trash to save disk space."
            )
            dialog.run()
            dialog.destroy()
            return

        # Otherwise show macOS-style interactive Trash prompt
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Installation Successful! Move to Trash?",
        )
        size_mb = 0
        if os.path.isfile(archive_path):
            size_mb = round(os.path.getsize(archive_path) / (1024 * 1024), 1)

        dialog.format_secondary_text(
            f"Successfully installed '{archive_name}'.\n\n"
            f"Package File: {archive_name} ({size_mb} MB)\n"
            f"Do you want to move the installer archive to Trash to save space?"
        )

        # Checkbox for Auto-Trash setting
        content_area = dialog.get_message_area()
        chk_auto = Gtk.CheckButton(label="Always move installer archives to Trash automatically")
        chk_auto.set_margin_top(8)
        content_area.pack_start(chk_auto, False, False, 0)
        content_area.show_all()

        dialog.add_button("🗑 Move to Trash", 101)
        dialog.add_button("Keep File", 102)

        res = dialog.run()
        if chk_auto.get_active():
            config["auto_trash_installer"] = True
            save_config(config)

        dialog.destroy()

        if res == 101:
            success = move_to_trash(archive_path)
            if success:
                toast = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Moved to Trash",
                )
                toast.format_secondary_text(f"Moved '{archive_name}' to system Trash.")
                toast.run()
                toast.destroy()

    def _show_error_dialog(self, err_msg: str) -> None:
        """Displays error toast."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Installation Failed",
        )
        dialog.format_secondary_text(f"Error details:\n{err_msg}")
        dialog.run()
        dialog.destroy()

    def _on_settings_clicked(self) -> None:
        """Displays Preferences modal dialog."""
        config = load_config()
        dialog = Gtk.Dialog(
            title="Rapid Installer Preferences",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(480, 220)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        box = dialog.get_content_area()
        box.set_spacing(16)
        box.set_border_width(20)

        lbl_title = Gtk.Label(label="<b>Installer Preferences</b>")
        lbl_title.set_use_markup(True)
        lbl_title.set_xalign(0)
        box.pack_start(lbl_title, False, False, 0)

        chk_auto = Gtk.CheckButton(label="Automatically move installer archives (.tar.gz, .deb) to Trash after installation")
        chk_auto.set_active(config.get("auto_trash_installer", False))
        box.pack_start(chk_auto, False, False, 0)

        chk_default = Gtk.CheckButton(label="Set Rapid Installer as default Linux package handler")
        chk_default.set_active(is_default_installer())
        box.pack_start(chk_default, False, False, 0)

        box.show_all()
        dialog.run()

        config["auto_trash_installer"] = chk_auto.get_active()
        save_config(config)

        if chk_default.get_active() and not is_default_installer():
            set_as_default_installer()
            self._update_default_installer_widget()

        dialog.destroy()


def launch_gtk_manager(archive_path: Optional[str] = None) -> int:
    """Entry point routine to initialize GTK Application Manager loop."""
    app = AppLaunchManagerWindow(initial_archive=archive_path)
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    archive = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(launch_gtk_manager(archive))
