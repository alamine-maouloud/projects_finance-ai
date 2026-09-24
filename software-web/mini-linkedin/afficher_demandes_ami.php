<?php

include('db.php');


session_start();
if (!isset($_SESSION['id_utilisateur'])) {
    echo "Vous devez être connecté pour voir vos demandes.";
    exit;
}


$id_utilisateur2 = $_SESSION['id_utilisateur']; 


$query = $pdo->prepare("SELECT * FROM connexions WHERE id_utilisateur2 = :id_utilisateur2 AND statut_connexion = 'en attente'");
$query->execute(['id_utilisateur2' => $id_utilisateur2]);

$demandes = $query->fetchAll();

if (count($demandes) > 0) {
    foreach ($demandes as $demande) {
        
        $query = $pdo->prepare("SELECT pseudo FROM utilisateurs WHERE id_utilisateur = :id_utilisateur");
        $query->execute(['id_utilisateur' => $demande['id_utilisateur1']]);
        $utilisateur = $query->fetch();

        echo "<p>Demande d'ami de : " . $utilisateur['pseudo'] . "</p>";
        echo "<form method='POST' action='accepter_demande_ami.php'>
                <input type='hidden' name='id_utilisateur1' value='" . $demande['id_utilisateur1'] . "'>
                <button type='submit'>Accepter</button>
              </form>";
        echo "<form method='POST' action='refuser_demande_ami.php'>
                <input type='hidden' name='id_utilisateur1' value='" . $demande['id_utilisateur1'] . "'>
                <button type='submit'>Refuser</button>
              </form>";
    }
} else {
    echo "Aucune demande d'ami en attente.";
}
?>
