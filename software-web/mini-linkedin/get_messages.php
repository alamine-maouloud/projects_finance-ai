<?php

include('db.php');


$id_utilisateur1 = $_SESSION['id_utilisateur']; 
$id_utilisateur2 = $_GET['id_utilisateur2']; 


$query = $pdo->prepare("SELECT * FROM conversations WHERE (id_utilisateur1 = :id_utilisateur1 AND id_utilisateur2 = :id_utilisateur2) OR (id_utilisateur1 = :id_utilisateur2 AND id_utilisateur2 = :id_utilisateur1)");
$query->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);

$conversation = $query->fetch();
if (!$conversation) {
    echo "Aucune conversation trouvée.";
    exit;
}

$conversation_id = $conversation['id_conversation'];


$query = $pdo->prepare("SELECT * FROM messages WHERE id_conversation = :id_conversation ORDER BY date_message ASC");
$query->execute(['id_conversation' => $conversation_id]);

$messages = $query->fetchAll();

foreach ($messages as $message) {
    echo "<p><strong>" . $message['id_utilisateur'] . ":</strong> " . $message['message'] . "</p>";
}
?>
