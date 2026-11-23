"""Ghost Referee script. Runs inside LibreOffice's bundled Python.

Must not import from ``ghost``. Started by the engine through the macro URL
``vnd.sun.star.script:ghost_referee.py$serve?language=Python&location=user``.

The engine's TCP port is read from the ``GHOST_REFEREE_PORT`` environment
variable (a numeric argument passed to ``serve`` is also accepted). The script
connects to 127.0.0.1 on that port and exchanges one JSON object per line
(UTF-8, request/response in order). See design.md "Referee JSON protocol".

Commands: open, eval, read, macros, run_macro, save_with_vba, quit.

Values are encoded as number, string, null or ``{"error": "<code>"}``.
Input values: number -> numeric cell, bool -> 1/0, str -> text cell,
null -> cleared cell.
"""

import json
import os
import re
import socket
import traceback

HOST = "127.0.0.1"

# com.sun.star.document.MacroExecMode
NEVER_EXECUTE = 0
ALWAYS_EXECUTE_NO_WARN = 2
# com.sun.star.document.UpdateDocMode.NO_UPDATE
NO_UPDATE = 0

VBA_FILTER = "Calc MS Excel 2007 VBA XML"
VBA_LIBRARY = "VBAProject"
MODULE_TYPE_NORMAL = 1  # com.sun.star.script.ModuleType.NORMAL

# CellContentType / FormulaResult constants
_CT_EMPTY, _CT_VALUE, _CT_TEXT, _CT_FORMULA = 0, 1, 2, 3
_FR_VALUE, _FR_STRING, _FR_ERROR = 1, 2, 4
# CellFlags VALUE | DATETIME | STRING | FORMULA
_CLEAR_FLAGS = 1 | 2 | 4 | 16

# LibreOffice error number -> Excel error code (fallback when the cell string
# is not itself an Excel-style error such as "#DIV/0!").
_ERR_CODES = {
    502: "#VALUE!",
    503: "#NUM!",
    504: "#VALUE!",
    519: "#VALUE!",
    524: "#REF!",
    525: "#NAME?",
    532: "#DIV/0!",
    32767: "#N/A",
}


# --------------------------------------------------------------------------
# Pure helpers (no UNO), importable for tests
# --------------------------------------------------------------------------

def parse_ref(ref):
    """Split ``Sheet!A1`` or ``'My Sheet'!A1`` into (sheet, address)."""
    if "!" not in ref:
        raise ValueError("cell reference must look like Sheet!A1: %r" % (ref,))
    sheet, addr = ref.rsplit("!", 1)
    if len(sheet) >= 2 and sheet[0] == "'" and sheet[-1] == "'":
        sheet = sheet[1:-1].replace("''", "'")
    return sheet, addr.replace("$", "")


def error_code(error_number, text):
    """Excel-style error code for a LibreOffice cell error."""
    if text and text.startswith("#") and not text.startswith("#ERR"):
        return text
    return _ERR_CODES.get(error_number, "Err:%d" % error_number)


_SUB_RE = re.compile(r"^\s*(?:(?:Public|Private|Friend|Static)\s+)?(Sub|Function)\s+([A-Za-z_][A-Za-z0-9_]*)",
                     re.IGNORECASE | re.MULTILINE)


def find_procedures(source):
    """Return [(kind, name)] for Sub/Function declarations in Basic source."""
    return [(m.group(1).lower(), m.group(2)) for m in _SUB_RE.finditer(source)]


# --------------------------------------------------------------------------
# Referee (UNO)
# --------------------------------------------------------------------------

class Referee(object):
    def __init__(self, desktop):
        self.desktop = desktop
        self.doc = None
        self.run_macros = False

    # -- plumbing ---------------------------------------------------------
    @staticmethod
    def _props(**kw):
        import uno
        from com.sun.star.beans import PropertyValue
        out = []
        for k, v in kw.items():
            p = PropertyValue()
            p.Name = k
            p.Value = v
            out.append(p)
        return tuple(out)

    def _require_doc(self):
        if self.doc is None:
            raise RuntimeError("no workbook open")

    def _cell(self, ref):
        sheet, addr = parse_ref(ref)
        sheets = self.doc.Sheets
        if not sheets.hasByName(sheet):
            raise KeyError("no such sheet: %s" % sheet)
        return sheets.getByName(sheet).getCellRangeByName(addr)

    def _recalc(self):
        self.doc.calculateAll()

    # -- values -----------------------------------------------------------
    @staticmethod
    def encode(cell):
        ctype = cell.Type.value if hasattr(cell.Type, "value") else cell.Type
        if ctype == "EMPTY" or ctype == _CT_EMPTY:
            return None
        if ctype == "VALUE" or ctype == _CT_VALUE:
            return cell.getValue()
        if ctype == "TEXT" or ctype == _CT_TEXT:
            return cell.getString()
        # formula
        err = cell.getError()
        if err:
            return {"error": error_code(err, cell.getString())}
        rtype = cell.FormulaResultType2
        if rtype == _FR_STRING:
            return cell.getString()
        if rtype == _FR_ERROR:
            return {"error": error_code(0, cell.getString())}
        return cell.getValue()

    def _set_inputs(self, inputs):
        for ref, val in (inputs or {}).items():
            cell = self._cell(ref)
            if val is None:
                cell.clearContents(_CLEAR_FLAGS)
            elif isinstance(val, bool):
                cell.setValue(1.0 if val else 0.0)
            elif isinstance(val, (int, float)):
                cell.setValue(float(val))
            elif isinstance(val, str):
                cell.setString(val)
            else:
                raise TypeError("unsupported input type for %s: %s" % (ref, type(val).__name__))

    def _read(self, refs):
        return {ref: self.encode(self._cell(ref)) for ref in refs}

    # -- commands ---------------------------------------------------------
    def cmd_open(self, req):
        import uno
        path = req["path"]
        run_macros = bool(req.get("run_macros", False))
        if self.doc is not None:
            self._close_doc()
        props = self._props(
            Hidden=True,
            ReadOnly=False,
            MacroExecutionMode=ALWAYS_EXECUTE_NO_WARN if run_macros else NEVER_EXECUTE,
            UpdateDocMode=NO_UPDATE,
        )
        self.doc = self.desktop.loadComponentFromURL(
            uno.systemPathToFileUrl(os.path.abspath(path)), "_blank", 0, props)
        if self.doc is None:
            raise RuntimeError("LibreOffice could not open %s" % path)
        self.run_macros = run_macros
        return {}

    def cmd_eval(self, req):
        self._require_doc()
        self._set_inputs(req.get("inputs"))
        self._recalc()
        return {"values": self._read(req.get("outputs") or [])}

    def cmd_read(self, req):
        self._require_doc()
        self._recalc()
        return {"values": self._read(req.get("cells") or [])}

    def _modules(self):
        """Yield (library, module, source) for document Basic modules."""
        libs = self.doc.BasicLibraries
        for lib_name in libs.getElementNames():
            if not libs.isLibraryLoaded(lib_name):
                libs.loadLibrary(lib_name)
            lib = libs.getByName(lib_name)
            for mod in lib.getElementNames():
                yield lib_name, mod, lib.getByName(mod)

    def cmd_macros(self, req):
        self._require_doc()
        found = []
        for lib, mod, src in self._modules():
            for kind, name in find_procedures(src):
                found.append({"library": lib, "module": mod, "name": name, "kind": kind})
        return {"macros": found}

    def cmd_run_macro(self, req):
        self._require_doc()
        if not self.run_macros:
            raise PermissionError("macros disabled")
        name = req["name"]
        target = None
        parts = name.split(".")
        for lib, mod, src in self._modules():
            for _kind, proc in find_procedures(src):
                if (len(parts) == 3 and (lib, mod, proc) == tuple(parts)) or (
                        len(parts) == 1 and proc == name):
                    target = (lib, mod, proc)
                    break
            if target:
                break
        if target is None:
            raise KeyError("no such macro: %s" % name)
        self._set_inputs(req.get("inputs"))
        url = "vnd.sun.star.script:%s.%s.%s?language=Basic&location=document" % target
        script = self.doc.getScriptProvider().getScript(url)
        script.invoke((), (), ())
        self._recalc()
        return {"values": self._read(req.get("outputs") or [])}

    def cmd_save_with_vba(self, req):
        import uno
        self._require_doc()
        out = req["out"]
        modules = req.get("modules") or {}
        if isinstance(modules, list):
            modules = {m["name"]: m["source"] for m in modules}
        libs = self.doc.BasicLibraries
        for prop, value in (("VBACompatibilityMode", True), ("ProjectName", VBA_LIBRARY)):
            try:
                libs.setPropertyValue(prop, value)
            except Exception:
                setattr(libs, prop, value)
        if not libs.hasByName(VBA_LIBRARY):
            libs.createLibrary(VBA_LIBRARY)
        libs.loadLibrary(VBA_LIBRARY)
        lib = libs.getByName(VBA_LIBRARY)
        for mod_name, source in modules.items():
            if lib.hasByName(mod_name):
                lib.replaceByName(mod_name, source)
            else:
                lib.insertByName(mod_name, source)
            info = uno.createUnoStruct("com.sun.star.script.ModuleInfo")
            info.ModuleType = MODULE_TYPE_NORMAL
            try:
                lib.removeModuleInfo(mod_name)
            except Exception:
                pass
            lib.insertModuleInfo(mod_name, info)
        self.doc.storeToURL(
            uno.systemPathToFileUrl(os.path.abspath(out)),
            self._props(FilterName=VBA_FILTER))
        return {}

    def _close_doc(self):
        if self.doc is not None:
            try:
                self.doc.close(True)
            except Exception:
                try:
                    self.doc.dispose()
                except Exception:
                    pass
            self.doc = None

    def cmd_quit(self, req):
        self._close_doc()
        return {}

    def handle(self, req):
        rid = req.get("id")
        cmd = req.get("cmd")
        resp = {"id": rid} if rid is not None else {}
        fn = getattr(self, "cmd_" + str(cmd), None) if cmd in (
            "open", "eval", "read", "macros", "run_macro", "save_with_vba", "quit") else None
        if fn is None:
            resp.update(ok=False, error="unknown command: %s" % (cmd,))
            return resp
        try:
            resp.update(fn(req))
            resp["ok"] = True
        except PermissionError as exc:
            resp.update(ok=False, error=str(exc))
        except Exception as exc:  # report to the engine, keep serving
            resp.update(ok=False, error="%s: %s" % (type(exc).__name__, exc),
                        trace=traceback.format_exc(limit=5))
        return resp


def _port_from(args):
    for a in args:
        if isinstance(a, int) and not isinstance(a, bool):
            return a
        if isinstance(a, str) and a.isdigit():
            return int(a)
    env = os.environ.get("GHOST_REFEREE_PORT")
    if env and env.isdigit():
        return int(env)
    raise RuntimeError("GHOST_REFEREE_PORT is not set")


def serve(*args):
    """Entry point: connect back to the engine and answer commands."""
    port = _port_from(args)
    try:
        desktop = XSCRIPTCONTEXT.getDesktop()  # noqa: F821 injected by LibreOffice
    except NameError:
        import uno
        ctx = uno.getComponentContext()
        desktop = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", ctx)
    referee = Referee(desktop)
    sock = socket.create_connection((HOST, port))
    reader = sock.makefile("r", encoding="utf-8", newline="\n")
    writer = sock.makefile("w", encoding="utf-8", newline="\n")
    try:
        for line in reader:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except ValueError as exc:
                resp = {"ok": False, "error": "bad json: %s" % exc}
            else:
                resp = referee.handle(req)
            writer.write(json.dumps(resp, default=str) + "\n")
            writer.flush()
            if isinstance(req, dict) and req.get("cmd") == "quit":
                break
    finally:
        referee._close_doc()
        try:
            sock.close()
        finally:
            try:
                desktop.terminate()
            except Exception:
                pass


g_exportedScripts = (serve,)
