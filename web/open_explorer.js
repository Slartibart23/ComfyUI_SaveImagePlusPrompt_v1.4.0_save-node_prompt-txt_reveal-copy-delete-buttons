// SaveImagePlusPrompt - Frontend-Erweiterung (v1.2.0)
// Button 1: "Im Explorer zeigen"  -> oeffnet den Dateimanager mit der zuletzt
//           gespeicherten Bilddatei.
// Feld:     "copy_to_folder"      -> Zielordner fuer die Kopie. Der Wert wird
//           in node.properties gespeichert (nicht in widgets_values), damit
//           alte Workflows sauber laden und der Pfad trotzdem im
//           Workflow-JSON erhalten bleibt.
// Button 2: "Kopie in Ordner speichern" -> kopiert das zuletzt gespeicherte
//           Bild samt gleichnamiger .txt (und .json) mit identischem
//           Dateinamen in den Zielordner. Reine Dateikopie, keine
//           Neugenerierung.

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "SaveImagePlusPrompt.OpenExplorer",

    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "SaveImagePlusPrompt") return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            origOnNodeCreated?.apply(this, arguments);

            const node = this;
            node.properties = node.properties || {};

            const noSerialize = (w) => {
                w.serialize = false;
                w.options = Object.assign({}, w.options, { serialize: false });
            };

            const showToast = (ok, msg) => {
                if (app.extensionManager?.toast?.add) {
                    app.extensionManager.toast.add({
                        severity: ok ? "success" : "warn",
                        summary: "Save Image Plus",
                        detail: msg,
                        life: 4000,
                    });
                } else if (!ok) {
                    alert("Save Image Plus: " + msg);
                }
            };

            const post = async (route, body) => {
                const resp = await api.fetchApi(route, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
                return await resp.json();
            };

            // ---------------- Button: Im Explorer zeigen ----------------
            const explorerW = this.addWidget(
                "button",
                "\uD83D\uDCC2 Reveal in file manager",
                null,
                async () => {
                    try {
                        const data = await post(
                            "/saveimageplusprompt/open_explorer",
                            { node_id: String(node.id) }
                        );
                        if (!data.ok) {
                            showToast(false, data.error || "Unknown error");
                        }
                    } catch (err) {
                        console.error("[SaveImagePlusPrompt] open_explorer failed:", err);
                        alert("Save Image Plus: request failed - " + err);
                    }
                }
            );
            noSerialize(explorerW);

            // ---------------- Feld: Zielordner fuer Kopie ----------------
            const folderW = this.addWidget(
                "text",
                "copy_to_folder",
                node.properties.copy_target ?? "",
                (v) => { node.properties.copy_target = v; }
            );
            noSerialize(folderW);

            // ---------------- Button: Kopie in Ordner speichern ----------------
            const copyW = this.addWidget(
                "button",
                "\uD83D\uDCBE Save Training File",
                null,
                async () => {
                    try {
                        const data = await post(
                            "/saveimageplusprompt/copy_last",
                            {
                                node_id: String(node.id),
                                target_dir: folderW.value ?? "",
                            }
                        );
                        showToast(
                            data.ok,
                            data.ok
                                ? (data.message || "Copied.")
                                : (data.error || "Unknown error")
                        );
                    } catch (err) {
                        console.error("[SaveImagePlusPrompt] copy_last failed:", err);
                        alert("Save Image Plus: request failed - " + err);
                    }
                }
            );
            noSerialize(copyW);

            // ---------------- Button: Delete Last Generated Image ----------------
            // Loescht das zuletzt gespeicherte Bild samt .txt/.json aus dem
            // Original-Speicherordner. Mit Rueckfrage gegen Fehlklicks.
            const deleteW = this.addWidget(
                "button",
                "\uD83D\uDDD1\uFE0F Delete Last Generated Image",
                null,
                async () => {
                    if (!confirm("Delete the last generated image together with its .txt/.json files?")) {
                        return;
                    }
                    try {
                        const data = await post(
                            "/saveimageplusprompt/delete_last",
                            { node_id: String(node.id) }
                        );
                        showToast(
                            data.ok,
                            data.ok
                                ? (data.message || "Deleted.")
                                : (data.error || "Unknown error")
                        );
                    } catch (err) {
                        console.error("[SaveImagePlusPrompt] delete_last failed:", err);
                        alert("Save Image Plus: request failed - " + err);
                    }
                }
            );
            noSerialize(deleteW);
        };

        // Beim Laden eines Workflows den gespeicherten Zielordner ins Feld holen
        const origOnConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            origOnConfigure?.apply(this, arguments);
            const folderW = this.widgets?.find((x) => x.name === "copy_to_folder");
            if (folderW && this.properties?.copy_target !== undefined) {
                folderW.value = this.properties.copy_target;
            }
        };
    },
});
