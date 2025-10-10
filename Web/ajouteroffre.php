<?php

include('db.php');
session_start();


if (isset($_SESSION['role']) && $_SESSION['role'] === 'employeur') {

    if ($_SERVER['REQUEST_METHOD'] === 'POST') {

        $type_emploi = $db->real_escape_string($_POST['type_emploi']);
        $lieu_emploi = $db->real_escape_string($_POST['lieu_emploi']);
        $description_offre = $db->real_escape_string($_POST['description_offre']);
        $job_requirements = $db->real_escape_string($_POST['job_requirements']);
        $date_expiration = $db->real_escape_string($_POST['date_expiration']);


        $query = "INSERT INTO offres_emploi (type_emploi, lieu_emploi, description_offre, job_requirements, date_expiration, date_offre) 
                  VALUES ('$type_emploi', '$lieu_emploi', '$description_offre', '$job_requirements', '$date_expiration', NOW())";

        if ($db->query($query) === TRUE) {

            header('Location: emploi.php');
            exit;
        } else {
            echo "Erreur lors de l'ajout de l'offre : " . $db->error;
        }
    }
} else {
    echo "Accès interdit, vous devez être un employeur pour ajouter une offre.";
}
?>
