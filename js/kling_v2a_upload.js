import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "KlingVideo2Audio.Upload",

    async nodeCreated(node) {
        if (node.comfyClass !== "KlingVideo2Audio") return;

        const videoWidget = node.widgets?.find(w => w.name === "video");
        if (!videoWidget) return;

        const MAX_DURATION = 20;

        // --- Hide the video text field ---
        videoWidget.type = "hidden";
        videoWidget.computeSize = () => [0, -4];
        videoWidget.draw = function() { return; };

        // --- Status widget (non-serialized, display only) ---
        const statusWidget = node.addWidget("text", "status", 
            videoWidget.value ? `Ready: ${videoWidget.value}` : "Click 'Upload Video' to begin",
            () => {}, { serialize: false }
        );

        // --- Preview holder ---
        let previewWidget = null;

        // --- Upload Video button ---
        node.addWidget("button", "upload_video_btn", "Upload Video", async () => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "video/mp4,video/webm,video/x-matroska,video/quicktime,.mp4,.webm,.mkv,.mov";

            input.onchange = async () => {
                const file = input.files?.[0];
                if (!file) return;

                try {
                    // Check duration
                    statusWidget.value = "Checking video duration...";
                    node.setDirtyCanvas(true);

                    const duration = await getVideoDuration(file);
                    if (duration > MAX_DURATION) {
                        statusWidget.value = `Too long: ${duration.toFixed(1)}s (max ${MAX_DURATION}s)`;
                        node.setDirtyCanvas(true);
                        app.ui.dialog.show(
                            `Video is ${duration.toFixed(1)}s — max allowed is ${MAX_DURATION}s.\nPlease trim and try again.`
                        );
                        return;
                    }

                    // Upload
                    const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
                    statusWidget.value = `Uploading ${file.name} (${sizeMB} MB)...`;
                    node.setDirtyCanvas(true);

                    const fd = new FormData();
                    fd.append("image", file, file.name);
                    fd.append("type", "input");
                    fd.append("overwrite", "true");

                    const resp = await fetch("/upload/image", { method: "POST", body: fd });
                    if (!resp.ok) {
                        statusWidget.value = `Upload failed (HTTP ${resp.status})`;
                        node.setDirtyCanvas(true);
                        app.ui.dialog.show(`Upload failed (HTTP ${resp.status})`);
                        return;
                    }

                    const result = await resp.json();
                    const uploadedName = result.name || file.name;

                    // Only NOW set the widget value — guarantees file is on server
                    videoWidget.value = uploadedName;

                    statusWidget.value = `Ready: ${uploadedName} (${duration.toFixed(1)}s)`;
                    node.setDirtyCanvas(true);

                    // Show preview
                    showPreview(node, uploadedName);

                } catch (e) {
                    console.error("[KlingV2A]", e);
                    statusWidget.value = `Error: ${e.message}`;
                    node.setDirtyCanvas(true);
                    app.ui.dialog.show(`Error: ${e.message}`);
                }
            };
            input.click();
        });

        function showPreview(targetNode, filename) {
            removePreview();

            const videoUrl = `/view?filename=${encodeURIComponent(filename)}&type=input&rand=${Math.random()}`;

            previewWidget = targetNode.addDOMWidget("video_preview", "custom", (() => {
                const container = document.createElement("div");
                container.style.cssText = "width:100%;background:#111;border-radius:6px;overflow:hidden;";

                const vid = document.createElement("video");
                vid.src = videoUrl;
                vid.muted = true;
                vid.autoplay = true;
                vid.loop = true;
                vid.playsInline = true;
                vid.style.cssText = "width:100%;display:block;border-radius:6px;";

                container.appendChild(vid);
                return container;
            })(), { serialize: false, hideOnZoom: false });

            previewWidget.computeSize = function() {
                const w = targetNode.size[0] - 20;
                return [w, Math.round(w * 9 / 16) + 8];
            };

            targetNode.setDirtyCanvas(true, true);
            requestAnimationFrame(() => {
                targetNode.setSize(targetNode.computeSize());
                targetNode.setDirtyCanvas(true, true);
            });
        }

        function removePreview() {
            const idx = node.widgets?.findIndex(w => w.name === "video_preview");
            if (idx >= 0) {
                const w = node.widgets[idx];
                if (w.element?.parentNode) w.element.parentNode.removeChild(w.element);
                node.widgets.splice(idx, 1);
            }
            previewWidget = null;
        }

        // Show preview on load if video is already set
        if (videoWidget.value) {
            setTimeout(() => showPreview(node, videoWidget.value), 500);
        }

        node.size[0] = Math.max(node.size[0], 350);
    },
});

function getVideoDuration(file) {
    return new Promise((resolve, reject) => {
        const v = document.createElement("video");
        v.preload = "metadata";
        v.muted = true;
        v.onloadedmetadata = () => {
            const d = v.duration;
            URL.revokeObjectURL(v.src);
            resolve(isFinite(d) ? d : 0);
        };
        v.onerror = () => {
            URL.revokeObjectURL(v.src);
            reject(new Error("Could not read video metadata"));
        };
        v.src = URL.createObjectURL(file);
    });
}
