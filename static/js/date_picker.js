document.addEventListener("DOMContentLoaded", function() {
    setHoy();
});

function setHoy() {
    const hoy = new Date();
    document.getElementById("fecha_carga").value = formatDate(hoy);
}

function setAyer() {
    const ayer = new Date();
    ayer.setDate(ayer.getDate() - 1);
    document.getElementById("fecha_carga").value = formatDate(ayer);
}

function formatDate(d) {
    // Evita el problema de timezone que hace que traiga un día menos
    const offset = d.getTimezoneOffset();
    const local = new Date(d.getTime() - offset * 60000);
    return local.toISOString().split("T")[0];
}
