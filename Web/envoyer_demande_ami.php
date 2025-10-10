<?php

include('db.php');


session_start();
if (!isset($_SESSION['id_utilisateur'])) {
    echo "Vous devez être connecté pour envoyer une demande.";
    exit;
}

$id_utilisateur1 = $_SESSION['id_utilisateur']; 
$id_utilisateur2 = $_POST['id_utilisateur2']; 


if ($id_utilisateur1 == $id_utilisateur2) {
    header('Location: reseau.php');
    exit();
}


$query = $pdo->prepare("SELECT * FROM connexions WHERE (id_utilisateur1 = :id_utilisateur1 AND id_utilisateur2 = :id_utilisateur2) OR (id_utilisateur1 = :id_utilisateur2 AND id_utilisateur2 = :id_utilisateur1)");
$query->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);

$exist = $query->fetch();
if ($exist) {
    header('Location: reseau.php');
    exit();
}


$stmt = $pdo->prepare("INSERT INTO connexions (id_utilisateur1, id_utilisateur2, statut_connexion) VALUES (:id_utilisateur1, :id_utilisateur2, 'en attente')");
$stmt->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);


header('Location: reseau.php');
exit();
?>