// Wizard del formulario de ingreso: navega por pasos sin scrollear la página.
// Todos los pasos viven en un mismo <form>; solo se muestra uno a la vez y el
// submit real ocurre en el último paso.
(function () {
    "use strict";

    const form = document.querySelector("form.wizard");
    if (!form) return;

    const steps = Array.from(form.querySelectorAll(".wizard-step"));
    const prevBtn = form.querySelector("[data-prev]");
    const nextBtn = form.querySelector("[data-next]");
    const submitBtn = form.querySelector(".btn-submit");
    const currentOut = form.querySelector("[data-current]");
    const totalOut = form.querySelector("[data-total]");
    const dots = Array.from(document.querySelectorAll(".stepper li"));

    let idx = 0;
    const last = steps.length - 1;
    if (totalOut) totalOut.textContent = steps.length;

    function render(foco) {
        steps.forEach((s, i) => (s.hidden = i !== idx));
        dots.forEach((d, i) => {
            d.classList.toggle("is-current", i === idx);
            d.classList.toggle("is-done", i < idx);
        });
        prevBtn.disabled = idx === 0;
        nextBtn.hidden = idx === last;
        submitBtn.hidden = idx !== last;
        if (currentOut) currentOut.textContent = idx + 1;
        // Autofoco en el primer campo del paso para cargar sin usar el mouse.
        if (foco) {
            const primero = steps[idx].querySelector("input, select, textarea");
            if (primero) primero.focus({ preventScroll: true });
        }
    }

    // Valida los campos con [required] del paso actual usando la UI nativa.
    function pasoValido() {
        const requeridos = steps[idx].querySelectorAll("[required]");
        for (const campo of requeridos) {
            if (!campo.reportValidity()) {
                campo.focus();
                return false;
            }
        }
        return true;
    }

    nextBtn.addEventListener("click", () => {
        if (!pasoValido()) return;
        if (idx < last) {
            idx++;
            render(true);
        }
    });

    prevBtn.addEventListener("click", () => {
        if (idx > 0) {
            idx--;
            render(true);
        }
    });

    form.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        const t = e.target;
        if (t.tagName === "TEXTAREA") return;

        // Dentro de la tabla de monitoreo: Enter baja a la celda de abajo
        // (misma columna), como en una planilla. No cambia de página.
        const celda = t.closest(".med-table td");
        if (celda) {
            e.preventDefault();
            const fila = celda.parentElement;
            const siguienteFila = fila.nextElementSibling;
            if (siguienteFila && siguienteFila.cells[celda.cellIndex]) {
                const sig = siguienteFila.cells[celda.cellIndex].querySelector("input");
                if (sig) sig.focus();
            }
            return;
        }

        // En el resto de los pasos (no el último) Enter avanza en vez de mandar.
        if (idx !== last) {
            e.preventDefault();
            nextBtn.click();
        }
    });

    render(false);
})();
