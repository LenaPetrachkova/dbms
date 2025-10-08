from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from pathlib import Path
import tempfile

from typing import Optional

from core.database import Database, TableNotFoundError
from storage.json_backend import JsonStorageBackend


class DatabaseGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Mini DBMS - Desktop Client")
        self.root.geometry("900x600")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.database: Database | None = None
        self.db_path: str | None = None
        self.is_dirty: bool = False
        self._in_dialog: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        self._setup_style()

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        # Top controls
        controls = ttk.Frame(container)
        controls.pack(fill=tk.X)

        self._add_button(controls, "New DB", self.new_db)
        self._add_button(controls, "Open DB", self.open_db)
        self._add_button(controls, "Save DB", self.save_db)
        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=4)
        self._add_button(controls, "Create Table", self.create_table)
        self._add_button(controls, "Delete Table", self.delete_table)
        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=4)
        self._add_button(controls, "Add Row", self.add_row)
        self._add_button(controls, "Edit Row", self.edit_row)
        self._add_button(controls, "Delete Row", self.delete_row)
        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=4)
        self._add_button(controls, "Sort", self.sort_rows)

        self.info_label = ttk.Label(container, text="No database loaded")
        self.info_label.pack(fill=tk.X, pady=5)

        body = ttk.Frame(container)
        body.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(body)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        ttk.Label(left, text="Tables", style="Heading.TLabel").pack(anchor=tk.W)
        self.tables_list = tk.Listbox(
            left,
            height=20,
            width=30,
            bg="#0f172a",
            fg="#e2e8f0",
            selectbackground="#22d3ee",
            selectforeground="#0f172a",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#1f2937",
        )
        self.tables_list.pack(fill=tk.Y, expand=False, pady=(4, 0))
        self.tables_list.bind("<<ListboxSelect>>", lambda e: self.refresh_rows())

        right = ttk.Frame(body)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(right, show="headings", style="Treeview")
        yscroll = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Double-Button-1>", self._on_double_click)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Sort by column (asc)", command=lambda: self._sort_selected(False))
        self.menu.add_command(label="Sort by column (desc)", command=lambda: self._sort_selected(True))
        
        self.html_menu = tk.Menu(self.root, tearoff=0)
        self.html_menu.add_command(label="Preview HTML", command=self._preview_selected_html)
        self.html_menu.add_command(label="Export HTML", command=self._export_selected_html)

    # DB actions
    def new_db(self) -> None:
        name = simpledialog.askstring("New Database", "Database name:")
        if not name:
            return
        self.database = Database(name=name)
        self.db_path = None
        self._refresh_all()
        self.is_dirty = True

    def open_db(self) -> None:
        path = filedialog.askopenfilename(title="Open DB", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            self.database = JsonStorageBackend.load(path)
            self.db_path = path
            self._refresh_all()
            self.is_dirty = False
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    def save_db(self) -> None:
        if not self.database:
            return
        if not self.db_path:
            path = filedialog.asksaveasfilename(title="Save DB", defaultextension=".json", filetypes=[("JSON", "*.json")])
            if not path:
                return
            self.db_path = path
        try:
            JsonStorageBackend.save(self.database, self.db_path)
            messagebox.showinfo("Saved", f"Saved to {self.db_path}")
            self.is_dirty = False
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    # Table actions
    def create_table(self) -> None:
        if not self.database:
            messagebox.showwarning("No DB", "Create or open a database first")
            return
        self._in_dialog = True
        dialog = TableDialog(self.root, "Create Table")
        result = dialog.show()
        self._in_dialog = False
        if not result:
            return
        name, schema = result
        try:
            self.database.create_table(name, schema)
            self._refresh_all()
            self.is_dirty = True
        except Exception as exc:
            messagebox.showerror("Create failed", str(exc))

    def add_row(self) -> None:
        table = self._selected_table()
        if not table:
            return
        self._in_dialog = True
        dialog = RowDialog(self.root, table, title="Add Row")
        values = dialog.show()
        self._in_dialog = False
        if values is None:
            return
        try:
            table.insert(values)
            self.refresh_rows()
            self.is_dirty = True
        except Exception as exc:
            messagebox.showerror("Insert failed", str(exc))

    def edit_row(self) -> None:
        table = self._selected_table()
        row_id = self._selected_row_id()
        if not table or not row_id:
            messagebox.showwarning("Select Row", "Choose a row to edit")
            return
        current = next((row for row in table.rows if row.get("_id") == row_id), None)
        if not current:
            return
        self._in_dialog = True
        dialog = RowDialog(self.root, table, title="Edit Row", initial=current)
        new_values = dialog.show()
        self._in_dialog = False
        if new_values is None:
            return
        try:
            table.update(row_id, new_values)
            self.refresh_rows()
            self.is_dirty = True
        except Exception as exc:
            messagebox.showerror("Update failed", str(exc))

    def delete_row(self) -> None:
        table = self._selected_table()
        row_id = self._selected_row_id()
        if not table or not row_id:
            messagebox.showwarning("Select Row", "Choose a row to delete")
            return
        if messagebox.askyesno("Confirm", "Delete selected row?"):
            table.delete(row_id)
            self.refresh_rows()
            self.is_dirty = True

    def sort_rows(self) -> None:
        table = self._selected_table()
        if not table:
            return
        # Зберігаємо поточний вибір таблиці
        current_selection = self.tables_list.curselection()
        self._in_dialog = True
        dialog = SortDialog(self.root, list(table.schema.keys()))
        result = dialog.show()
        self._in_dialog = False
        if not result:
            # Відновлюємо вибір навіть якщо користувач скасував
            if current_selection:
                self.tables_list.selection_clear(0, tk.END)
                self.tables_list.selection_set(current_selection[0])
            return
        column, reverse = result
        try:
            table.sort_by(column, reverse=reverse)
            # Відновлюємо вибір таблиці перед оновленням
            if current_selection:
                self.tables_list.selection_clear(0, tk.END)
                self.tables_list.selection_set(current_selection[0])
            self.refresh_rows()
            self.is_dirty = True
        except Exception as exc:
            messagebox.showerror("Sort failed", str(exc))

    def _show_context_menu(self, event: tk.Event) -> None:
        table = self._selected_table()
        if not table:
            return
        region = self.tree.identify("region", event.x, event.y)
        column_id = self.tree.identify_column(event.x)
        index = int(column_id.strip("#")) - 1
        columns = list(table.schema.keys()) + ["_id"]
        
        if 0 <= index < len(columns):
            self._context_column = columns[index]
            if self._context_column == "_id":
                return
            
            field_type = table.schema.get(self._context_column)
            
            if region == "heading":
                self.menu.tk_popup(event.x_root, event.y_root)
            elif region == "cell" and field_type and field_type.type_name == "htmlFile":
                row_id = self.tree.identify_row(event.y)
                if row_id:
                    self.tree.selection_set(row_id)
                    self.html_menu.tk_popup(event.x_root, event.y_root)

    def _sort_selected(self, descending: bool) -> None:
        table = self._selected_table()
        column = getattr(self, "_context_column", None)
        if not table or not column:
            return
        try:
            table.sort_by(column, reverse=descending)
            self.refresh_rows()
            self.is_dirty = True
        except Exception as exc:
            messagebox.showerror("Sort failed", str(exc))

    def _on_double_click(self, event: tk.Event) -> None:
        table = self._selected_table()
        row_id = self._selected_row_id()
        if not table or not row_id:
            return
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column_id = self.tree.identify_column(event.x)
        index = int(column_id.strip("#")) - 1
        columns = list(table.schema.keys()) + ["_id"]
        if 0 <= index < len(columns):
            column = columns[index]
            field_type = table.schema.get(column)
            if field_type and field_type.type_name == "htmlFile":
                row = next((r for r in table.rows if r.get("_id") == row_id), None)
                if row:
                    self._preview_html(row.get(column, ""))

    def _preview_selected_html(self) -> None:
        table = self._selected_table()
        row_id = self._selected_row_id()
        column = getattr(self, "_context_column", None)
        if not table or not row_id or not column:
            return
        field_type = table.schema.get(column)
        if field_type and field_type.type_name == "htmlFile":
            row = next((r for r in table.rows if r.get("_id") == row_id), None)
            if row:
                self._preview_html(row.get(column, ""))

    def _export_selected_html(self) -> None:
        table = self._selected_table()
        row_id = self._selected_row_id()
        column = getattr(self, "_context_column", None)
        if not table or not row_id or not column:
            return
        field_type = table.schema.get(column)
        if field_type and field_type.type_name == "htmlFile":
            row = next((r for r in table.rows if r.get("_id") == row_id), None)
            if row:
                self._export_html(row.get(column, ""))

    def delete_table(self) -> None:
        if not self.database:
            return
        sel = self.tables_list.curselection()
        if not sel:
            return
        name = self.tables_list.get(sel[0])
        if messagebox.askyesno("Confirm", f"Delete table '{name}'?"):
            self.database.drop_table(name)
            self._refresh_all()
            self.is_dirty = True

    # Helpers
    def _selected_table(self):
        if not self.database:
            return None
        sel = self.tables_list.curselection()
        if not sel:
            return None
        name = self.tables_list.get(sel[0])
        try:
            return self.database.get_table(name)
        except TableNotFoundError:
            return None

    def refresh_rows(self) -> None:
        if self._in_dialog:
            return
        table = self._selected_table()
        for col in self.tree["columns"]:
            self.tree.heading(col, text="")
        self.tree["columns"] = ()
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not table:
            return
        columns = list(table.schema.keys()) + ["_id"]
        self.tree["columns"] = columns
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        for row in table.rows:
            display_values = []
            for c in columns:
                value = row.get(c, "")
                field_type = table.schema.get(c)
                if field_type and field_type.type_name == "htmlFile":
                    display_values.append(f"HTML ({len(value)} chars)")
                else:
                    display_values.append(value)
            self.tree.insert("", tk.END, values=display_values, iid=row.get("_id"))

    def _refresh_all(self) -> None:
        if self.database:
            self.info_label.config(text=f"Database: {self.database.name} | {len(self.database.tables)} tables")
            self.tables_list.delete(0, tk.END)
            for name in self.database.tables.keys():
                self.tables_list.insert(tk.END, name)
        else:
            self.info_label.config(text="No database loaded")
            self.tables_list.delete(0, tk.END)
        self.refresh_rows()

    def _on_close(self) -> None:
        if self.is_dirty and messagebox.askyesno("Unsaved changes", "Save changes before exit?"):
            self.save_db()
        self.root.destroy()

    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#0f172a")
        style.configure("TLabel", background="#0f172a", foreground="#e2e8f0")
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"), padding=(0, 4))
        style.configure("TButton", background="#1f2937", foreground="#e2e8f0", padding=(12, 6), relief="flat")
        style.map("TButton", background=[("active", "#22d3ee")], foreground=[("active", "#0f172a")])
        style.configure("Treeview", background="#0f172a", foreground="#e2e8f0", fieldbackground="#0f172a", borderwidth=0)
        style.configure("Treeview.Heading", background="#111827", foreground="#e2e8f0")

    def _add_button(self, parent: ttk.Frame, text: str, command) -> None:
        ttk.Button(parent, text=text, command=command).pack(side=tk.LEFT, padx=4, pady=4)

    def _selected_row_id(self) -> Optional[str]:
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0]

    def _preview_html(self, content: str) -> None:
        if not content:
            messagebox.showwarning("Preview", "No HTML content to preview")
            return
        try:
            tmp_dir = Path(tempfile.gettempdir())
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / "mini_dbms_preview.html"
            tmp_path.write_text(content, encoding="utf-8")
            import webbrowser
            webbrowser.open(tmp_path.as_uri())
        except OSError as exc:
            messagebox.showerror("Preview failed", str(exc))

    def _export_html(self, content: str) -> None:
        if not content:
            messagebox.showwarning("Export", "No HTML content to export")
            return
        file_path = filedialog.asksaveasfilename(title="Export HTML", defaultextension=".html", filetypes=[("HTML", "*.html;*.htm")])
        if file_path:
            try:
                Path(file_path).write_text(content, encoding="utf-8")
                messagebox.showinfo("Export", f"Saved to {file_path}")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc))


class TableDialog:
    TYPES = ["integer", "real", "char", "string", "htmlFile", "stringInvl"]

    def __init__(self, parent: tk.Tk, title: str):
        self.result: Optional[tuple[str, dict[str, object]]] = None
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("520x420")
        self.top.configure(bg="#0f172a")
        self.top.transient(parent)
        self.top.grab_set()

        self.name_var = tk.StringVar()
        self.field_rows: list[FieldRow] = []

        content = ttk.Frame(self.top, padding=16)
        content.pack(fill=tk.BOTH, expand=True)

        ttk.Label(content, text="Table name:").pack(anchor=tk.W)
        ttk.Entry(content, textvariable=self.name_var).pack(fill=tk.X, pady=(4, 12))

        ttk.Label(content, text="Fields:").pack(anchor=tk.W)
        fields_container = ttk.Frame(content)
        fields_container.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        self.canvas = tk.Canvas(fields_container, background="#0f172a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(fields_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.canvas_frame, anchor="nw")
        self.canvas_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        controls = ttk.Frame(content)
        controls.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(controls, text="Add field", command=self._add_field).pack(side=tk.LEFT)
        ttk.Button(controls, text="Create", command=self._submit).pack(side=tk.RIGHT)
        ttk.Button(controls, text="Cancel", command=self.top.destroy).pack(side=tk.RIGHT, padx=(8, 0))

        self._add_field()

    def _add_field(self) -> None:
        row = FieldRow(self.canvas_frame, self)
        self.field_rows.append(row)
        row.frame.pack(fill=tk.X, pady=4)

    def remove_field(self, row: "FieldRow") -> None:
        if row in self.field_rows:
            self.field_rows.remove(row)
            row.frame.destroy()

    def _submit(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Invalid", "Table name required")
            return
        schema: dict[str, object] = {}
        for row in self.field_rows:
            data = row.get_data()
            if not data:
                messagebox.showerror("Invalid", "Fill in all fields")
                return
            field_name, descriptor = data
            if field_name in schema:
                messagebox.showerror("Invalid", f"Duplicate field '{field_name}'")
                return
            schema[field_name] = descriptor
        if not schema:
            messagebox.showerror("Invalid", "Table must have at least one field")
            return
        self.result = (name, schema)
        self.top.destroy()

    def show(self) -> Optional[tuple[str, dict[str, object]]]:
        self.top.wait_window()
        return self.result


class FieldRow:
    def __init__(self, parent: ttk.Frame, dialog: TableDialog) -> None:
        self.dialog = dialog
        self.frame = ttk.Frame(parent)
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar(value=TableDialog.TYPES[0])
        self.min_var = tk.StringVar()
        self.max_var = tk.StringVar()

        ttk.Entry(self.frame, textvariable=self.name_var, width=18).pack(side=tk.LEFT, padx=(0, 6))
        type_box = ttk.Combobox(self.frame, textvariable=self.type_var, values=TableDialog.TYPES, state="readonly", width=14)
        type_box.pack(side=tk.LEFT)
        type_box.bind("<<ComboboxSelected>>", self._toggle_interval)

        self.interval_frame = ttk.Frame(self.frame)
        ttk.Label(self.interval_frame, text="min:").pack(side=tk.LEFT, padx=(6, 3))
        ttk.Entry(self.interval_frame, textvariable=self.min_var, width=8).pack(side=tk.LEFT)
        ttk.Label(self.interval_frame, text="max:").pack(side=tk.LEFT, padx=(6, 3))
        ttk.Entry(self.interval_frame, textvariable=self.max_var, width=8).pack(side=tk.LEFT)

        ttk.Button(self.frame, text="Remove", command=lambda: dialog.remove_field(self)).pack(side=tk.LEFT, padx=(6, 0))

    def _toggle_interval(self, event=None) -> None:
        if self.type_var.get() == "stringInvl":
            self.interval_frame.pack(side=tk.LEFT)
        else:
            self.interval_frame.pack_forget()

    def get_data(self) -> Optional[tuple[str, object]]:
        name = self.name_var.get().strip()
        if not name:
            return None
        type_name = self.type_var.get()
        if type_name == "stringInvl":
            return name, {
                "type": "stringInvl",
                "config": {
                    "base_type": {"type": "string", "config": {}},
                    "min_value": self.min_var.get() or None,
                    "max_value": self.max_var.get() or None,
                },
            }
        return name, type_name


class RowDialog:
    def __init__(self, parent: tk.Tk, table, title: str, initial: Optional[dict[str, object]] = None) -> None:
        self.table = table
        self.initial = initial or {}
        self.result: Optional[dict[str, object]] = None

        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("420x400")
        self.top.configure(bg="#0f172a")
        self.top.transient(parent)
        self.top.grab_set()

        self.entries: dict[str, object] = {}
        frame = ttk.Frame(self.top, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        for field_name, field_type in self.table.schema.items():
            ttk.Label(frame, text=f"{field_name} ({field_type.type_name})").pack(anchor=tk.W, pady=(0, 4))
            if field_type.type_name == "htmlFile":
                html_container = ttk.Frame(frame)
                html_container.pack(fill=tk.X, pady=(0, 12))
                
                content_text = tk.Text(html_container, height=6, background="#0b1220", foreground="#e2e8f0", wrap=tk.WORD)
                content_text.insert("1.0", str(self.initial.get(field_name, "")))
                content_text.pack(fill=tk.X)
                
                button_frame = ttk.Frame(html_container)
                button_frame.pack(fill=tk.X, pady=(6, 0))
                ttk.Button(
                    button_frame,
                    text="Browse",
                    command=lambda widget=content_text: self._select_html_file(widget),
                ).pack(side=tk.LEFT, padx=(0, 6))
                ttk.Button(
                    button_frame,
                    text="Preview",
                    command=lambda widget=content_text: self._preview_html(widget.get("1.0", tk.END)),
                ).pack(side=tk.LEFT, padx=(0, 6))
                ttk.Button(
                    button_frame,
                    text="Export",
                    command=lambda widget=content_text: self._export_html(widget.get("1.0", tk.END)),
                ).pack(side=tk.LEFT)
                self.entries[field_name] = content_text
            else:
                entry = ttk.Entry(frame)
                entry.insert(0, str(self.initial.get(field_name, "")))
                entry.pack(fill=tk.X, pady=(0, 10))
                self.entries[field_name] = entry

        buttons = ttk.Frame(self.top, padding=16)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Save", command=self._submit).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.top.destroy).pack(side=tk.RIGHT)

    def _submit(self) -> None:
        values: dict[str, object] = {}
        for name, entry in self.entries.items():
            if isinstance(entry, tk.Text):
                value = entry.get("1.0", tk.END).strip()
            elif isinstance(entry, tk.StringVar):
                value = entry.get()
            else:
                value = entry.get()
            field_type = self.table.schema[name]
            if field_type.type_name == "integer":
                try:
                    values[name] = int(value)
                except ValueError:
                    messagebox.showerror("Invalid", f"{name} must be integer")
                    return
            elif field_type.type_name == "real":
                try:
                    values[name] = float(value)
                except ValueError:
                    messagebox.showerror("Invalid", f"{name} must be number")
                    return
            elif field_type.type_name == "htmlFile":
                if not value:
                    messagebox.showerror("Invalid", f"{name} requires HTML content or file")
                    return
                values[name] = value
            else:
                values[name] = value
        self.result = values
        self.top.destroy()

    def _select_html_file(self, widget: tk.Text) -> None:
        file_path = filedialog.askopenfilename(title="Select HTML file", filetypes=[("HTML", "*.html;*.htm")])
        if file_path:
            try:
                widget.delete("1.0", tk.END)
                widget.insert("1.0", Path(file_path).read_text(encoding="utf-8"))
            except OSError as exc:
                messagebox.showerror("Error", f"Failed to read file: {exc}")

    def _preview_html(self, content: str) -> None:
        if not content:
            messagebox.showwarning("Preview", "No HTML content to preview")
            return
        try:
            tmp_dir = Path(tempfile.gettempdir())
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / "mini_dbms_preview.html"
            tmp_path.write_text(content, encoding="utf-8")
            import webbrowser

            webbrowser.open(tmp_path.as_uri())
        except OSError as exc:
            messagebox.showerror("Preview failed", str(exc))

    def _export_html(self, content: str) -> None:
        if not content:
            messagebox.showwarning("Export", "No HTML content to export")
            return
        file_path = filedialog.asksaveasfilename(title="Export HTML", defaultextension=".html", filetypes=[("HTML", "*.html;*.htm")])
        if file_path:
            try:
                Path(file_path).write_text(content, encoding="utf-8")
                messagebox.showinfo("Export", f"Saved to {file_path}")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc))

    def show(self) -> Optional[dict[str, object]]:
        self.top.wait_window()
        return self.result


class SortDialog:
    def __init__(self, parent: tk.Tk, columns: list[str]):
        self.result: Optional[tuple[str, bool]] = None
        self.top = tk.Toplevel(parent)
        self.top.title("Sort Table")
        self.top.geometry("300x180")
        self.top.configure(bg="#0f172a")
        self.top.transient(parent)
        self.top.grab_set()

        self.column_var = tk.StringVar(value=columns[0] if columns else "")
        self.reverse_var = tk.BooleanVar(value=False)

        frame = ttk.Frame(self.top, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Column:").pack(anchor=tk.W)
        ttk.Combobox(frame, textvariable=self.column_var, values=columns, state="readonly").pack(fill=tk.X, pady=(4, 12))

        ttk.Checkbutton(frame, text="Descending", variable=self.reverse_var).pack(anchor=tk.W)

        buttons = ttk.Frame(self.top, padding=16)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Sort", command=self._submit).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.top.destroy).pack(side=tk.RIGHT)

    def _submit(self) -> None:
        if not self.column_var.get():
            messagebox.showerror("Invalid", "Select column")
            return
        self.result = (self.column_var.get(), self.reverse_var.get())
        self.top.destroy()

    def show(self) -> Optional[tuple[str, bool]]:
        self.top.wait_window()
        return self.result


def launch_gui() -> None:
    root = tk.Tk()
    DatabaseGUI(root)
    root.mainloop()


