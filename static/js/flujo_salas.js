// Flujo de pacientes en OAF — small multiples.
// Un mini-gráfico por cada sala DONDE SE INICIA la OAF (destino).
// En cada uno: la sala de destino a la DERECHA y TODAS las salas de origen
// (derivación) a la IZQUIERDA, con una flecha por origen que le derivó
// pacientes. Color por origen, grosor ∝ cantidad (escala global), tooltip.
(function () {
    "use strict";
    const NS = "http://www.w3.org/2000/svg";
    const cont = document.getElementById("flujo-salas");
    const data = window.flujoData;
    if (!cont || !data) return;

    const COLORS = ["#60a5fa", "#f59e0b", "#34d399", "#f87171", "#a78bfa",
                    "#22d3ee", "#fb7185", "#facc15", "#4ade80", "#c084fc"];

    // Tooltip único, reutilizable.
    let tip = document.getElementById("flujo-tooltip");
    if (!tip) {
        tip = document.createElement("div");
        tip.id = "flujo-tooltip";
        tip.className = "flujo-tooltip";
        tip.style.display = "none";
        document.body.appendChild(tip);
    }
    const showTip = (e, html) => {
        tip.innerHTML = html;
        tip.style.display = "block";
        tip.style.left = (e.clientX + 14) + "px";
        tip.style.top = (e.clientY + 14) + "px";
    };
    const hideTip = () => { tip.style.display = "none"; };

    const origenes = data.origenes || [];
    const destinos = data.destinos || [];
    const flujos = data.flujos || [];

    const colorOf = {};
    origenes.forEach((o, i) => (colorOf[o] = COLORS[i % COLORS.length]));

    // Escala de grosor global, así el grosor es comparable entre mini-gráficos.
    const maxN = flujos.length ? Math.max(...flujos.map(f => f.n)) : 1;
    const widthOf = n => 1.5 + (n / maxN) * 8;

    // Geometría de cada mini-gráfico (coordenadas del viewBox).
    const W = 320, rowH = 24, topPad = 12, botPad = 12;
    const leftX = 128, rightX = 214, xEnd = rightX - 12;

    function yLeft(i, n) {
        if (n <= 1) return (topPad + (n * rowH) / 2) || (topPad + rowH / 2);
        const gap = ((n - 1) * rowH);
        return topPad + i * (gap / (n - 1));
    }

    function miniGraph(destino) {
        const entrantes = flujos.filter(f => f.destino === destino);
        const total = entrantes.reduce((s, f) => s + f.n, 0);

        const wrap = document.createElement("div");
        wrap.className = "flujo-mini";

        const h = document.createElement("h4");
        h.textContent = destino + (total ? " (" + total + ")" : "");
        wrap.appendChild(h);

        const n = origenes.length;
        const H = Math.max(n, 1) * rowH + topPad + botPad;
        const yDest = H / 2;

        const svg = document.createElementNS(NS, "svg");
        svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
        svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
        svg.style.width = "100%";
        svg.style.height = "auto";
        svg.style.display = "block";
        svg.style.overflow = "visible";

        // Flechas: una por origen que derivó pacientes a este destino.
        entrantes.forEach(f => {
            const i = origenes.indexOf(f.origen);
            const y0 = yLeft(i < 0 ? 0 : i, n);
            const mx = (leftX + rightX) / 2;
            const color = colorOf[f.origen] || "#94a3b8";
            const w = widthOf(f.n);

            const path = document.createElementNS(NS, "path");
            path.setAttribute("d", `M ${leftX} ${y0} C ${mx} ${y0}, ${mx} ${yDest}, ${xEnd} ${yDest}`);
            path.setAttribute("fill", "none");
            path.setAttribute("stroke", color);
            path.setAttribute("stroke-width", w);
            path.setAttribute("stroke-opacity", "0.6");
            path.setAttribute("stroke-linecap", "round");
            path.style.cursor = "pointer";
            path.style.transition = "stroke-opacity .12s";

            const head = document.createElementNS(NS, "polygon");
            head.setAttribute("points", `${xEnd},${yDest - 5} ${rightX},${yDest} ${xEnd},${yDest + 5}`);
            head.setAttribute("fill", color);
            head.setAttribute("fill-opacity", "0.85");

            const label = `<b>${f.origen} → ${destino}</b><br>${f.n} paciente${f.n !== 1 ? "s" : ""}`;
            const enter = () => { path.setAttribute("stroke-opacity", "1"); head.setAttribute("fill-opacity", "1"); };
            const leave = () => { path.setAttribute("stroke-opacity", "0.6"); head.setAttribute("fill-opacity", "0.85"); hideTip(); };
            [path, head].forEach(el => {
                el.addEventListener("mouseenter", enter);
                el.addEventListener("mousemove", e => showTip(e, label));
                el.addEventListener("mouseleave", leave);
            });

            svg.appendChild(path);
            svg.appendChild(head);
        });

        // Nodos de origen (izquierda) — todas las salas, tengan o no flecha.
        const conFlujo = new Set(entrantes.map(f => f.origen));
        origenes.forEach((o, i) => {
            const y = yLeft(i, n);
            const activo = conFlujo.has(o);
            const dot = document.createElementNS(NS, "circle");
            dot.setAttribute("cx", leftX); dot.setAttribute("cy", y); dot.setAttribute("r", 4);
            dot.setAttribute("fill", activo ? (colorOf[o] || "#94a3b8") : "#475569");
            svg.appendChild(dot);

            const t = document.createElementNS(NS, "text");
            t.setAttribute("x", leftX - 10); t.setAttribute("y", y + 3.5);
            t.setAttribute("text-anchor", "end");
            t.setAttribute("fill", activo ? "#e5e7eb" : "#64748b");
            t.setAttribute("font-size", "11");
            t.textContent = o;
            svg.appendChild(t);
        });

        // Nodo de destino (derecha).
        const ddot = document.createElementNS(NS, "circle");
        ddot.setAttribute("cx", rightX); ddot.setAttribute("cy", yDest); ddot.setAttribute("r", 5);
        ddot.setAttribute("fill", "#cbd5e1");
        svg.appendChild(ddot);

        const dt = document.createElementNS(NS, "text");
        dt.setAttribute("x", rightX + 10); dt.setAttribute("y", yDest + 4);
        dt.setAttribute("text-anchor", "start");
        dt.setAttribute("fill", "#f1f5f9");
        dt.setAttribute("font-size", "12");
        dt.setAttribute("font-weight", "bold");
        dt.textContent = destino;
        svg.appendChild(dt);

        wrap.appendChild(svg);
        return wrap;
    }

    function draw() {
        cont.innerHTML = "";
        if (!destinos.length) {
            cont.innerHTML = '<p style="text-align:center;color:#94a3b8;margin:20px;">Sin datos todavía.</p>';
            return;
        }
        destinos.forEach(d => cont.appendChild(miniGraph(d)));
    }

    draw();
})();
