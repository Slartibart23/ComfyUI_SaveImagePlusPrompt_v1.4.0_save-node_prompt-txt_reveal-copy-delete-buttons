# ComfyUI SaveImagePlusPrompt

A standalone image-saving node for ComfyUI, inspired by **LayerUtility: SaveImagePlus V2** from [ComfyUI_LayerStyle_Advance](https://github.com/chflame163/ComfyUI_LayerStyle_Advance) (MIT license, thanks to chflame163).

**Node name:** `Save Image + Prompt TXT (Copy & Reveal)` (category: image, internal class name in workflow JSON: `SaveImagePlusPrompt`)

## What it does

- **Saves images** (jpg/png) with sequential numbering, custom output folder on
  any drive, optional timestamp, quality/DPI settings, and optional workflow
  metadata (PNG) or workflow JSON sidecar.
- **Saves the prompt as a .txt file** with the exact same filename as the
  image, in the same folder. Example: `image_00007.jpg` + `image_00007.txt`.
  The prompt is whatever string you connect to the `prompt_text` input.
- **Reveal in file manager** button: one click opens the system file manager
  with the last saved image selected (Windows Explorer, macOS Finder, Linux
  file manager).
- **Save Training File** button: one click copies the last saved image together
  with its matching `.txt` (and `.json`, if present) to any folder you enter
  in the `copy_to_folder` field - keeping identical filenames. This is a pure
  file copy (byte-identical), nothing is re-generated. Useful for sorting
  keepers into a separate folder right after generation.
- **Delete Last Generated Image** button: removes the last saved image and its
  `.txt`/`.json` sidecars (only those files) after a confirmation dialog -
  for discarding bad generations on the spot.

## Installation

1. Clone or copy this folder into `ComfyUI/custom_nodes/`:

```
git clone https://github.com/Slartibart23/ComfyUI_SaveImagePlusPrompt_v1.4.0_save-node_prompt-txt_reveal-copy-delete-buttons.git
```

2. Restart ComfyUI. No additional packages are required.
3. After updating: press **Ctrl+F5** in the browser once so the frontend
   extension (buttons) reloads.

## Inputs

- `images`: image input, as with any save node.
- `prompt_text` (optional): the prompt string to save as `.txt` - e.g. from a
  text node, or from the `text` widget of a *CLIP Text Encode* node
  (right-click the node → *Convert widget to input* → `text`, then wire it to
  both the encoder and this node). If empty or unconnected, no txt is written.
- `custom_path`: custom output folder. Empty = ComfyUI's default output folder.
- `filename_prefix`: filename prefix, may contain subfolders (`project/img`).
  `%date` and `%time` are replaced with the current date/time.
- `timestamp`: optional timestamp in the filename (None / second / millisecond).
- `format`: `jpg` or `png`.
- `quality`: image quality 10-100.
- `dpi`: DPI value written into the file.
- `meta_data`: embed workflow metadata into PNG (PNG only).
- `save_workflow_as_json`: additionally save the workflow as a `.json` sidecar.
- `preview`: show a preview in the ComfyUI window.

The node scans the target folder for existing images and continues the
sequential numbering (`_00001`, `_00002`, ...). The txt file always uses the
same name as the image just saved.

## Buttons on the node

**Reveal in file manager** - after each run, the node remembers the path of
the last saved image (for batches: the last image of the batch). The button
opens the file manager with that file selected. The remembered path only
lives for the current ComfyUI session; before the first run the button shows
a friendly message instead.

**Save Training File** - enter a target folder in the `copy_to_folder` text field
(the value is stored in the workflow), then click the button to copy the last
saved image + its `.txt`/`.json` sidecars into that folder with identical
filenames. Existing files with the same name are replaced.

**Delete Last Generated Image** - deletes the last saved image together
with its `.txt`/`.json` sidecars from the original output folder (only these
files, nothing else). A confirmation dialog protects against accidental
clicks. Useful for discarding bad generations immediately.

Security note: the server endpoints only reveal, copy, or delete paths this
node itself saved during the current session - the frontend cannot operate on
arbitrary paths.

## Compatibility & requirements

- Works with current ComfyUI versions on Windows, macOS, and Linux
  (the "Reveal" button opens Windows Explorer, macOS Finder, or the default
  Linux file manager).
- No additional Python packages required - only the standard ComfyUI
  environment (Pillow, numpy).
- The buttons are provided by a small frontend extension (`web/` folder);
  after updates, reload the browser with **Ctrl+F5**.
- Existing workflows keep loading unchanged: the buttons are not serialized
  into `widgets_values`, and the copy target folder is stored in the node's
  properties.

## Version history

- **v1.4.1** - "Reveal in file manager" on Windows now starts Explorer without a
  shell (safer with unusual file names); fixed the `git clone` URL in the README.
- **v1.4.0** - "Copy to folder" renamed to "Save Training File"; new
  "Delete Last Generated Image" button (removes image + txt/json sidecars,
  with confirmation).
- **v1.3.0** - node display name and all UI messages in English; README rewritten.
- **v1.2.x** - "Copy to folder" button + target folder field; guard against
  duplicate route registration on startup.
- **v1.1.0** - "Reveal in file manager" button.
- **v1.0.0** - initial release: image saving with matching prompt txt.

## License

MIT - like the project that inspired it. See [LICENSE](LICENSE).
