<?php

include('db.php');
session_start();


if (!isset($_SESSION['id_utilisateur'])) {
    header("Location: connexion.php");
    exit();
}

$id_utilisateur = $_SESSION['id_utilisateur'];


$query = $pdo->prepare("SELECT * FROM utilisateurs WHERE id_utilisateur = :id_utilisateur");
$query->execute(['id_utilisateur' => $id_utilisateur]);
$user = $query->fetch();


$query = $pdo->prepare("
    SELECT c.id_conversation, 
           CASE 
               WHEN c.id_utilisateur1 = :id_utilisateur THEN u2.prenom
               ELSE u1.prenom
           END AS prenom,
           CASE 
               WHEN c.id_utilisateur1 = :id_utilisateur THEN u2.nom
               ELSE u1.nom
           END AS nom,
           CASE 
               WHEN c.id_utilisateur1 = :id_utilisateur THEN u2.photo_profil
               ELSE u1.photo_profil
           END AS photo_profil
    FROM conversations c
    LEFT JOIN utilisateurs u1 ON c.id_utilisateur1 = u1.id_utilisateur
    LEFT JOIN utilisateurs u2 ON c.id_utilisateur2 = u2.id_utilisateur
    WHERE c.id_utilisateur1 = :id_utilisateur OR c.id_utilisateur2 = :id_utilisateur
    GROUP BY c.id_conversation
");
$query->execute(['id_utilisateur' => $id_utilisateur]);
$conversations = $query->fetchAll(PDO::FETCH_ASSOC);


$messages = [];
if (isset($_GET['id_conversation'])) {
    $id_conversation = $_GET['id_conversation'];
    $messageQuery = $pdo->prepare("
        SELECT m.id_message, m.message, m.date_message, u.prenom, u.nom
        FROM messages m
        JOIN utilisateurs u ON m.id_utilisateur = u.id_utilisateur
        WHERE m.id_conversation = :id_conversation
        ORDER BY m.date_message ASC
    ");
    $messageQuery->execute(['id_conversation' => $id_conversation]);
    $messages = $messageQuery->fetchAll(PDO::FETCH_ASSOC);

    
    $updateQuery = $pdo->prepare("
        UPDATE messages
        SET status_message = 'lu'
        WHERE id_conversation = :id_conversation
    ");
    $updateQuery->execute(['id_conversation' => $id_conversation]);

    
    $updateNotifQuery = $pdo->prepare("
    UPDATE notifications
    SET status_notification = 'vue'
    WHERE type_notification = 'message' AND id_utilisateur_receveur = :id_utilisateur
");
$updateNotifQuery->execute(['id_utilisateur' => $id_utilisateur]);

}


if (isset($_GET['action']) && $_GET['action'] == 'start_conversation' && isset($_GET['id_ami'])) {
    $id_ami = $_GET['id_ami'];

    
    $checkQuery = $pdo->prepare("
        SELECT id_conversation FROM conversations
        WHERE (id_utilisateur1 = :id_utilisateur AND id_utilisateur2 = :id_ami)
        OR (id_utilisateur1 = :id_ami AND id_utilisateur2 = :id_utilisateur)
    ");
    $checkQuery->execute(['id_utilisateur' => $id_utilisateur, 'id_ami' => $id_ami]);
    $conversation = $checkQuery->fetch();

    if (!$conversation) {
        
        $insertQuery = $pdo->prepare("
            INSERT INTO conversations (id_utilisateur1, id_utilisateur2)
            VALUES (:id_utilisateur1, :id_utilisateur2)
        ");
        $insertQuery->execute(['id_utilisateur1' => $id_utilisateur, 'id_utilisateur2' => $id_ami]);

        
        $conversation_id = $pdo->lastInsertId();
        header("Location: messagerie.php?id_conversation=" . $conversation_id);
        exit();
    } else {
        
        header("Location: messagerie.php?id_conversation=" . $conversation['id_conversation']);
        exit();
    }
}


if (isset($_GET['action']) && $_GET['action'] == 'new_conversation') {
    $query = $pdo->prepare("
        SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_profil
        FROM utilisateurs u
        JOIN connexions c ON (c.id_utilisateur1 = u.id_utilisateur OR c.id_utilisateur2 = u.id_utilisateur)
        WHERE (c.id_utilisateur1 = :id_utilisateur OR c.id_utilisateur2 = :id_utilisateur)
        AND u.id_utilisateur != :id_utilisateur
        AND NOT EXISTS (
            SELECT 1 FROM conversations
            WHERE (id_utilisateur1 = u.id_utilisateur AND id_utilisateur2 = :id_utilisateur)
            OR (id_utilisateur1 = :id_utilisateur AND id_utilisateur2 = u.id_utilisateur)
        )
    ");
    $query->execute(['id_utilisateur' => $id_utilisateur]);
    $amis = $query->fetchAll(PDO::FETCH_ASSOC);
}

?>

<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EceIn | Messagerie</title>
    <style>

        /* Ajoute ton propre style ici */
        .container { display: flex; }
        .conversations { width: 100%; padding: 10px; height: 100%; }
        .messages { width: 70%; padding: 10px; }
        .message { margin-bottom: 10px; }
        .message .sender { font-weight: bold; }
        .message .content { margin-left: 10px; }

        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500&display=swap');

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Poppins', sans-serif;
        }

        /* Fond général */
        body {
            background: white;
            margin: 0;
        }

        /* c'est la bar ou il ya les icones */
        nav .wrapper {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            padding: 0.3rem 4rem;
            background: white;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); /* Ajout d'une ombre */
            border: 2px solid black;
            border-radius: 13px;

        }

        header h1 {
          text-align: left;
          font-weight: bolder;
          font-size: 20px;
          color: blueviolet;
          margin: 20px 0;
        }

        header h1 span {
          color: white;
          background-color: darkviolet;
          border-radius: 5px;
          padding: 0 5px;
        }

        nav .wrapper .left,
        nav .wrapper .right {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 2rem;
        }

        nav .wrapper .left {
        padding-left: 3rem;
        display: flex;
        gap: 0.7rem;
        }

        nav .wrapper .logo i {
            font-size: 2.5rem;
            cursor: pointer;
            color: #0a66c2;
        }

        nav .wrapper .left .input {
        background: rgb(237, 245, 246);
        width: 100%;
        padding: 0.5rem 0.8rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-radius: 0.2rem;
        }

        nav .wrapper .left .input input[type='search'] {
            width: 15rem;
            border: none;
            background: transparent;
        }

        nav .wrapper .left .input input[type='search']::placeholder {
            font-size: 0.8rem;
            color: rgb(49, 49, 49);
            font-weight: 100;
        }

        nav .wrapper .left .input i {
            font-size: 0.8rem;
            color: blueviolet;
        }

        nav .wrapper .right .acceuil,
        nav .wrapper .right .reseau,
        nav .wrapper .right .emplois,
        nav .wrapper .right .messagerie,
        nav .wrapper .right .notification,
        nav .wrapper .right .moi,
        nav .wrapper .right .travail {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            cursor: pointer;
        }

        nav .wrapper .right .acceuil,
        nav .wrapper .right .reseau:hover,
        nav .wrapper .right .emplois:hover,
        nav .wrapper .right .messagerie:hover,
        nav .wrapper .right .notification:hover,
        nav .wrapper .right .moi .down:hover,
        nav .wrapper .right .travail .down:hover {
            color: blueviolet; /*reseau et messagerie*/
        }

        nav .wrapper .right .reseau,
        nav .wrapper .right .emplois,
        nav .wrapper .right .messagerie,
        nav .wrapper .right .notification,
        nav .wrapper .right .travail {
            color: blueviolet; /*reseau et messagerie*/
        }

        nav .wrapper .right .acceuil i,
        nav .wrapper .right .reseau i,
        nav .wrapper .right .emplois i,
        nav .wrapper .right .messagerie i,
        nav .wrapper .right .notification i {
            font-size: 1.2rem;
        }

        nav .wrapper .right .moi .down,
        nav .wrapper .right .travail .down {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.5rem;
            color: blueviolet;
        }

        nav .wrapper .right .moi i:first-child {
        background: blueviolet; /*de l'icone profil*/
        color: #fff;
        width: 1.5rem;
        height: 1.5rem;
        border-radius: 50%;
        font-size: 0.9rem;
        display: flex;
        justify-content: center;
        align-items: center;
        }

        .wrapper a {
        text-decoration: none;
        font-size: 0.7rem;
        width: 7rem;
        text-align: center;
        cursor: pointer;
        color: blueviolet; 
        }

        .wrapper a:hover {
            text-decoration: none;
        }

        /* La boîte contenant la liste des conversations et messages */

        .container {
            display: flex;
            gap: 2rem;
            padding: 5rem;
            background-color: white;
            margin-top: 1.0rem;
            border-radius: 3rem;
            box-shadow: 0 5px 8px rgba(0, 0, 0, 0.1);
        }

        .conversations {
            padding: 30px;
            border-radius: 10px;
            background-color: #f7eaff;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
            border: 2px solid black;
            height: 100%;  /* Hauteur fixe */
        }

        .conversations h3 {
            font-size: 1.2rem;
            font-weight: bold;
            color: blueviolet;
            margin-bottom: 20px;
        }

        .conversations a {
            text-decoration: none;
            color: black;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 30px;
            border: 1.5px solid black;
            border-radius: 13px;
            padding: 20px;

        }

        .conversations a:hover {
            background-color: rgba(0, 0, 0, 0.05);
            border-radius: 5px;
            display: flex; /* Utiliser flexbox pour centrer le contenu */
            align-items: center; /* Centrer verticalement */
            justify-content: flex-start; /* Centrer horizontalement vers la gauche */
            padding: 10px; /* Ajouter un peu de padding pour que le texte et l'image soient espacés correctement */
        }

        .conversations img {
            border-radius: 50%;
            width: 30px;
            height: 30px;
            margin-right: 10px; 
            margin-left: 10px;
        }

        .messages {
            flex: 2;
            padding: 20px;
            border-radius: 10px;
            background-color: #f7eaff;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
            border: 2px solid black;
        }

        .messages h3 {
            font-size: 1.2rem;
            font-weight: bold;
            color: blueviolet;
            margin-bottom: 20px;
        }

        .messages .message {
            background-color: white;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .messages .sender {
            font-weight: bold;
            color: black;
        }

        .messages .content {
            font-size: 1rem;
            color: #333;
        }

        .messages .date {
            font-size: 0.8rem;
            color: #777;
            text-align: right;
        }

        .messages form {
            margin-top: 20px;
        }

        .messages textarea {
            width: 100%;
            padding: 10px;
            border-radius: 10px;
            border: 1px solid #ddd;
            box-sizing: border-box;
            font-size: 1rem;
        }

        .messages button {
            background-color: blueviolet;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
        }

        .messages button:hover {
            background-color: darkviolet;
        }

        /* Footer */
        footer nav {
            width: 100%;
            max-width: 800px;
            display: flex;
            font-size: 9px;
            justify-content: center;
            gap: 15px;
            padding: 5px;
            margin: 100px auto 20px;
            flex-wrap: wrap;
        }

        footer nav a {
            text-decoration: none;
            color: rgba(0, 0, 0, 0.6);
            font-size: 10px;
            text-align: center;
            padding: 5px;
        }

        footer nav a:hover {
            color: blueviolet;
            font-weight: bold;
        }

        footer nav a.first span:first-of-type {
            font-weight: 800;
        }

        footer nav a.first span:last-of-type {
            font-weight: 800;
            color: white;
            background-color: rgba(0, 0, 0, 0.7);
            padding: 1px 3px;
            border-radius: 2px;
        }



        
        .selected-conversation {
            background-color: #f7eaff;
            border: 2px solid blueviolet;
            padding: 10px;
            border-radius: 10px;
            margin-bottom: 20px;
        }

        .selected-conversation h3 {
            font-size: 1.2rem;
            font-weight: bold;
            color: blueviolet;
        }

        .selected-conversation .sender {
            font-weight: bold;
            color: blueviolet;
        }

        .selected-conversation .content {
            font-size: 1rem;
            color: #333;
        }

        .selected-conversation .date {
            font-size: 0.8rem;
            color: #777;
            text-align: right;
        }
    </style>
    <link rel="stylesheet" href="css/styles.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css">
</head>
<body>
<nav>
      <div class="wrapper">
        <header><h1>EcE<span>in</span></h1></header>
        <div class="right">
          <div class="acceuil">
            <a href="accueil.php" class="accueil">
            <i class="fa-solid fa-house"></i>
            <h6>Accueil</h6>
            </a>
          </div>
          <div class="reseau">
            <a href="reseau.php" class="reseau">
            <i class="fa-solid fa-user-group"></i>
            <h6>Mon Réseau</h6>
            </a>
          </div>
          <div class="emplois">
            <a href="emploi.php" class="emploi">
            <i class="fa-solid fa-suitcase"></i>
            <h6>Emplois</h6>
            </a>
          </div>
          <div class="messagerie">
            <a href="messagerie.php" class="messagerie">
            <i class="fa-solid fa-message"></i>
            <h6>Messagerie</h6>
            </a>
          </div>
          <div class="moi">
            <a href="monprofil.php" class="moi">
            <i class="fa-solid fa-user"></i>
            <h6>Mon Profil</h6>
            </a>
          </div>
          
          
        </div>
      </div>
    </nav>


    <div class="container">
        <div class="conversations">
            <h3>Conversations</h3>
            <?php foreach ($conversations as $conv): ?>
                <a href="?id_conversation=<?= $conv['id_conversation']; ?>">
                    <div>
                        <img src="<?= $conv['photo_profil']; ?>" alt="Photo de profil" width="40">
                        <?= $conv['prenom'] . ' ' . $conv['nom']; ?>
                    </div>
                </a>
            <?php endforeach; ?>
        </div>

        
        <div class="messages">
            <h3>Messages</h3>
            <?php if (empty($messages)): ?>
                <p>Aucune conversation sélectionnée.</p>
            <?php else: ?>
                <?php foreach ($messages as $message): ?>
                    <div class="message">
                        <div class="sender"><?= htmlspecialchars($message['prenom']) . ' ' . htmlspecialchars($message['nom']); ?></div>
                        <div class="content"><?= nl2br(htmlspecialchars($message['message'])); ?></div>
                        <div class="date"><?= htmlspecialchars($message['date_message']); ?></div>
                    </div>
                <?php endforeach; ?>
            <?php endif; ?>

            
            <?php if (isset($id_conversation)): ?>
                <form method="POST" action="envoyer_message.php">
                    <textarea name="message" placeholder="Écrire un message..." required></textarea><br>
                    <input type="hidden" name="id_conversation" value="<?= htmlspecialchars($id_conversation); ?>">
                    <button type="submit">Envoyer le message</button>
                </form>
            <?php endif; ?>
        </div>

    </div>
<footer>
    <nav>
        <a href="#" class="first"><span>EcE<span>in</span></span> @2024 </a>
        <a href="#"> Accord d'utilisateur</a>
        <a href="#"> politique de confidentialité</a>
        <a href="#"> Directives communautaires</a>
        <a href="#"> Politiques en matière de cookies</a>
        <a href="#"> Droit d'auteur</a>
        <a href="#"> Partagez votre expérience</a>
        <a href="#"> Langues</a>
    </nav>
</footer>
</body>
</html>
