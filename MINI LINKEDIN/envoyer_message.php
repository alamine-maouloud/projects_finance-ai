<?php
include('db.php');
session_start();


if (!isset($_SESSION['id_utilisateur'])) {
    echo "Vous devez être connecté pour envoyer un message.";
    exit;
}


$id_utilisateur = $_SESSION['id_utilisateur'];


$message = $_POST['message'];
$id_conversation = $_POST['id_conversation'];


$query = $pdo->prepare("INSERT INTO messages (id_conversation, id_utilisateur, message) VALUES (:id_conversation, :id_utilisateur, :message)");
$query->execute(['id_conversation' => $id_conversation, 'id_utilisateur' => $id_utilisateur, 'message' => $message]);


$query = $pdo->prepare("
    SELECT id_utilisateur1, id_utilisateur2
    FROM conversations
    WHERE id_conversation = :id_conversation
");
$query->execute(['id_conversation' => $id_conversation]);
$convers = $query->fetch();


$destinataire_id = ($convers['id_utilisateur1'] != $id_utilisateur) ? $convers['id_utilisateur1'] : $convers['id_utilisateur2'];


$notifQuery = $pdo->prepare("
    INSERT INTO notifications (id_utilisateur_envoyeur, id_utilisateur_receveur, type_notification, contenu_notification, status_notification)
    VALUES (:id_utilisateur_envoyeur, :id_utilisateur_receveur, 'message', 'Vous avez un nouveau message.', 'non vue')
");
$notifQuery->execute([
    'id_utilisateur_envoyeur' => $id_utilisateur, 
    'id_utilisateur_receveur' => $destinataire_id 
]);


header("Location: messagerie.php?id_conversation=" . $id_conversation);
exit();
?>
