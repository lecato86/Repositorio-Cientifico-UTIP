// estudio_form.js — campos que solo aplican a una respuesta puntual.
//
// Hay preguntas cuyo campo de detalle solo tiene sentido con cierta opción
// elegida ("De otras fuentes (especificar)", "¿Otras instituciones? Sí").
// Esos campos viven SIEMPRE en el HTML —sin JS quedan visibles, que es el
// comportamiento seguro— y acá se ocultan salvo cuando corresponde.
//
// Para sumar otro no hay que tocar este archivo: alcanza con marcar el campo
// en el template con
//     data-depende-de="<id del select>" data-mostrar-si="<texto de la opción>"
(function () {
    "use strict";

    const condicionales = document.querySelectorAll("[data-depende-de]");

    condicionales.forEach((campo) => {
        const select = document.getElementById(campo.dataset.dependeDe);
        if (!select) return;

        // El texto exacto de la opción lo pone el template desde la constante
        // de Python, para no repetirlo acá y que no se desincronicen.
        const valorQueMuestra = campo.dataset.mostrarSi;

        function sincronizar() {
            campo.hidden = select.value !== valorQueMuestra;
        }

        select.addEventListener("change", sincronizar);
        sincronizar();
    });
})();
