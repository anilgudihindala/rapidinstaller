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
    export_backup_manifest,
    get_environment_info,
    get_installed_apps,
    is_default_installer,
    load_config,
    move_to_trash,
    refresh_desktop_database,
    run_health_diagnostics_and_repair,
    save_config,
    set_as_default_installer,
)

# Custom GTK CSS Design System - macOS Sequoia Refined Edition
CSS_THEME = """
window {
    background-color: #0b0f17;
    color: #f1f5f9;
    font-family: 'Inter', '-apple-system', 'SF Pro Text', 'Ubuntu', sans-serif;
}

headerbar {
    background: linear-gradient(180deg, #1c2638 0%, #0f172a 100%);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 6px 14px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}

.title-header {
    font-size: 15px;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: -0.2px;
}

.subtitle-header {
    font-size: 11px;
    color: #38bdf8;
    font-weight: 600;
}

.card-overview {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.85) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 10px 18px;
    margin: 10px 20px 8px 20px;
}

.stat-label {
    font-size: 10px;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 0.5px;
}

.stat-value {
    font-size: 14px;
    font-weight: 700;
    color: #38bdf8;
}

.app-card {
    background: linear-gradient(145deg, #141c2b 0%, #0f172a 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    margin: 4px 20px;
    padding: 10px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    transition: all 150ms ease-in-out;
}

.app-card:hover {
    background: linear-gradient(145deg, #1b263a 0%, #141c2b 100%);
    border-color: rgba(56, 189, 248, 0.35);
    box-shadow: 0 4px 14px rgba(56, 189, 248, 0.12);
}

.app-title {
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.1px;
}

.app-subtitle {
    font-size: 11px;
    color: #94a3b8;
    font-weight: 500;
}

.badge-size {
    background: rgba(2, 132, 199, 0.2);
    border: 1px solid rgba(56, 189, 248, 0.3);
    color: #38bdf8;
    font-size: 11px;
    font-weight: 700;
    border-radius: 14px;
    padding: 3px 10px;
}

.btn-primary {
    background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 6px 14px;
    box-shadow: 0 2px 8px rgba(2, 132, 199, 0.3);
}

.btn-primary:hover {
    background: linear-gradient(135deg, #38bdf8 0%, #0284c7 100%);
}

.btn-default-installer {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 5px 12px;
    margin-left: 6px;
}

.btn-default-installer:hover {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.badge-default-active {
    background: rgba(6, 95, 70, 0.5);
    border: 1px solid rgba(52, 211, 153, 0.3);
    color: #34d399;
    font-size: 11px;
    font-weight: 700;
    border-radius: 14px;
    padding: 4px 10px;
    margin-left: 6px;
}

.btn-launch {
    background: linear-gradient(135deg, #059669 0%, #10b981 100%);
    color: #ffffff;
    font-weight: 700;
    border-radius: 7px;
    border: none;
    padding: 6px 14px;
}

.btn-launch:hover {
    background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
}

.btn-uninstall {
    background: rgba(239, 68, 68, 0.08);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.25);
    font-weight: 600;
    border-radius: 7px;
    padding: 5px 12px;
}

.btn-uninstall:hover {
    background-color: #ef4444;
    color: #ffffff;
}

.search-entry {
    margin: 4px 20px 8px 20px;
    background-color: #141c2b;
    color: #f8fafc;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px 12px;
}

.search-entry:focus {
    border-color: #38bdf8;
}

.empty-card {
    background: linear-gradient(145deg, #141c2b 0%, #0f172a 100%);
    border: 2px dashed rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    margin: 20px;
    padding: 40px 24px;
}

.empty-title {
    font-size: 18px;
    font-weight: 700;
    color: #f8fafc;
}

.empty-desc {
    font-size: 13px;
    color: #94a3b8;
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

        self.selected_app_ids = set()

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

        # Install Package Button
        btn_install = Gtk.Button(label="+ Install Package...")
        btn_install.get_style_context().add_class("btn-primary")
        btn_install.connect("clicked", self._on_install_clicked)
        header.pack_end(btn_install)

        # Discover & Adopt External Applications Button
        btn_discover = Gtk.Button()
        img_discover = Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON)
        btn_discover.set_image(img_discover)
        btn_discover.set_tooltip_text("Discover & Adopt Unmanaged System Applications")
        btn_discover.connect("clicked", lambda w: self._on_discover_apps_clicked())
        header.pack_end(btn_discover)

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

    def _on_discover_apps_clicked(self) -> None:
        """Scans environment for unmanaged external apps and displays Adoption GTK modal."""
        from applaunch.core.discovery import ExistingAppDiscoverer
        unmanaged = ExistingAppDiscoverer.scan_unmanaged_applications()

        dialog = Gtk.Dialog(
            title=f"Discovered External Applications ({len(unmanaged)})",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(620, 440)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_border_width(16)

        lbl = Gtk.Label(label="<b>Discovered Unmanaged Applications</b>")
        lbl.set_use_markup(True)
        lbl.set_xalign(0)
        box.pack_start(lbl, False, False, 0)

        lbl_sub = Gtk.Label(label="These applications were installed via other means (Snap, DPKG, Flatpak). Click 'Adopt' to manage them in Rapid Installer.")
        lbl_sub.set_xalign(0)
        box.pack_start(lbl_sub, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(scrolled, True, True, 0)

        vbox_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.add(vbox_list)

        for app in unmanaged:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.get_style_context().add_class("app-card")

            meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            meta_box.set_valign(Gtk.Align.CENTER)

            lbl_name = Gtk.Label(label=app["display_name"])
            lbl_name.get_style_context().add_class("app-title")
            lbl_name.set_xalign(0)

            exec_preview = app['exec_cmd'][:50] + ("..." if len(app['exec_cmd']) > 50 else "")
            lbl_source = Gtk.Label(label=f"Source: {app['source']} | Exec: {exec_preview}")
            lbl_source.get_style_context().add_class("app-subtitle")
            lbl_source.set_xalign(0)

            meta_box.pack_start(lbl_name, False, False, 0)
            meta_box.pack_start(lbl_source, False, False, 0)
            row.pack_start(meta_box, True, True, 0)

            btn_adopt = Gtk.Button(label="Adopt")
            btn_adopt.get_style_context().add_class("btn-primary")
            btn_adopt.set_valign(Gtk.Align.CENTER)
            btn_adopt.connect("clicked", lambda w, a=app, r=row: self._adopt_single_app(a, r, vbox_list))
            row.pack_start(btn_adopt, False, False, 0)

            vbox_list.pack_start(row, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _adopt_single_app(self, app: dict, row_widget: Gtk.Widget, list_container: Gtk.Container) -> None:
        """Adopts single application and updates GTK list."""
        from applaunch.core.discovery import ExistingAppDiscoverer
        if ExistingAppDiscoverer.adopt_application(app):
            list_container.remove(row_widget)
            self.refresh_apps_list()
            toast = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Application Adopted!",
            )
            toast.format_secondary_text(f"Successfully adopted '{app['display_name']}' into Rapid Installer!")
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

        lbl_s3_val = Gtk.Label(label="~/.local/opt")
        lbl_s3_val.get_style_context().add_class("stat-value")
        lbl_s3_val.set_xalign(0)

        stat3_box.pack_start(lbl_s3_title, False, False, 0)
        stat3_box.pack_start(lbl_s3_val, False, False, 0)

        overview_card.pack_start(stat1_box, True, True, 0)
        overview_card.pack_start(stat2_box, True, True, 0)
        overview_card.pack_start(stat3_box, True, True, 0)

        main_vbox.pack_start(overview_card, False, False, 0)

        # --- Notebook Tabs for Applications vs. Developer Toolchains ---
        self.notebook = Gtk.Notebook()
        self.notebook.set_show_border(False)
        main_vbox.pack_start(self.notebook, True, True, 0)

        # Tab 1: Desktop Applications
        tab_apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search installed applications...")
        self.search_entry.get_style_context().add_class("search-entry")
        self.search_entry.connect("search-changed", lambda w: self.refresh_apps_list())
        tab_apps_box.pack_start(self.search_entry, False, False, 0)

        scrolled_apps = Gtk.ScrolledWindow()
        scrolled_apps.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tab_apps_box.pack_start(scrolled_apps, True, True, 0)

        self.apps_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled_apps.add(self.apps_vbox)

        lbl_tab1 = Gtk.Label(label="Desktop Applications")
        self.notebook.append_page(tab_apps_box, lbl_tab1)

        # Tab 2: Developer Toolchains & Runtimes
        tab_tools_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        scrolled_tools = Gtk.ScrolledWindow()
        scrolled_tools.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tab_tools_box.pack_start(scrolled_tools, True, True, 0)

        self.toolchains_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled_tools.add(self.toolchains_vbox)

        lbl_tab2 = Gtk.Label(label="Developer Runtimes (nvm, bun, rustup...)")
        self.notebook.append_page(tab_tools_box, lbl_tab2)

        # --- Drag & Drop Footer Bar ---
        drop_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        drop_bar.get_style_context().add_class("drop-banner")

        img_drop = Gtk.Image.new_from_icon_name("emblem-downloads-symbolic", Gtk.IconSize.MENU)
        lbl_drop = Gtk.Label(label="Drag & drop package archives (.tar.gz, .deb, .zip, .AppImage) anywhere into window to install")
        lbl_drop.get_style_context().add_class("drop-banner-text")

        drop_bar.pack_start(img_drop, False, False, 8)
        drop_bar.pack_start(lbl_drop, False, False, 0)
        main_vbox.pack_end(drop_bar, False, False, 0)

        # --- Batch Selection Action Bar ---
        self.batch_action_bar = Gtk.ActionBar()
        self.batch_action_bar.get_style_context().add_class("batch-action-bar")

        self.lbl_batch_count = Gtk.Label(label="0 Selected Applications")
        self.lbl_batch_count.get_style_context().add_class("batch-count-label")

        btn_batch_uninstall = Gtk.Button(label="Remove Selected Apps")
        btn_batch_uninstall.get_style_context().add_class("btn-uninstall")
        btn_batch_uninstall.connect("clicked", lambda w: self._on_batch_uninstall_clicked())

        btn_batch_cancel = Gtk.Button(label="Clear Selection")
        btn_batch_cancel.connect("clicked", lambda w: self._clear_selection())

        self.batch_action_bar.pack_start(self.lbl_batch_count)
        self.batch_action_bar.pack_end(btn_batch_uninstall)
        self.batch_action_bar.pack_end(btn_batch_cancel)

        main_vbox.pack_end(self.batch_action_bar, False, False, 0)
        self.batch_action_bar.set_visible(False)

        self.refresh_apps_list()
        self.refresh_toolchains_list()

    def refresh_toolchains_list(self) -> None:
        """Queries developer toolchains and populates GTK card list."""
        from applaunch.core.toolchains import ToolchainManager
        for c in self.toolchains_vbox.get_children():
            self.toolchains_vbox.remove(c)

        toolchains = ToolchainManager.list_all_toolchains()
        for tool in toolchains:
            row = self._create_toolchain_card_row(tool)
            self.toolchains_vbox.pack_start(row, False, False, 0)

        self.toolchains_vbox.show_all()

    def _create_toolchain_card_row(self, tool: dict) -> Gtk.Widget:
        """Constructs card row for single developer toolchain."""
        card_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        card_box.get_style_context().add_class("app-card")

        img_icon = Gtk.Image.new_from_icon_name("utilities-terminal-symbolic", Gtk.IconSize.DND)
        img_icon.set_pixel_size(44)
        card_box.pack_start(img_icon, False, False, 0)

        meta_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        meta_vbox.set_valign(Gtk.Align.CENTER)

        lbl_name = Gtk.Label(label=tool["display_name"])
        lbl_name.get_style_context().add_class("app-title")
        lbl_name.set_xalign(0)

        lbl_desc = Gtk.Label(label=f"{tool['category']} — {tool['description']}")
        lbl_desc.get_style_context().add_class("app-subtitle")
        lbl_desc.set_xalign(0)

        meta_vbox.pack_start(lbl_name, False, False, 0)
        meta_vbox.pack_start(lbl_desc, False, False, 0)
        card_box.pack_start(meta_vbox, True, True, 0)

        # Status badge
        badge = Gtk.Label(label=f"✓ {tool['version']}" if tool["installed"] else "Not Installed")
        badge.get_style_context().add_class("badge-size" if tool["installed"] else "badge-default-active")
        badge.set_valign(Gtk.Align.CENTER)
        card_box.pack_start(badge, False, False, 8)

        # Actions
        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions_box.set_valign(Gtk.Align.CENTER)

        if tool["installed"]:
            if tool["id"] in ("nvm", "pyenv"):
                btn_switch = Gtk.Button()
                box_sw = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                img_sw = Gtk.Image.new_from_icon_name("media-playlist-repeat-symbolic", Gtk.IconSize.BUTTON)
                lbl_sw = Gtk.Label(label="Switch Version")
                box_sw.pack_start(img_sw, False, False, 0)
                box_sw.pack_start(lbl_sw, False, False, 0)
                btn_switch.add(box_sw)
                btn_switch.get_style_context().add_class("btn-launch")
                btn_switch.connect("clicked", lambda w, t=tool: self._on_switch_toolchain_version(t))
                actions_box.pack_start(btn_switch, False, False, 0)

            btn_remove = Gtk.Button()
            box_rm = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            img_rm = Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
            lbl_rm = Gtk.Label(label="Remove")
            box_rm.pack_start(img_rm, False, False, 0)
            box_rm.pack_start(lbl_rm, False, False, 0)
            btn_remove.add(box_rm)
            btn_remove.get_style_context().add_class("btn-uninstall")
            btn_remove.connect("clicked", lambda w, t=tool: self._on_remove_toolchain(t))
            actions_box.pack_start(btn_remove, False, False, 0)
        else:
            btn_inst = Gtk.Button()
            box_in = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            img_in = Gtk.Image.new_from_icon_name("system-software-install-symbolic", Gtk.IconSize.BUTTON)
            lbl_in = Gtk.Label(label="Install")
            box_in.pack_start(img_in, False, False, 0)
            box_in.pack_start(lbl_in, False, False, 0)
            btn_inst.add(box_in)
            btn_inst.get_style_context().add_class("btn-primary")
            btn_inst.connect("clicked", lambda w, t=tool: self._on_install_toolchain(t))
            actions_box.pack_start(btn_inst, False, False, 0)

        card_box.pack_start(actions_box, False, False, 0)
        return card_box

    def _on_switch_toolchain_version(self, tool: dict) -> None:
        """Displays GTK Modal to select and switch active runtime version."""
        from applaunch.core.toolchains import ToolchainManager
        versions = ToolchainManager.get_toolchain_versions(tool["id"])

        dialog = Gtk.Dialog(
            title=f"Switch Version - {tool['display_name']}",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(440, 200)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)

        box = dialog.get_content_area()
        box.set_spacing(12)
        box.set_border_width(16)

        lbl = Gtk.Label(label=f"<b>Select Active Version for {tool['display_name']}</b>")
        lbl.set_use_markup(True)
        lbl.set_xalign(0)
        box.pack_start(lbl, False, False, 0)

        combo = Gtk.ComboBoxText()
        for v in versions:
            combo.append_text(v)
        combo.set_active(0)
        box.pack_start(combo, False, False, 0)

        btn_apply = Gtk.Button(label="Set Active Version")
        btn_apply.get_style_context().add_class("btn-primary")
        box.pack_start(btn_apply, False, False, 6)

        def apply_ver(w):
            selected = combo.get_active_text()
            dialog.destroy()
            if selected:
                def worker():
                    ToolchainManager.switch_toolchain_version(tool["id"], selected)
                    GLib.idle_add(self.refresh_toolchains_list)
                    GLib.idle_add(self._show_toolchain_toast, f"Switched {tool['display_name']} active version to '{selected}'.")
                threading.Thread(target=worker, daemon=True).start()

        btn_apply.connect("clicked", apply_ver)
        dialog.show_all()
        dialog.run()

    def _on_install_toolchain(self, tool: dict) -> None:
        """Triggers background installation for toolchain."""
        progress_dialog = Gtk.Dialog(
            title=f"Installing {tool['display_name']}",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        progress_dialog.set_default_size(450, 150)
        vbox = progress_dialog.get_content_area()
        vbox.set_spacing(12)
        vbox.set_border_width(16)

        lbl = Gtk.Label(label=f"Installing {tool['display_name']} environment...")
        lbl.set_xalign(0)
        pbar = Gtk.ProgressBar()
        pbar.set_fraction(0.1)
        pbar.set_show_text(True)
        pbar.set_text("Executing official installer pipeline...")
        vbox.pack_start(lbl, False, False, 0)
        vbox.pack_start(pbar, False, False, 0)
        progress_dialog.show_all()

        def worker():
            from applaunch.core.toolchains import ToolchainManager
            res = ToolchainManager.install_toolchain(tool["id"])
            GLib.idle_add(progress_dialog.destroy)
            if res.get("status") == "SUCCESS":
                GLib.idle_add(self.refresh_toolchains_list)
                GLib.idle_add(self._show_toolchain_toast, f"Successfully installed {tool['display_name']} ({res.get('version')}).")
            else:
                GLib.idle_add(self._show_error_dialog, res.get("msg", "Error installing toolchain"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_remove_toolchain(self, tool: dict) -> None:
        """Uninstalls toolchain and strips shell environment profile blocks."""
        from applaunch.core.toolchains import ToolchainManager
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Remove {tool['display_name']}?",
        )
        dialog.format_secondary_text(
            f"This will remove {tool['display_name']} files and clean environment entries from ~/.bashrc and ~/.zshrc."
        )
        if dialog.run() == Gtk.ResponseType.OK:
            dialog.destroy()
            ToolchainManager.uninstall_toolchain(tool["id"])
            self.refresh_toolchains_list()
            self._show_toolchain_toast(f"Removed {tool['display_name']} and cleaned shell profiles.")
        else:
            dialog.destroy()

    def _show_toolchain_toast(self, msg: str) -> None:
        toast = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Toolchain Configured!",
        )
        toast.format_secondary_text(
            f"{msg}\n\n"
            f"💡 Terminal Notice: Run 'source ~/.bashrc' (or 'source ~/.zshrc') or open a new terminal window to apply changes."
        )
        toast.run()
        toast.destroy()

    def _clear_selection(self) -> None:
        """Clears selected app checkboxes and hides action bar."""
        self.selected_app_ids.clear()
        self.batch_action_bar.set_visible(False)
        self.refresh_apps_list()

    def _on_card_checkbox_toggled(self, app_id: str, active: bool) -> None:
        """Tracks selected app IDs for batch uninstall."""
        if active:
            self.selected_app_ids.add(app_id)
        else:
            self.selected_app_ids.discard(app_id)

        count = len(self.selected_app_ids)
        if count >= 1:
            plural = "s" if count > 1 else ""
            self.lbl_batch_count.set_text(f"{count} Selected Application{plural}")
            self.batch_action_bar.set_visible(True)
        else:
            self.batch_action_bar.set_visible(False)

    def _on_batch_uninstall_clicked(self) -> None:
        """Executes sequential batch uninstallation of selected applications."""
        if not self.selected_app_ids:
            return

        app_list = list(self.selected_app_ids)
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Batch Uninstall {len(app_list)} Applications?",
        )

        res_text = "The following applications will be removed:\n"
        for aid in app_list:
            res_text += f"• {aid}\n"

        dialog.format_secondary_text(res_text + "\nAre you sure you want to proceed?")

        content_area = dialog.get_message_area()
        chk_purge = Gtk.CheckButton(label="Deep Clean: Also purge residual config & cache folders")
        chk_purge.set_active(True)
        chk_purge.set_margin_top(8)
        content_area.pack_start(chk_purge, False, False, 0)
        content_area.show_all()

        response = dialog.run()
        purge = chk_purge.get_active()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            count = 0
            for aid in app_list:
                if uninstall_app_backend(aid, purge_residuals=purge):
                    count += 1

            self._clear_selection()
            self.refresh_apps_list()

            toast = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Batch Uninstall Complete",
            )
            toast.format_secondary_text(
                f"Successfully uninstalled {count} applications." +
                ("\nResidual config and cache files were deep cleaned." if purge else "")
            )
            toast.run()
            toast.destroy()

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

        # Checkbox is ALWAYS displayed by default on every card
        chk = Gtk.CheckButton()
        chk.set_active(app["app_id"] in self.selected_app_ids)
        chk.get_style_context().add_class("app-checkbox")
        chk.set_valign(Gtk.Align.CENTER)
        chk.set_tooltip_text("Select application")
        chk.connect("toggled", lambda w, aid=app["app_id"]: self._on_card_checkbox_toggled(aid, w.get_active()))
        card_box.pack_start(chk, False, False, 4)

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

        # Launch / Open Button with symbolic icon
        btn_launch = Gtk.Button()
        box_launch = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        img_launch = Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.BUTTON)
        lbl_launch = Gtk.Label(label="Open")
        box_launch.pack_start(img_launch, False, False, 0)
        box_launch.pack_start(lbl_launch, False, False, 0)
        btn_launch.add(box_launch)
        btn_launch.get_style_context().add_class("btn-launch")
        btn_launch.connect("clicked", lambda w, a=app: self._on_launch_app(a))

        # Uninstall / Remove Button with symbolic icon
        btn_uninstall = Gtk.Button()
        box_uninstall = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        img_uninstall = Gtk.Image.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
        lbl_uninstall = Gtk.Label(label="Remove")
        box_uninstall.pack_start(img_uninstall, False, False, 0)
        box_uninstall.pack_start(lbl_uninstall, False, False, 0)
        btn_uninstall.add(box_uninstall)
        btn_uninstall.get_style_context().add_class("btn-uninstall")
        btn_uninstall.connect("clicked", lambda w, a=app: self._on_uninstall_app(a))

        # Info Inspector Button
        btn_info = Gtk.Button()
        img_info = Gtk.Image.new_from_icon_name("dialog-information-symbolic", Gtk.IconSize.BUTTON)
        btn_info.set_image(img_info)
        btn_info.set_tooltip_text("App Inspector & Details")
        btn_info.connect("clicked", lambda w, a=app: self._on_inspect_app(a))

        actions_box.pack_start(btn_info, False, False, 0)
        actions_box.pack_start(btn_launch, False, False, 0)
        actions_box.pack_start(btn_uninstall, False, False, 0)

        card_box.pack_start(actions_box, False, False, 0)

        return card_box

    def _on_inspect_app(self, app: dict) -> None:
        """Displays macOS-style App Details Inspector modal dialog."""
        dialog = Gtk.Dialog(
            title=f"App Inspector - {app['display_name']}",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(520, 320)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        box = dialog.get_content_area()
        box.set_spacing(16)
        box.set_border_width(20)

        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        icon_path = app.get("icon_path")
        if icon_path and os.path.isfile(icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 64, 64, True)
                img = Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                img = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
                img.set_pixel_size(64)
        else:
            img = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DIALOG)
            img.set_pixel_size(64)

        hdr_box.pack_start(img, False, False, 0)

        txt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        txt_box.set_valign(Gtk.Align.CENTER)

        lbl_n = Gtk.Label(label=f"<b>{app['display_name']}</b>")
        lbl_n.set_use_markup(True)
        lbl_n.set_xalign(0)

        lbl_i = Gtk.Label(label=f"App ID: {app['app_id']} | Size: {app['size_mb']} MB")
        lbl_i.set_xalign(0)

        txt_box.pack_start(lbl_n, False, False, 0)
        txt_box.pack_start(lbl_i, False, False, 0)
        hdr_box.pack_start(txt_box, True, True, 0)

        box.pack_start(hdr_box, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)

        lbl_l1 = Gtk.Label(label="Installed Path:")
        lbl_l1.set_xalign(0)
        lbl_p1 = Gtk.Label(label=app['path'])
        lbl_p1.set_xalign(0)
        grid.attach(lbl_l1, 0, 0, 1, 1)
        grid.attach(lbl_p1, 1, 0, 1, 1)

        lbl_l2 = Gtk.Label(label="CLI Executable:")
        lbl_l2.set_xalign(0)
        cli_symlink = os.path.expanduser(f"~/.local/bin/{app['app_id']}")
        lbl_p2 = Gtk.Label(label=cli_symlink if os.path.exists(cli_symlink) else app.get('exec_cmd', 'Auto-detected'))
        lbl_p2.set_xalign(0)
        grid.attach(lbl_l2, 0, 1, 1, 1)
        grid.attach(lbl_p2, 1, 1, 1, 1)

        lbl_l3 = Gtk.Label(label="Desktop Entry:")
        lbl_l3.set_xalign(0)
        lbl_p3 = Gtk.Label(label=app.get('desktop_file', 'Registered in ~/.local/share/applications/'))
        lbl_p3.set_xalign(0)
        grid.attach(lbl_l3, 0, 2, 1, 1)
        grid.attach(lbl_p3, 1, 2, 1, 1)

        box.pack_start(grid, False, False, 0)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_folder = Gtk.Button(label="📂 Open Install Folder")
        btn_folder.connect("clicked", lambda w: subprocess.Popen(["gio", "open", app["path"]]))

        btn_box.pack_start(btn_folder, False, False, 0)
        box.pack_start(btn_box, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

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
        """Presents AppCleaner-style Deep Uninstaller GTK dialog."""
        from applaunch.utils.sys_info import get_app_residual_paths
        residuals = get_app_residual_paths(app["app_id"])

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"Uninstall {app['display_name']}?",
        )

        res_text = f"• Directory: {app['path']}\n• Desktop shortcuts & CLI symlinks.\n"
        if residuals:
            res_text += f"\nDeep Cleaner discovered {len(residuals)} residual config/cache paths:\n"
            for r in residuals:
                res_text += f"  - {r}\n"

        dialog.format_secondary_text(res_text + "\nAre you sure you want to proceed?")

        content_area = dialog.get_message_area()
        chk_purge = Gtk.CheckButton(label="Deep Clean: Also purge residual config & cache folders")
        chk_purge.set_active(True)
        chk_purge.set_margin_top(8)
        content_area.pack_start(chk_purge, False, False, 0)
        content_area.show_all()

        response = dialog.run()
        purge = chk_purge.get_active()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            success = uninstall_app_backend(app["app_id"], purge_residuals=purge)
            if success:
                self.refresh_apps_list()
                toast = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Application Uninstalled",
                )
                toast.format_secondary_text(
                    f"Successfully uninstalled '{app['display_name']}'." +
                    ("\nResidual config and cache files were deep cleaned." if purge else "")
                )
                toast.run()
                toast.destroy()

    def _on_install_clicked(self, widget: Gtk.Widget) -> None:
        """Opens GTK FileChooserDialog with multi-select support to select application archives."""
        chooser = Gtk.FileChooserDialog(
            title="Select Application Archive Package(s)",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.set_select_multiple(True)
        chooser.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT
        )

        # File Filter
        filter_archives = Gtk.FileFilter()
        filter_archives.set_name("Application Packages (*.tar.gz, *.tgz, *.zip, *.deb, *.rpm, *.7z, *.AppImage)")
        filter_archives.add_mime_type("application/x-compressed-tar")
        filter_archives.add_mime_type("application/x-gzip")
        filter_archives.add_mime_type("application/zip")
        filter_archives.add_mime_type("application/x-tar")
        filter_archives.add_mime_type("application/x-xz")
        filter_archives.add_mime_type("application/x-7z-compressed")
        filter_archives.add_pattern("*.tar.gz")
        filter_archives.add_pattern("*.tgz")
        filter_archives.add_pattern("*.zip")
        filter_archives.add_pattern("*.deb")
        filter_archives.add_pattern("*.rpm")
        filter_archives.add_pattern("*.AppImage")
        filter_archives.add_pattern("*.appimage")
        filter_archives.add_pattern("*.7z")
        chooser.add_filter(filter_archives)

        response = chooser.run()
        selected_files = chooser.get_filenames()
        chooser.destroy()

        if response == Gtk.ResponseType.ACCEPT and selected_files:
            for f in selected_files:
                self._trigger_installation_flow(f)

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
            dialog.add_button("Open Existing App", 101)
            dialog.add_button("Reinstall / Upgrade", 102)
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
                f"Installer archive was automatically moved to Trash to save disk space."
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

        dialog.add_button("Move to Trash", 101)
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
            title="Rapid Installer Preferences & Tools",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.set_default_size(520, 340)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)

        box = dialog.get_content_area()
        box.set_spacing(16)
        box.set_border_width(20)

        lbl_title = Gtk.Label(label="<b>Installer Preferences & Power Tools</b>")
        lbl_title.set_use_markup(True)
        lbl_title.set_xalign(0)
        box.pack_start(lbl_title, False, False, 0)

        chk_auto = Gtk.CheckButton(label="Automatically move installer archives (.tar.gz, .deb) to Trash after installation")
        chk_auto.set_active(config.get("auto_trash_installer", False))
        box.pack_start(chk_auto, False, False, 0)

        chk_default = Gtk.CheckButton(label="Set Rapid Installer as default Linux package handler")
        chk_default.set_active(is_default_installer())
        box.pack_start(chk_default, False, False, 0)

        # Power Tools Section
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.pack_start(sep, False, False, 4)

        lbl_tools = Gtk.Label(label="<b>Power Tools</b>")
        lbl_tools.set_use_markup(True)
        lbl_tools.set_xalign(0)
        box.pack_start(lbl_tools, False, False, 0)

        btn_tools_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        btn_repair = Gtk.Button(label="🛠 Repair Shortcuts")
        btn_repair.connect("clicked", lambda w: self._on_repair_clicked())

        btn_backup = Gtk.Button(label="📥 Export Backup")
        btn_backup.connect("clicked", lambda w: self._on_export_backup_clicked())

        btn_custom = Gtk.Button(label="+ Custom App Shortcut")
        btn_custom.connect("clicked", lambda w: self._on_create_custom_shortcut_clicked())

        btn_tools_box.pack_start(btn_repair, False, False, 0)
        btn_tools_box.pack_start(btn_backup, False, False, 0)
        btn_tools_box.pack_start(btn_custom, False, False, 0)

        box.pack_start(btn_tools_box, False, False, 0)

        dialog.show_all()
        dialog.run()

        config["auto_trash_installer"] = chk_auto.get_active()
        save_config(config)

        if chk_default.get_active() and not is_default_installer():
            set_as_default_installer()

        dialog.destroy()

    def _on_repair_clicked(self) -> None:
        """Executes health diagnostics and repairs missing shortcuts or CLI symlinks."""
        diag = run_health_diagnostics_and_repair()
        toast = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Diagnostics & Repair Complete",
        )
        toast.format_secondary_text(
            f"Scanned {diag['apps_scanned']} installed applications.\n\n"
            f"• Repaired Desktop Shortcuts: {diag['repaired_shortcuts']}\n"
            f"• Repaired CLI Symlinks: {diag['repaired_symlinks']}"
        )
        toast.run()
        toast.destroy()
        self.refresh_apps_list()

    def _on_export_backup_clicked(self) -> None:
        """Exports installed applications manifest to a JSON backup file."""
        chooser = Gtk.FileChooserDialog(
            title="Export Installed Applications Backup",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.ACCEPT)
        chooser.set_current_name("rapid-installer-apps-backup.json")

        if chooser.run() == Gtk.ResponseType.ACCEPT:
            save_path = chooser.get_filename()
            chooser.destroy()
            if export_backup_manifest(save_path):
                toast = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="Backup Exported",
                )
                toast.format_secondary_text(f"Successfully saved application backup to:\n{save_path}")
                toast.run()
                toast.destroy()
        else:
            chooser.destroy()

    def _on_create_custom_shortcut_clicked(self) -> None:
        """Creates a managed application shortcut for any raw standalone executable or script."""
        chooser = Gtk.FileChooserDialog(
            title="Select Standalone Binary or Script",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.ACCEPT)
        if chooser.run() == Gtk.ResponseType.ACCEPT:
            bin_path = chooser.get_filename()
            chooser.destroy()

            # Name entry dialog
            entry_dialog = Gtk.Dialog(title="Application Display Name", transient_for=self, flags=Gtk.DialogFlags.MODAL)
            entry_dialog.add_button("OK", Gtk.ResponseType.OK)
            box = entry_dialog.get_content_area()
            box.set_spacing(10)
            box.set_border_width(14)
            lbl = Gtk.Label(label="Enter Display Name for Application:")
            entry = Gtk.Entry()
            entry.set_text(os.path.basename(bin_path).replace(".AppImage", "").replace(".sh", "").title())
            box.pack_start(lbl, False, False, 0)
            box.pack_start(entry, False, False, 0)
            entry_dialog.show_all()
            if entry_dialog.run() == Gtk.ResponseType.OK:
                disp_name = entry.get_text().strip()
                entry_dialog.destroy()
                if disp_name:
                    app_id = disp_name.lower().replace(" ", "-")
                    dest_dir = os.path.expanduser(f"~/.local/opt/{app_id}")
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_bin = os.path.join(dest_dir, os.path.basename(bin_path))
                    shutil.copy2(bin_path, dest_bin)
                    os.chmod(dest_bin, 0o755)

                    from applaunch.core.desktop import DesktopShortcutGenerator
                    gen = DesktopShortcutGenerator(app_id=app_id, display_name=disp_name, exec_path=dest_bin)
                    gen.generate_and_install()
                    self.refresh_apps_list()
            else:
                entry_dialog.destroy()
        else:
            chooser.destroy()


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
