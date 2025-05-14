document.getElementById('checkbox').addEventListener('change', function() {
    var passwordField = document.getElementById('password');
    var eyeIcon = document.getElementById('eye');
    var eyeSlashIcon = document.getElementById('eye-slash');
    
    if (this.checked) {
        passwordField.type = 'text';
        eyeIcon.classList.remove('hide');
        eyeSlashIcon.classList.add('hide');
    } else {
        passwordField.type = 'password';
        eyeIcon.classList.add('hide');
        eyeSlashIcon.classList.remove('hide');
    }
});

// Ajout d'événements click pour les icônes
document.getElementById('eye').addEventListener('click', function() {
    var checkbox = document.getElementById('checkbox');
    checkbox.checked = !checkbox.checked; 
    checkbox.dispatchEvent(new Event('change')); 
});

document.getElementById('eye-slash').addEventListener('click', function() {
    var checkbox = document.getElementById('checkbox');
    checkbox.checked = !checkbox.checked; 
    checkbox.dispatchEvent(new Event('change')); 
});