# ComfyUI_SaveImagePlusPrompt
#
# Eine eigenstaendige Save-Node, inspiriert von "LayerUtility: SaveImagePlus V2"
# aus https://github.com/chflame163/ComfyUI_LayerStyle_Advance (MIT-Lizenz).
# Zusatzfunktion: Der verwendete Textprompt wird als TXT-Datei mit exakt dem
# gleichen Dateinamen wie das Bild im gleichen Ordner gespeichert.
#
# v1.2.1: Doppelt-Lade-Schutz fuer die HTTP-Routen.
# v1.2.0: "Kopie in Ordner"-Button. v1.1.0: "Im Explorer zeigen"-Button. Die Node merkt sich pro Node-Instanz den
# zuletzt gespeicherten Bildpfad; ein Klick auf den Button (siehe web/) ruft
# einen HTTP-Endpoint auf, der den Windows-Explorer mit markierter Datei
# oeffnet (macOS: Finder, Linux: Dateimanager des Systems).

import os
import re
import sys
import json
import datetime
import shutil
import subprocess
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths

# Zuletzt gespeicherter Bildpfad je Node-ID (nur fuer die laufende Session).
# Der Explorer-Endpoint oeffnet ausschliesslich Pfade aus diesem Dict --
# das Frontend kann also keine beliebigen Pfade oeffnen lassen.
_LAST_SAVED = {}


def _replace_tokens(text: str, now: datetime.datetime) -> str:
    """Ersetzt %date und %time wie im Original-Plugin."""
    text = text.replace("%date", now.strftime("%Y-%m-%d"))
    text = text.replace("%time", now.strftime("%H-%M-%S"))
    return text


def _open_in_file_manager(path: str) -> None:
    """Oeffnet den System-Dateimanager mit markierter/angezeigter Datei."""
    path = os.path.normpath(path)
    if sys.platform == "win32":
        # explorer /select,"C:\pfad\datei.jpg" markiert die Datei im Ordner.
        # Hinweis: explorer liefert oft Exit-Code 1, das ist KEIN Fehler.
        subprocess.Popen(["explorer", "/select,", path])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


class SaveImagePlusPrompt:

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.temp_dir = folder_paths.get_temp_directory()

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "custom_path": ("STRING", {"default": ""}),
                "filename_prefix": ("STRING", {"default": "comfyui"}),
                "timestamp": (["None", "second", "millisecond"],),
                "format": (["jpg", "png"],),
                "quality": ("INT", {"default": 80, "min": 10, "max": 100, "step": 1}),
                "dpi": ("INT", {"default": 300, "min": 72, "max": 1200, "step": 1}),
                "meta_data": ("BOOLEAN", {"default": False}),
                "save_workflow_as_json": ("BOOLEAN", {"default": False}),
                "preview": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "prompt_text": ("STRING", {"forceInput": True}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_image_plus_prompt"
    OUTPUT_NODE = True
    CATEGORY = "image"

    def save_image_plus_prompt(self, images, custom_path, filename_prefix, timestamp,
                               format, quality, dpi, meta_data, save_workflow_as_json,
                               preview, prompt_text="", prompt=None, extra_pnginfo=None,
                               unique_id=None):
        now = datetime.datetime.now()

        # ------------------------------------------------------------------
        # Zielordner bestimmen
        # ------------------------------------------------------------------
        custom_path = _replace_tokens(custom_path.strip(), now)
        filename_prefix = _replace_tokens(filename_prefix.strip(), now)

        # Der Prefix darf Unterordner enthalten (z.B. "projekt/bild")
        sub_dir, base_name = os.path.split(filename_prefix)
        if base_name == "":
            base_name = "comfyui"

        if custom_path != "":
            output_dir = os.path.join(custom_path, sub_dir)
        else:
            output_dir = os.path.join(self.output_dir, sub_dir)
        os.makedirs(output_dir, exist_ok=True)

        # ------------------------------------------------------------------
        # Optionaler Zeitstempel im Dateinamen
        # ------------------------------------------------------------------
        if timestamp == "second":
            base_name = f'{base_name}_{now.strftime("%Y-%m-%d_%H-%M-%S")}'
        elif timestamp == "millisecond":
            base_name = f'{base_name}_{now.strftime("%Y-%m-%d_%H-%M-%S")}_{now.microsecond // 1000:03d}'

        results = []
        for image in images:
            # Tensor -> PIL-Bild
            img_array = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))

            # ------------------------------------------------------------------
            # Laufende Nummer bestimmen: Der Ordner wird nach vorhandenen
            # Dateien mit dem Muster "<praefix>_<nummer>.<endung>" durchsucht.
            # Die hoechste gefundene Nummer wird uebernommen und mit derselben
            # Stellenzahl weitergezaehlt (z.B. _00435 -> _00436).
            # TXT- und JSON-Dateien werden dabei ignoriert, damit fehlende
            # Begleitdateien die Bild-Nummerierung nicht durcheinanderbringen.
            # ------------------------------------------------------------------
            pattern = re.compile(
                re.escape(base_name) + r"_(\d+)\.(png|jpg|jpeg|webp)$",
                re.IGNORECASE,
            )
            max_counter = 0
            digits = None
            for existing in os.listdir(output_dir):
                m = pattern.match(existing)
                if m:
                    num = int(m.group(1))
                    if num >= max_counter:
                        max_counter = num
                        digits = len(m.group(1))
            if digits is None:
                digits = 5  # Standard-Stellenzahl, falls der Ordner noch leer ist

            counter = max_counter + 1
            while True:
                file_stem = f"{base_name}_{counter:0{digits}d}"
                image_file_name = os.path.join(output_dir, f"{file_stem}.{format}")
                if not os.path.exists(image_file_name):
                    break
                counter += 1

            # ------------------------------------------------------------------
            # Bild speichern
            # ------------------------------------------------------------------
            if format == "png":
                png_info = None
                if meta_data:
                    png_info = PngInfo()
                    if prompt is not None:
                        png_info.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo is not None:
                        for key in extra_pnginfo:
                            png_info.add_text(key, json.dumps(extra_pnginfo[key]))
                img.save(image_file_name, pnginfo=png_info,
                         compress_level=int((100 - quality) / 10), dpi=(dpi, dpi))
            else:
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(image_file_name, quality=quality, dpi=(dpi, dpi))

            # NEU (v1.1.0): Pfad fuer den "Im Explorer zeigen"-Button merken.
            # Bei Batches gewinnt das zuletzt gespeicherte Bild.
            if unique_id is not None:
                _LAST_SAVED[str(unique_id)] = os.path.abspath(image_file_name)

            # ------------------------------------------------------------------
            # Prompt als TXT mit identischem Dateinamen speichern.
            # Es wird stur derselbe Name wie beim gerade gespeicherten Bild
            # verwendet - eine evtl. vorhandene TXT wird ueberschrieben.
            # ------------------------------------------------------------------
            if prompt_text is not None and str(prompt_text).strip() != "":
                txt_file_name = os.path.splitext(image_file_name)[0] + ".txt"
                with open(txt_file_name, "w", encoding="utf-8") as f:
                    f.write(str(prompt_text))

            # ------------------------------------------------------------------
            # Optional: Workflow als JSON daneben speichern
            # ------------------------------------------------------------------
            if save_workflow_as_json and extra_pnginfo is not None and "workflow" in extra_pnginfo:
                json_file_name = os.path.splitext(image_file_name)[0] + ".json"
                with open(json_file_name, "w", encoding="utf-8") as f:
                    json.dump(extra_pnginfo["workflow"], f, indent=2)

            # ------------------------------------------------------------------
            # Vorschau im ComfyUI-Fenster
            # ------------------------------------------------------------------
            if preview:
                try:
                    rel = os.path.relpath(image_file_name, self.output_dir)
                    if not rel.startswith(".."):
                        # Datei liegt im normalen Output-Ordner
                        results.append({
                            "filename": os.path.basename(image_file_name),
                            "subfolder": os.path.dirname(rel),
                            "type": "output",
                        })
                    else:
                        raise ValueError("outside output dir")
                except ValueError:
                    # Datei liegt ausserhalb -> Vorschau-Kopie in den Temp-Ordner
                    os.makedirs(self.temp_dir, exist_ok=True)
                    preview_name = f"sipp_{now.strftime('%H%M%S%f')}_{counter:04d}.png"
                    img.save(os.path.join(self.temp_dir, preview_name))
                    results.append({
                        "filename": preview_name,
                        "subfolder": "",
                        "type": "temp",
                    })

        return {"ui": {"images": results}}


def _copy_last(node_id: str, target_dir: str):
    """Kopiert das zuletzt gespeicherte Bild dieser Node-ID samt gleichnamiger
    .txt- (und .json-)Begleitdatei mit identischem Dateinamen in target_dir.
    Rueckgabe: (ok, meldung)."""
    path = _LAST_SAVED.get(str(node_id))
    if not path:
        return False, "No image saved yet - run the workflow first."
    if not os.path.isfile(path):
        return False, f"File no longer exists: {path}"
    target_dir = str(target_dir or "").strip()
    if target_dir == "":
        return False, "Please enter a target folder in 'copy_to_folder' first."
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        return False, f"Cannot create target folder: {e}"

    import shutil
    copied = []
    stem = os.path.splitext(path)[0]
    for src in [path, stem + ".txt", stem + ".json"]:
        if os.path.isfile(src):
            dst = os.path.join(target_dir, os.path.basename(src))
            shutil.copy2(src, dst)  # identischer Name; vorhandene Datei wird ersetzt
            copied.append(os.path.basename(src))
    return True, "Copied: " + ", ".join(copied) + " -> " + os.path.normpath(target_dir)


def _delete_last(node_id: str):
    """Loescht das zuletzt gespeicherte Bild dieser Node-ID samt gleichnamiger
    .txt- und .json-Begleitdatei (nur diese drei Dateien, keine Ordner).
    Rueckgabe: (ok, meldung)."""
    node_id = str(node_id)
    path = _LAST_SAVED.get(node_id)
    if not path:
        return False, "No image saved yet - run the workflow first."
    stem = os.path.splitext(path)[0]
    deleted, errors = [], []
    for src in [path, stem + ".txt", stem + ".json"]:
        if os.path.isfile(src):
            try:
                os.remove(src)
                deleted.append(os.path.basename(src))
            except Exception as e:
                errors.append(f"{os.path.basename(src)}: {e}")
    # Eintrag entfernen: Nach dem Loeschen gibt es kein "letztes Bild" mehr,
    # ein zweiter Klick soll eine klare Meldung statt Fehlern liefern.
    _LAST_SAVED.pop(node_id, None)
    if errors:
        return False, "Errors: " + "; ".join(errors)
    if not deleted:
        return False, "Files already gone: " + os.path.basename(path)
    return True, "Deleted: " + ", ".join(deleted)


# ----------------------------------------------------------------------
# HTTP-Endpoint fuer den "Im Explorer zeigen"-Button (web/open_explorer.js).
# Oeffnet NUR Pfade, die diese Node in der laufenden Session selbst
# gespeichert hat (Lookup ueber die Node-ID) - keine freien Pfade.
# ----------------------------------------------------------------------
try:
    from server import PromptServer
    from aiohttp import web as _aioweb

    # Schutz gegen doppeltes Laden des Moduls (z.B. Ordner-Duplikat in
    # custom_nodes oder lose .py-Kopie): Die Routen duerfen nur EINMAL
    # registriert werden, sonst crasht ComfyUI beim Start mit
    # "method POST is already registered". Das Flag liegt bewusst auf der
    # geteilten PromptServer-Instanz, nicht im Modul.
    if getattr(PromptServer.instance, "_sipp_routes_registered", False):
        raise RuntimeError(
            "SaveImagePlusPrompt-Routen bereits registriert - zweite Kopie des "
            "Node-Packs erkannt (custom_nodes auf Duplikate pruefen). "
            "Routen-Registrierung wird uebersprungen, Node funktioniert weiter.")
    PromptServer.instance._sipp_routes_registered = True

    @PromptServer.instance.routes.post("/saveimageplusprompt/open_explorer")
    async def _sipp_open_explorer(request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        node_id = str(data.get("node_id", ""))
        path = _LAST_SAVED.get(node_id)
        if not path:
            return _aioweb.json_response(
                {"ok": False,
                 "error": "No image saved yet - run the workflow first."})
        if not os.path.isfile(path):
            return _aioweb.json_response(
                {"ok": False,
                 "error": f"File no longer exists: {path}"})
        try:
            _open_in_file_manager(path)
            return _aioweb.json_response({"ok": True, "path": path})
        except Exception as e:
            return _aioweb.json_response({"ok": False, "error": str(e)})

    @PromptServer.instance.routes.post("/saveimageplusprompt/copy_last")
    async def _sipp_copy_last(request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        ok, msg = _copy_last(str(data.get("node_id", "")),
                             data.get("target_dir", ""))
        key = "message" if ok else "error"
        return _aioweb.json_response({"ok": ok, key: msg})

    @PromptServer.instance.routes.post("/saveimageplusprompt/delete_last")
    async def _sipp_delete_last(request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        ok, msg = _delete_last(str(data.get("node_id", "")))
        key = "message" if ok else "error"
        return _aioweb.json_response({"ok": ok, key: msg})

except Exception as _e:
    # Ausserhalb einer laufenden ComfyUI-Instanz (z.B. Tests) einfach ohne Route weiter.
    print(f"[SaveImagePlusPrompt] Explorer-Route nicht registriert: {_e}")


NODE_CLASS_MAPPINGS = {
    "SaveImagePlusPrompt": SaveImagePlusPrompt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SaveImagePlusPrompt": "Save Image + Prompt TXT (Copy & Reveal)",
}
