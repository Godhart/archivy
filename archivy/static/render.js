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

    static render_ssr(kind, objid, content) {
        return new Promise((resolve, reject) => {
            resolve({
                "ok": true,
                "data": `<pre>TODO: Render Visio Doc</pre>`
            })
        })
    }

    static renders() { return {
        "raw": {
            "function" : this.render_raw
        },
        "render-visio" : {
            "function" : this.render_ssr
        }
    }}

    static supported (kind) {
        if (kind === "xxx") {
            // NOTE: that one is for testing error handling only
            return true
        }
        return this.renders()[kind] !== undefined
    }

    static render (kind, objid, content, target) {
        console.log(`render(${kind}, ${objid}, ${content}, ${target})`)
        if (this.renders()[kind] !== undefined) {
            this.renders()[kind].function(kind, objid, content)
            .then((response) => {
                    target.innerHTML = response.data
                }
            )
            .catch((err) => {
                target.innerHTML = `<pre>Error: ${err.message}</pre>`
                console.error(`Fetch problem: ${err.message}`)
            })
        } else {
            target.innerHTML = `<pre class="hljs"><code>Error: render ${kind} is not supported!\n\n${content}</code></pre>`
        }

    }

    static render_div(kind, objid, content, clsid) {
        return `</code></pre>
<div class="${clsid}" data-kind="${kind}" data-objid="${objid}" data-needs-update="true">
<pre style="display:none;"><code class="lazyrender-content">${content}</code></pre>
<div class="lazyrender-result"></div>
</div><pre><code>`
    }

    static render_by_clsid(clsid) {
        let items = document.getElementsByClassName(clsid);
        for(let i = 0; i < items.length; i++) {
            let item = items[i]
            if (item.getAttribute("data-needs-update") != "true") {
                continue
            }
            let content = item.getElementsByClassName("lazyrender-content")
            if (content.length != 1) {
                continue
            }
            let target = item.getElementsByClassName("lazyrender-result")
            if (target.length != 1) {
                continue
            }
            this.render(item.getAttribute("data-kind"), item.getAttribute("data-objid"), content[0].innerHTML, target[0])
            item.setAttribute("data-needs-update", "false")
        }
    }

}