<?php

include('db.php');
session_start();


if (!isset($_SESSION['id_utilisateur'])) {
    header('Location: connexion.html');
    exit();
}


if (isset($_GET['id_offre'])) {
    $id_offre = (int)$_GET['id_offre'];
    $id_utilisateur = $_SESSION['id_utilisateur']; 

    
    $query = "SELECT * FROM offres_emploi WHERE id_offre = $id_offre";
    $result = $db->query($query);

    if ($result->num_rows > 0) {
        
        $query = "INSERT INTO candidatures (id_utilisateur, id_offre, date_candidature) 
                  VALUES ($id_utilisateur, $id_offre, NOW())";

        if ($db->query($query) === TRUE) {
            
            header('Location: emploi.php');
            exit;
        } else {
            echo "Erreur lors de la candidature : " . $db->error;
        }
    } else {
        echo "L'offre n'existe pas.";
    }
} else {
    echo "Aucune offre spécifiée.";
}
?>
