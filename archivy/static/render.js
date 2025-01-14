class Renderer {

    constructor() {

    }

    static render_raw(kind, objid, content) {
        return new Promise((resolve, reject) => {
            resolve({
                "ok": true,
                "data": `<pre>${content}</pre>`
            })
        })
    }

    static makeCopier(block, button, feedback) {
        /* based on https://jordemort.dev/blog/adding-copy-buttons-to-code-blocks/ */
        let code = block.getElementsByTagName("code")[0];
      
        async function copier() {
            await navigator.clipboard.writeText(code.innerText);
            button.classList.add("clicked");
            feedback.style.display = "block";
        
            setTimeout(() => {
                button.classList.remove("clicked")
            }, 100);
        
            setTimeout(() => {
                feedback.style.display = "none";
            }, 500);
        }
        
        return copier;
    }

    static render_copybutton(kind, objid, content, datanode) {
        return new Promise((resolve, reject) => {
            /* based on https://jordemort.dev/blog/adding-copy-buttons-to-code-blocks/ */

            let block = datanode;

            const copyButton = document.getElementById("copyButtonTemplate").content.firstElementChild;
            const copiedFeedback = document.getElementById("copiedFeedbackTemplate").content.firstElementChild;

            let div = document.createElement("div");
            div.classList.add("code-buttons");

            let feedback = copiedFeedback.cloneNode(true);
            feedback.style.display = "none";

            let button = copyButton.cloneNode(true);
            button.addEventListener("click", Renderer.makeCopier(block, button, feedback));

            block.parentNode.insertBefore(div, block);
            div.appendChild(button);
            div.appendChild(feedback);

            resolve({
                "ok": true,
                "data": null
            })
        })
    }

    static render_ssr(kind, objid, content, datanode) {
        return new Promise((resolve, reject) => {
            const dark = datanode.getAttribute("data-dark");
            const options = {
                "dark-theme": dark == "true"
            }
            fetch(`/api/render`, {
                "method": "POST",
                "body": JSON.stringify({
                    "kind": kind,
                    "objid": objid,
                    "content": content,
                    "options": options,
                }),
                "headers": {
                    "Accept": "application/json",
                    "Content-type": "application/json; charset=UTF-8"
                },
            })
            .then((response) => {
                if (response.ok) {
                    response.json()
                    .then((json) => resolve({"ok": true, "data": json.data}))
                } else {
                    let msg = `render request error: ${response.status} - ${response.statusText}`
                    console.error(msg)
                    reject({"message":msg})
                }
            })
            .catch((err) => {console.error(`render error: ${err.message}`); reject(err) });
        })
    }

    static wavedrom_id = 0;
    static wavedrom_notFirstSignal = false;

    static render_wavedrom(kind, objid, content, datanode) {
        return new Promise((resolve, reject) => {
            // NOTE: code is based on WaveDrom.ProcessAll function (second pass)
            const id = datanode.getAttribute("data-wavedrom-idx");
            const obj = WaveDrom.eva(`InputJSON_${id}`);
            WaveDrom.RenderWaveForm(id, obj, 'WaveDrom_Display_', Renderer.wavedrom_notFirstSignal)
            if (obj && obj.signal && !Renderer.wavedrom_notFirstSignal) {
                Renderer.wavedrom_notFirstSignal = true;
            }
            // TODO: appendSaveAsDialog(id, 'WaveDrom_Display_')
            resolve({
                "ok": true,
                "data": null    // NOTE: return null since content is already rendered
            })
        })
    }

    static custom_div_wavedrom (kind, objid, content, clsid) {
        const id = Renderer.wavedrom_id;
        Renderer.wavedrom_id += 1;
        // NOTE: code is based on WaveDrom.ProcessAll function (first pass)
        return `
<div class="${clsid}" data-kind="${kind}" data-objid="${objid}" data-needs-update="true" data-wavedrom-idx="${id}">
<div id="WaveDrom_Display_${id}" class="lazyrender-result"></div>
<script type="WaveDrom" id="InputJSON_${id}">${content}</script>
<div class="lazyrender-content" style="display:none;"></div>
</div>`
    }

    static renders() { return {
        "raw": {
            "function"  : this.render_raw
        },
        "copybutton": {
            "function"  : this.render_copybutton
        },
        "ssr" : {
            "function"  : this.render_ssr
        },
        "wavedrom" : {
            "function"  : this.render_wavedrom,
            "custom_div": this.custom_div_wavedrom,
        }
    }}

    static render_map(value) {
        if (value === "ssq") {
            return "ssr"
        }
        if ((value.substring(0,4) === "ssr-") || (value.substring(0,4) === "ssq-")) {
            return "ssr"
        }
        return value
    }

    static supported (kind) {
        if (kind === "xxx") {
            // NOTE: that one is for testing errors handling only
            return true
        }
        return this.renders()[this.render_map(kind)] !== undefined
    }

    static tuneSvg(element) {
        // get all SVG objects marked to tune
        let tune_marker = element.getElementsByClassName("svg-to-tune");
        if (tune_marker.length == 0) {
            console.log("svg to tune")
            return;
        }
        let trim_svg   = tune_marker[0].classList.contains("svg-trim");
        let hacky_trim = tune_marker[0].classList.contains("svg-hacky-trim");
        if (hacky_trim) {
            trim_svg = true;
        }
        let hacky_back = tune_marker[0].classList.contains("svg-hacky-back");
        let svgs = element.getElementsByTagName("svg");

        // go through each one and add a viewbox that ensures all children are visible
        for (let i=0, l=svgs.length; i<l; i++) {

            let svg = svgs[i];

            let box = null;
            let viewBox = null;

            if (trim_svg) {
                console.log("trim 1")
                box = svg.getBBox(); // <- get the visual boundary required to view all children
                viewBox = [box.x, box.y, box.width, box.height].join(" ");
            }

            if (hacky_trim) {
                // EMF/WMF imported SVGs (at least via libre office) may return invalid result for getBBox
                // This hack may help
                console.log("trim 2")
                let bboxes = svg.getElementsByClassName("BoundingBox");
                if (bboxes.length > 0) {
                    viewBox = [
                        bboxes[0].getAttribute("x"),
                        bboxes[0].getAttribute("y"),
                        bboxes[0].getAttribute("width"),
                        bboxes[0].getAttribute("height")
                    ]
                }
            }

            if (trim_svg) {
                console.log("trim 3")
                // set viewable area based on value above
                svg.setAttribute("viewBox", viewBox);

                // set scaling method (preserve aspect ratio, center based)
                svg.setAttribute("preserveAspectRatio", "xMidYMid");
                svg.removeAttribute("height");
                svg.removeAttribute("width");
            }

            if (hacky_back) {
                console.log("hacky back")
                // Symbolator doesn't produces transparent background
                // This hack helps
                let rects = svg.getElementsByTagName("rect");
                for (let j=0, lr=rects.length; j < lr; j++) {
                    let rect = rects[j];
                    if (rect.parentNode != svg) {
                        continue
                    }
                    if (rect.getAttribute("width") != "100%") {
                        continue
                    }
                    if (rect.getAttribute("height") != "100%") {
                        continue
                    }
                    rect.setAttribute("fill", "#FFFFFF00")
                }
            }
        }
    }

    static render (kind, objid, content, target, datanode) {
        // console.log(`render(${kind}, ${objid}, ${content}, ${target})`)
        if (this.renders()[this.render_map(kind)] !== undefined) {
            this.renders()[this.render_map(kind)].function(kind, objid, content, datanode)
            .then((response) => {
                    if (response.data !== null && target !== null) {
                        target.innerHTML = response.data
                        let scripts = target.getElementsByTagName('script');
                        for (let ix = 0; ix < scripts.length; ix++) {
                            eval(scripts[ix].text);
                        }
                        Renderer.tuneSvg(target)
                    }
                }
            )
            .catch((err) => {
                if (target !== null) {
                    target.innerHTML = `<pre>Error: ${err.message}</pre>`
                }
                console.error(`Fetch problem: ${err.message}`)
            })
        } else {
            if (target !== null) {
                target.innerHTML = `<pre class="hljs"><code>Error: render ${kind} is not supported!\n\n${content}</code></pre>`
            }
            console.error(`render ${kind} is not supported!`)
        }

    }

    static render_div(kind, objid, content, clsid, dark) {
        if (this.renders()[this.render_map(kind)].custom_div !== undefined) {
            return this.renders()[this.render_map(kind)].custom_div(kind, objid, content, clsid)
        } else {
            return `</code></pre>
<div class="${clsid}" data-kind="${kind}" data-objid="${objid}" data-dark="${dark}" data-needs-update="true">
<pre style="display:none;"><code class="lazyrender-content">${content}</code></pre>
<div class="lazyrender-result"></div>
</div><pre><code>`
        }
    }

    static render_by_clsid(clsid) {
        let items = document.getElementsByClassName(clsid);
        for(let i = 0; i < items.length; i++) {
            let item = items[i]
            if (item.getAttribute("data-needs-update") != "true") {
                continue
            }
            let data_kind = item.getAttribute("data-kind")
            let content = item.getElementsByClassName("lazyrender-content")
            if (content.length != 1) {
                if (data_kind != "copybutton") {
                    continue
                }
                content = null
            } else {
                content = content[0].innerHTML
            }

            let target = item.getElementsByClassName("lazyrender-result")
            if (target.length != 1) {
                if (data_kind != "copybutton") {
                    continue
                }
                target = null
            } else {
                target = target[0]
            }
            this.render(data_kind, item.getAttribute("data-objid"), content, target, item)
            item.setAttribute("data-needs-update", "false")
        }
    }

}