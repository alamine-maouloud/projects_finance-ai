<?php


include('db.php');

session_start();
if (!isset($_SESSION['id_utilisateur'])) {
    echo "Vous devez être connecté pour refuser une demande.";
    exit;
}


$id_utilisateur2 = $_SESSION['id_utilisateur']; 
$id_utilisateur1 = $_POST['id_utilisateur1']; 


$query = $pdo->prepare("SELECT * FROM connexions WHERE id_utilisateur1 = :id_utilisateur1 AND id_utilisateur2 = :id_utilisateur2 AND statut_connexion = 'en attente'");
$query->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);

$request = $query->fetch();
if (!$request) {
    echo "Aucune demande en attente trouvée.";
    exit;
}


$stmt = $pdo->prepare("DELETE FROM connexions WHERE id_utilisateur1 = :id_utilisateur1 AND id_utilisateur2 = :id_utilisateur2");
$stmt->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);


header('Location: reseau.php');
exit();
?>