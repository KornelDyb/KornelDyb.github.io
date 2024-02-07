

console.log("Hello World")

function isElementInViewport(elem) {
    var rect = elem.getBoundingClientRect();

    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Funkcja, która dodaje klasę z animacją do elementu, gdy jest widoczny na ekranie
function addAnimationIfVisible() {
    var elements = document.querySelectorAll('.find-animation');

    elements.forEach(function(elem) {
        if (isElementInViewport(elem)) {
            elem.classList.add('visible');
        }
    });
}

// Sprawdź, czy elementy są widoczne na początku
addAnimationIfVisible();

// Sprawdź, czy elementy są widoczne podczas przewijania
window.addEventListener('scroll', function() {
    addAnimationIfVisible();
});

function skopiujEmail() {
    var email = 'kornel.dybalski@wp.pl';

    navigator.clipboard.writeText(email)
        .then(() => {
            console.log('Adres e-mail został skopiowany do schowka: ' + email);
            alert('Adres e-mail został skopiowany do schowka: ' + email);
        })
        .catch(err => {
            console.error('Wystąpił błąd podczas kopiowania adresu e-mail do schowka: ', err);
            alert('Wystąpił błąd podczas kopiowania adresu e-mail do schowka. Spróbuj ponownie.');
        });
}