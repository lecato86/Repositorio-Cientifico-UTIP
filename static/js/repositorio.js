// repositorio.js — filtro en vivo de la tabla del repositorio.
// Filtra las filas ya renderizadas (no vuelve al servidor): escribe cualquier
// texto y quedan solo las investigaciones que lo contienen en algún campo.
(function () {
    const input = document.getElementById("repo-filtro");
    const tabla = document.getElementById("repo-tabla");
    const conteo = document.getElementById("repo-conteo");
    if (!input || !tabla || !conteo) return;

    const filas = Array.from(tabla.tBodies[0].rows);
    const total = filas.length;
    // El texto de cada fila se calcula una sola vez: la tabla es ancha y
    // recorrer las celdas en cada tecla se nota con muchos registros.
    const textos = filas.map((f) => f.textContent.toLowerCase());

    function filtrar() {
        const q = input.value.trim().toLowerCase();
        let visibles = 0;

        filas.forEach((fila, i) => {
            const coincide = !q || textos[i].includes(q);
            fila.hidden = !coincide;
            if (coincide) visibles++;
        });

        conteo.textContent = visibles + " de " + total;
    }

    input.addEventListener("input", filtrar);
})();
