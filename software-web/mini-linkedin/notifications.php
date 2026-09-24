<?php

include('db.php');

$id_utilisateur = $_SESSION['id_utilisateur'];
$query = $pdo->prepare("SELECT * FROM notifications WHERE id_utilisateur = :id_utilisateur ORDER BY date_notification DESC");
$query->execute(['id_utilisateur' => $id_utilisateur]);

$notifications = $query->fetchAll();

foreach ($notifications as $notification) {
    echo "<p>" . $notification['contenu_notification'] . " - " . $notification['date_notification'] . "</p>";
}
?>
