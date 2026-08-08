// repositorio.js — filtro en vivo del repositorio.
// Filtra lo ya renderizado (no vuelve al servidor): se escribe cualquier texto
// y quedan solo las investigaciones que lo contienen en algún campo.
//
// Sirve para las dos vistas: marca con [data-filtrable] cada tarjeta
// (vista de tarjetas) o cada fila (vista de tabla), así el JS no necesita
// saber cuál se está mostrando.
(function () {
    "use strict";

    const input = document.getElementById("repo-filtro");
    const conteo = document.getElementById("repo-conteo");
    if (!input || !conteo) return;

    const items = Array.from(document.querySelectorAll("[data-filtrable]"));
    if (!items.length) return;

    const total = items.length;
    const vacio = document.getElementById("repo-sin-coincidencias");

    // El texto de cada item se calcula una sola vez: recorrer el DOM en cada
    // tecla se nota cuando hay muchos registros.
    const textos = items.map((el) => el.textContent.toLowerCase());

    function filtrar() {
        const q = input.value.trim().toLowerCase();
        let visibles = 0;

        items.forEach((el, i) => {
            const coincide = !q || textos[i].includes(q);
            el.hidden = !coincide;
            if (coincide) visibles++;
        });

        conteo.textContent = visibles + " de " + total;
        if (vacio) vacio.hidden = visibles !== 0;
    }

    input.addEventListener("input", filtrar);
})();
