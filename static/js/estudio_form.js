// estudio_form.js — reglas de visibilidad del formulario de investigaciones.
//
// "¿De dónde se obtendrán los datos?" tiene una opción que pide especificar.
// El campo de texto vive siempre en el HTML (sin JS queda visible, que es lo
// seguro) y acá se oculta salvo cuando esa opción está elegida.
(function () {
    "use strict";

    const select = document.getElementById("fuente-datos");
    const campo = document.getElementById("fuente-otra-campo");
    if (!select || !campo) return;

    // El texto exacto de la opción que habilita el campo lo pone el template
    // desde FUENTE_DATOS_OTRA, para no repetirlo acá.
    const valorOtra = select.dataset.otra;

    function sincronizar() {
        campo.hidden = select.value !== valorOtra;
    }

    select.addEventListener("change", sincronizar);
    sincronizar();
})();
