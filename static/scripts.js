document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function (event) {
            const title = document.getElementById('title')?.value;
            const summary = document.getElementById('summary')?.value;

            if (title && summary && (!title.trim() || !summary.trim())) {
                alert('Title and Summary are required.');
                event.preventDefault();
            }
        });
    }
});