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

    // Valida los campos del paso actual con la UI nativa del navegador: los
    // [required] vacíos y también los formatos mal escritos (type="email").
    //
    // El <form> lleva `novalidate` para que el navegador no reclame por campos
    // de pasos que todavía no se vieron; por eso la validación se hace paso a
    // paso desde acá. Un campo vacío sin [required] es válido y no molesta.
    function pasoValido() {
        const campos = steps[idx].querySelectorAll("input, select, textarea");
        for (const campo of campos) {
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

    // El submit siempre ocurre en el último paso: se valida antes de mandar,
    // si no un mail mal escrito se guardaría igual.
    form.addEventListener("submit", (e) => {
        if (!pasoValido()) e.preventDefault();
    });

    prevBtn.addEventListener("click", () => {
        if (idx > 0) {
            idx--;
            render(true);
        }
    });

    form.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        if (e.target.tagName === "TEXTAREA") return;

        // En los pasos que no son el último, Enter avanza en vez de mandar el
        // formulario: se carga entero sin tocar el mouse y sin enviar de más.
        if (idx !== last) {
            e.preventDefault();
            nextBtn.click();
        }
    });

    render(false);
})();
