(function() {
    const data = window.trajectoryData;
    const container = document.getElementById("trayectoria-chart");
    const empty = document.getElementById("trayectoria-empty");
    const tooltip = document.getElementById("trayectoria-tooltip");
    if (!container || !data || !data.length) {
        if (empty) empty.style.display = "block";
        if (container) container.style.display = "none";
        return;
    }
    if (empty) empty.style.display = "none";

    const width = 980;
    const height = 420;
    const margin = { top: 28, right: 28, bottom: 76, left: 92 };
    const levels = [
        { label: "AA", value: 7 },
        { label: "CN", value: 6 },
        { label: "VENTURI", value: 5 },
        { label: "MR", value: 4 },
        { label: "OAF", value: 3 },
        { label: "VNI", value: 2 },
        { label: "ARM", value: 1 }
    ];

    // Nombres de campos que devuelve el backend (en español).
    const nivelDe = d => d.soporte_nivel || 0;
    const atencionesDe = d => d.atenciones || 0;

    const maxInterventions = Math.max(1, ...data.map(atencionesDe));
    const xStep = data.length > 1
        ? (width - margin.left - margin.right) / (data.length - 1)
        : 0;
    const yFor = level => margin.top + ((7 - level) / 6) * (height - margin.top - margin.bottom);
    const xFor = index => data.length > 1
        ? margin.left + (index * xStep)
        : width / 2;
    const colorFor = (from, to) => {
        if (nivelDe(to) > nivelDe(from)) return "#16a34a";
        if (nivelDe(to) < nivelDe(from)) return "#f97316";
        return "#94a3b8";
    };
    const strokeFor = item => 2 + (atencionesDe(item) / maxInterventions) * 8;
    const ns = "http://www.w3.org/2000/svg";

    // Crear el elemento <svg> raíz (esto faltaba: sin <svg> no se dibuja nada).
    container.innerHTML = "";
    container.style.display = "block";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", "100%");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    svg.style.maxWidth = width + "px";
    svg.style.height = "auto";
    container.appendChild(svg);

    const add = (tag, attrs, text) => {
        const el = document.createElementNS(ns, tag);
        Object.entries(attrs || {}).forEach(([key, value]) => el.setAttribute(key, value));
        if (text !== undefined) el.textContent = text;
        svg.appendChild(el);
        return el;
    };

    add("rect", { x: 0, y: 0, width, height, rx: 8, fill: "#ffffff" });
    levels.forEach(level => {
        const y = yFor(level.value);
        add("line", {
            x1: margin.left, y1: y, x2: width - margin.right, y2: y,
            stroke: "#e2e8f0", "stroke-width": 1
        });
        add("text", {
            x: margin.left - 18, y: y + 5, "text-anchor": "end",
            fill: "#334155", "font-size": 13, "font-weight": 700
        }, level.label);
    });
    add("line", {
        x1: margin.left, y1: margin.top, x2: margin.left, y2: height - margin.bottom,
        stroke: "#94a3b8", "stroke-width": 1
    });
    add("line", {
        x1: margin.left, y1: height - margin.bottom, x2: width - margin.right, y2: height - margin.bottom,
        stroke: "#94a3b8", "stroke-width": 1
    });

    for (let i = 0; i < data.length - 1; i++) {
        const from = data[i];
        const to = data[i + 1];
        add("line", {
            x1: xFor(i), y1: yFor(nivelDe(from)),
            x2: xFor(i + 1), y2: yFor(nivelDe(to)),
            stroke: colorFor(from, to),
            "stroke-width": strokeFor(to),
            "stroke-linecap": "round",
            opacity: 0.9
        });
    }

    data.forEach((item, index) => {
        const x = xFor(index);
        const y = yFor(nivelDe(item));
        const group = add("g", { tabindex: "0", role: "button" });
        const circle = document.createElementNS(ns, "circle");
        circle.setAttribute("cx", x);
        circle.setAttribute("cy", y);
        circle.setAttribute("r", 7);
        circle.setAttribute("fill", "#0f172a");
        circle.setAttribute("stroke", "#ffffff");
        circle.setAttribute("stroke-width", 2);
        group.appendChild(circle);

        if (data.length <= 12 || index === 0 || index === data.length - 1) {
            const label = document.createElementNS(ns, "text");
            label.setAttribute("x", x);
            label.setAttribute("y", height - margin.bottom + 28);
            label.setAttribute("text-anchor", "middle");
            label.setAttribute("fill", "#64748b");
            label.setAttribute("font-size", "12");
            label.textContent = (item.fecha || "").slice(5);
            group.appendChild(label);
        }

        const showTip = event => {
            const tipParts = [
                "<b>" + item.fecha + "</b><br>",
                "Soporte: " + item.soporte + "<br>",
                "Sala: " + (item.sala || "Sin sala") + "<br>",
                "Atenciones: " + atencionesDe(item)
            ];
            tooltip.innerHTML = tipParts.join("");
            tooltip.style.display = "block";
            const rect = svg.getBoundingClientRect();
            tooltip.style.left = Math.min(rect.width - 180, Math.max(8, event.clientX - rect.left + 12)) + "px";
            tooltip.style.top = Math.max(8, event.clientY - rect.top - 18) + "px";
        };
        const hideTip = () => tooltip.style.display = "none";
        group.addEventListener("mousemove", showTip);
        group.addEventListener("focus", () => showTip({ clientX: x, clientY: y }));
        group.addEventListener("mouseleave", hideTip);
        group.addEventListener("blur", hideTip);
    });
})();
