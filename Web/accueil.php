<?php
session_start();
include('db.php');

if (!isset($_SESSION['id_utilisateur'])) {
    header('Location: connexion.html');
    exit;
}

$id_utilisateur = $_SESSION['id_utilisateur'];
$query = $pdo->prepare("SELECT * FROM utilisateurs WHERE id_utilisateur = :id_utilisateur");
$query->execute(['id_utilisateur' => $id_utilisateur]);
$user = $query->fetch();


$friendsQuery = $pdo->prepare("SELECT COUNT(*) AS nombre_amis FROM connexions WHERE (id_utilisateur1 = :id_utilisateur OR id_utilisateur2 = :id_utilisateur) AND statut_connexion = 'acceptée'");
$friendsQuery->execute(['id_utilisateur' => $id_utilisateur]);
$nombre_amis = $friendsQuery->fetchColumn();

$requestsQuery = $pdo->prepare("SELECT COUNT(*) AS nombre_demandes FROM connexions WHERE id_utilisateur2 = :id_utilisateur AND statut_connexion = 'en attente'");
$requestsQuery->execute(['id_utilisateur' => $id_utilisateur]);
$nombre_demandes = $requestsQuery->fetchColumn();

$notifQuery = $pdo->prepare("
SELECT n.id_notification,
       n.contenu_notification, 
       n.date_notification, 
       u.prenom AS notif_prenom, 
       u.nom AS notif_nom,
       MAX(c.id_conversation) AS id_conversation
FROM notifications n
JOIN utilisateurs u ON n.id_utilisateur_envoyeur = u.id_utilisateur
LEFT JOIN conversations c ON (n.id_utilisateur_receveur = c.id_utilisateur1 OR n.id_utilisateur_receveur = c.id_utilisateur2)
WHERE n.status_notification = 'non vue' 
  AND n.type_notification = 'message' 
  AND n.id_utilisateur_receveur = :id_utilisateur
GROUP BY n.id_notification
ORDER BY n.date_notification DESC
");
$notifQuery->execute(['id_utilisateur' => $id_utilisateur]);
$notifications = $notifQuery->fetchAll(PDO::FETCH_ASSOC);

//----------------------------------------------------------------------------------------------------------------------------------------

$postsQuery = $pdo->prepare("
    SELECT p.id_publication, p.contenu, p.date_publication, u.prenom, u.nom, u.photo_profil 
    FROM publications p
    JOIN utilisateurs u ON p.id_utilisateur = u.id_utilisateur
    WHERE p.id_utilisateur IN (
        SELECT id_utilisateur1 FROM connexions WHERE id_utilisateur2 = :id_utilisateur AND statut_connexion = 'acceptée'
        UNION 
        SELECT id_utilisateur2 FROM connexions WHERE id_utilisateur1 = :id_utilisateur AND statut_connexion = 'acceptée'
    )
    ORDER BY p.date_publication DESC
");
$postsQuery->execute(['id_utilisateur' => $id_utilisateur]);
$posts = $postsQuery->fetchAll(PDO::FETCH_ASSOC);


$type = $_POST['type'] ?? 'texte';  

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    
    $type = $_POST['type'] ?? 'texte';
    $contenu = $_POST['contenu'] ?? null;
    $file = $_FILES['file'] ?? null;

    if ($type && $contenu) {
        
        $query = $pdo->prepare("INSERT INTO publications (id_utilisateur, type, contenu, date_publication) VALUES (:id_utilisateur, :type, :contenu, NOW())");
        $query->execute([
            'id_utilisateur' => $id_utilisateur,
            'type' => $type,
            'contenu' => $contenu
        ]);

        
        if ($file && in_array($type, ['photo', 'video', 'cv'])) {
            $targetDir = "uploads/";
            $targetFile = $targetDir . basename($file["name"]);

            
            if (move_uploaded_file($file["tmp_name"], $targetFile)) {
                
                $updateQuery = $pdo->prepare("UPDATE publications SET contenu = :contenu, date_publication = NOW() WHERE id_utilisateur = :id_utilisateur ORDER BY date_publication DESC LIMIT 1");
                $updateQuery->execute(['contenu' => $targetFile, 'id_utilisateur' => $id_utilisateur]);
            }
        }

        header("Location: accueil.php");
        exit;
    }
}

?>


<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8" />
    <meta http-equiv="X-UA-Compatible" content="IE=edge" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css" />
    <title>EceIn | Accueil</title>
</head>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500&display=swap');

    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
        font-family: 'Poppins', sans-serif;
    }

    nav .wrapper {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        padding: 0.3rem 4rem;
        background: white;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
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

    .general-container {
    width: 90%; /* La largeur de la boîte générale */
    margin: 20px auto; /* Centrer la boîte horizontalement et un petit espace en haut et en bas */
    padding: 20px; /* Espacement interne */
    background-color: white; /* Fond coloré pour la boîte */
    border-radius: 10px; /* Coins arrondis */
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); /* Ombre douce autour de la boîte */
    border: 2px solid black; /* Bordure noire autour de la boîte */
    height: 550px;
    }

    .container {
    display: grid;
    grid-template-columns: 15% 65% 18%;
    gap: 1.0rem;
    width: 95%;
    margin: 0.2rem auto;
    position: center;
    }

    /*c'est le cote profil*/
    aside .sidebar {
    background: #f7eaff;
    width: 100%;
    height: 62vh;
    position: relative;
    border-radius: 0.8rem;
    overflow: hidden;
    border: 2px solid black;
    }

    .sidebar .top {
    width: 100%;
    height: 8vh;
    background-color: rgb(82, 92, 105);
    position: absolute;
    }

    .sidebar img {
    position: relative;
    left: 50%;
    transform: translate(-50%);
    top: 3%;
    border-radius: 50%;
    width: 4.0rem;
    height: 4.0rem;
    border: 2px solid black;
    }

    .sidebar .profile a:hover {
    text-decoration: none;
    }

    aside .sidebar .profile {
    position: relative;
    text-align: left;
    top: 5%;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    }

    .sidebar .profile a {
    text-decoration: none;
    color: black;
    }

    .sidebar .profile small {
    font-size: 0.7rem;
    color: black;
    }

    /*cest le nombre d'amis ..*/
    .sidebar .vue .vues h6 {
    color: black;
    font-weight: 100;
    }

    .sidebar .vue .vues a {
    color: rgb(39, 39, 219);
    text-decoration: none;
    font-size: 0.8rem;
    }

    .sidebar .vue .vues {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.2rem 0.5rem;
    cursor: pointer;
    font-weight: 100;
    padding-bottom: 0.4rem;
    }

    .sidebar .vue .vues:hover {
        background-color: rgb(223, 223, 223);
    }

    .sidebar .vue {
    position: relative;
    display: flex;
    flex-direction: column;
    top: 3%;
    }

    .sidebar .premium {
    position: relative;
    top: 7%;
    }

    .sidebar .premium h6 {
        color: black;
        font-weight: 100;
        margin-left: 0.2rem;
    }

    .sidebar .premium a {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        text-decoration: none;
        margin-left: 1rem;
        font-size: 0.8rem;
        color: black;
    }

    .sidebar .premium a i {
        color: rgb(211, 211, 33);
    }

    hr#premium,
    hr#vue,
    hr#profile {
        margin: 0.5rem 0 0 0;
    }

    /*mes elements*/

    .items {
    position: relative;
    top: 4%;
    display: flex;
    gap: 0.5rem;
    margin: 0.4rem 0 0 1rem;
    color: black;
    cursor: pointer;
    }

    aside .emplois_recent {
    background: #fff;
    margin-top: 0.5rem;
    width: 100%;
    height: 68vh;
    position: relative;
    border-radius: 0.8rem;
    overflow: hidden;
    }

    aside .emplois_recent .recent {
    margin: 1rem;
    }

    aside .emplois_recent .recent h6 {
        font-weight: 100;
    }

    aside .emplois_recent .recent .un {
        display: flex;
        align-items: center;
        margin-top: 0.7rem;
        gap: 0.5rem;
        color: rgb(83, 83, 83);
    }

    aside .emplois_recent .recent .un i {
        font-size: 0.8rem;
    }

    aside .recent_jobs .groupes {
    margin: 2rem 0 0 1rem;
    }

    aside .emplois_recents .groupes h5 {
        color: #0a66c2;
        font-size: 0.7rem;
    }

    aside .recent_jobs .groups .deux {
        display: flex;
        align-items: center;
        margin-top: 0.7rem;
        gap: 0.5rem;
        color: rgb(83, 83, 83);
    }

    .groups .show {
        display: flex;
        margin-top: 1rem;
        gap: 0.5rem;
        color: gray;
    }

    aside .evenement {
        display: flex;
        justify-content: space-between;
        margin: 2rem 1rem 0 1rem;
    }

    aside .evenement h6:hover {
        text-decoration: underline;
        cursor: pointer;
    }

    aside .evenement i {
        color: gray;
        cursor: pointer;
    }

    .discover {
    text-align: center;
    margin: 2rem 0 0 0;
    border-top: 1px solid rgb(144, 144, 144);
    padding-top: 1rem;
    }

    .discover a {
        text-decoration: none;
        color: gray;
    }

    /* le prénom et le nom */
    .profil a {
        font-size: 0.6rem;  /* Taille de la police du nom */
        font-weight: bold;  /* Mettre en gras */
        color: blueviolet;  /* Couleur du texte */
        text-decoration: none;  /* Enlève le soulignement */
        justify-content: center;
        display: flex;
    }


    /*case au milieu*/
    main {
    background: #f7eaff;
    border-radius: 0.8rem;
    height: 62vh;
    position: relative;
    border: 2px solid black;
    }

    main #close {
    position: absolute;
    right: 2rem;
    top: 1rem;
    color: white;
    }

    main .evenement {
    margin: 1.5rem 0 0 1rem;
    }

    main .evenement h3 {
        font-weight: 200;
    }

    main .box {
        width: 95%;
        overflow: hidden;
        margin: 0.6rem auto;
        border-radius: 0.8rem;
    }

    main .box img {
    width: 100%;
    }

    main .box .content {
        padding: 0.5rem 1rem;
    }

    main .box .content p {
        font-weight: 100;
    }

    /*bouton en savoir plus*/
    main .box .btn {
    border: none;
    background: blueviolet;
    padding: 0.3rem 1rem;
    border-radius: 5rem;
    margin: 0.3rem 1rem;
    color: white;
    cursor: pointer;
    font-size: 0.5rem;
    transition: 0.3s all ease;
    }

    main .box .btn:hover {
    background: blueviolet;
    }

    /*c'est la case ou ya la case commencez une pub*/
    main .media {
    background: white;
    height: 25vh;
    margin-top: 1rem;
    border-radius: 0.5rem;
    }

    main .media .recherche {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    }

    main .media .recherche img {
    width: 2.9rem;
    height: 2.9rem;
    border-radius: 50%;
    cursor: pointer;
    }

    main .media .recherche input {
    border-radius: 5rem;
    border: 1px solid white;
    width: 100%; /* Utilisez 100% pour qu'il prenne toute la largeur du conteneur */
    padding: 0 1.0rem;
    cursor: pointer;
    transition: 0.3s all ease;
    box-sizing: border-box; /* Cela assure que le padding est inclus dans la largeur de l'élément */
    border: 1px solid black;
    }

    main .media .recherche input:hover {
    background: rgb(233, 233, 233);
    }

    main .media .posts {
    display: flex;
    justify-content: space-between;
    margin: 0 6rem;
    box-sizing: border-box; 
    background-color: white;
    }

    main .media .posts .post {
        display: flex;
        gap: 1rem;
        padding: 0.0rem 0.1rem;
        cursor: pointer;
        opacity: 0.5;
    }

    main .media .posts .post h5 {
        font-weight: 200;
        font-size: 0.5rem;
        color: black;
    }

    main .media .posts .post:nth-child(1) i {
        color: blueviolet;
    }

    main .media .posts .post:nth-child(2) i {
        color: blueviolet;
    }

    main .media .posts .post:nth-child(3) i {
        color: blueviolet;
    }

    main .media .posts .post:nth-child(4) i {
        color: blueviolet;
    }

    main .media .posts .post:hover {
        background: rgb(235, 235, 235);
        border-radius: 0.2rem;
    }

    /*notification*/
    .right_side {
    background: #f7eaff;
    border-radius: 0.8rem;
    height: 62vh;
    border: 2px solid black;
    color: blueviolet;
    }

    .right_side .news {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 1rem;
    }

    .right_side .news h4 {
        font-weight: 400;
    }

    .right_side .latest_news {
    padding: 0.5rem 1rem;
    cursor: pointer;
    transition: 0.2s all ease;
    }

    .right_side .latest_news:hover {
        background: rgb(231, 231, 231);
    }

    .right_side .latest_news .un {
        display: flex;
        align-items: center;
        gap: 1.5rem;
    }

    .right_side .latest_news .un h5 {
        font-weight: 500;
    }

    .right_side .latest_news .un i {
        font-size: 0.5rem;
        color: black;
    }

    .right_side .latest_news .deux {
        margin: 0 1.9rem;
        font-size: 0.8rem;
        color: black;
    }

    .right_side .afficher {
        display: flex;
        gap: 0.5rem;
        color: blueviolet;
        align-items: center;
        margin: 1rem;
        cursor: pointer;
    }

    .right_side .afficher h5 {
        font-weight: 400;
    }

    /* === Carrousel Centré avec un seul profil visible === */
    .carousel-track-container {
      width: 300px; /* Largeur d'un profil */
      margin: 0 auto; /* Centré horizontalement */
      overflow: hidden; /* Masquer les profils hors du cadre */
    }

    .carousel-track {
      display: flex;
      transition: transform 0.3s ease-in-out; /* Animation fluide pour le défilement */
    }

    .carousel-card {
      flex: 0 0 100%; /* Chaque profil occupe 100% de la largeur du conteneur */
      list-style: none;
      text-align: center;
      margin: 0; /* Pas d’espacement entre les cartes */
    }

    .carousel-card img {
      width: 150px;
      height: 150px;
      border-radius: 50%; /* Cercle pour les photos */
      margin-bottom: 1rem;
    }

    .carousel-card h3 {
      margin: 0.5rem 0;
      font-size: 1.2rem;
      color: #0a66c2;
    }

    .carousel-card p {
      font-size: 0.9rem;
      color: gray;
    }

    /* Boutons de navigation */
    .carousel-btn {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      background-color: #0a66c2; /* Bleu foncé */
      color: white;
      border: none;
      font-size: 1.5rem;
      cursor: pointer;
      padding: 0.5rem 1rem;
      border-radius: 5px;
      box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2); /* Ombre légère */
    }

    .carousel-btn:hover {
      background-color: #0956a3; /* Bouton bleu légèrement plus foncé au survol */
    }

    .carousel-btn.left-btn {
      left: 10px; /* Position à gauche */
    }

    .carousel-btn.right-btn {
      right: 10px; /* Position à droite */
    }

    .create_post {
        background: #fff;
        border-radius: 0.8rem;
        padding: 1rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .create_post textarea {
        width: 100%;
        height: 80px;
        padding: 10px;
        font-size: 1rem;
        border: 1px solid gray;
        border-radius: 0.5rem;
        resize: none;
        background: rgb(250, 250, 250);
    }

    .create_post textarea:focus {
        border-color: #0a66c2;
        outline: none;
    }

    .create_post input[type="file"] {
        font-size: 0.9rem;
        color: gray;
    }

    .create_post button {
        background: #0a66c2;
        color: #fff;
        padding: 10px;
        border: none;
        border-radius: 5rem;
        cursor: pointer;
        transition: background 0.3s ease;
    }

    .create_post button:hover {
        background: #0956a3;
    }

    .posts_section {
        background: #fff;
        border-radius: 0.8rem;
        padding: 1rem;
        margin-top: 1rem;
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
    }

    .post {
        background: rgb(245, 245, 245);
        padding: 1rem;
        border-radius: 0.8rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .post img {
        width: 100%;
        border-radius: 0.5rem;
        margin-top: 0.5rem;
    }

    .post h5 {
        font-size: 1rem;
        font-weight: bold;
        color: #0a66c2;
    }

    .post p {
        font-size: 0.9rem;
        line-height: 1.5;
        color: #333;
    }

    .post small {
        font-size: 0.8rem;
        color: gray;
    }

    footer nav {
      width: 100%;
      max-width: 800px; /* Ajustez la largeur maximale si nécessaire */
      display: flex;
      font-size: 9px;
      justify-content: center; /* Centre tout le contenu */
      gap: 15px; /* Ajoute un espacement uniforme entre les éléments */
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
    .post img {
    width: 50px;  
    height: 50px;  
    object-fit: cover; 
    border-radius: 50%; 
    }

</style>
<body>
    <nav>
        <div class="wrapper">
            <header><h1>EcE<span>in</span></h1></header>
            <div class="right">
                <div class="acceuil"><a href="#" class="accueil"><i class="fa-solid fa-house"></i><h6>Accueil</h6></a></div>
                <div class="reseau"><a href="reseau.php" class="reseau"><i class="fa-solid fa-user-group"></i><h6>Mon Réseau</h6></a></div>
                <div class="emplois"><a href="emploi.php" class="emploi"><i class="fa-solid fa-suitcase"></i><h6>Emplois</h6></a></div>
                <div class="messagerie"><a href="messagerie.php" class="messagerie"><i class="fa-solid fa-message"></i><h6>Messagerie</h6></a></div>
                <div class="moi"><a href="monprofil.php" class="moi"><i class="fa-solid fa-user"></i><h6>Mon Profil</h6></a></div>
            </div>
        </div>
    </nav>

    <div class="general-container">
    <div class="container">
        <aside>
            <div class="sidebar">
                <img src="<?php echo $user['photo_profil']; ?>" alt="Profil de <?php echo $user['prenom'] . ' ' . $user['nom']; ?>" />
                <br><br>
                <div class="profil">
                    <a href="#"><?php echo $user['prenom'] . ' ' . $user['nom']; ?></a><br>
                    <small><?php echo $user['description']; ?></small>
                    <hr id="profile">
                </div>
                <div class="vue">
                    <div class="vues"><h6>Nombre d'amis</h6><h6><?php echo $nombre_amis; ?></h6></div>
                    <div class="vues"><h6>Demandes d'ami en attente</h6><h6><?php echo $nombre_demandes; ?></h6></div>
                    <hr id="vue">
                </div>
                <div class="items"><i class="fa-solid fa-bookmark"></i><h6>Mes Éléments</h6></div>
            </div>
        </aside>

        <main>
            <div class="create_post">
                <form action="accueil.php" method="POST" enctype="multipart/form-data">
                    <textarea name="contenu" placeholder="Commencez une publication..."></textarea><br><br>
                    <div>
                        <button type="submit" name="type" value="texte"><i class="fa-solid fa-pen"></i> Rédiger un post</button>
                        <button type="submit" name="type" value="photo"><i class="fa-solid fa-image"></i> Photo</button>
                        <button type="submit" name="type" value="video"><i class="fa-solid fa-video"></i> Vidéo</button>
                        <button type="submit" name="type" value="cv"><i class="fa-solid fa-briefcase"></i> CV</button>
                        <input type="file" name="file" />
                        <button type="submit" name="publish">Publier</button> 
                    </div>
                </form>
            </div>

            <div class="posts_section">
                <?php foreach ($posts as $post): ?>
                    <div class="post">
                        <img src="<?php echo $post['photo_profil']; ?>" alt="User Profile" />
                        <h5><?php echo htmlspecialchars($post['prenom'] . ' ' . $post['nom']); ?></h5>
                        <p><?php echo htmlspecialchars($post['contenu']); ?></p>
                        <small><?php echo $post['date_publication']; ?></small>
                    </div>
                <?php endforeach; ?>
            </div>
        </main>

        <div class="right_side">
            <div class="news"><h4>Notifications</h4><i class="fa-solid fa-circle-info"></i></div>
            <div class="latest_news">
    <?php if (empty($notifications)): ?>
        <p>Aucune notification pour le moment.</p>
    <?php else: ?>
        <?php foreach ($notifications as $notif): ?>
            <div class="notification-item">
                <i class="fa-solid fa-circle"></i>
                <h5>
                    Message de <?php echo htmlspecialchars($notif['notif_prenom'] ?? 'Inconnu') . ' ' . htmlspecialchars($notif['notif_nom'] ?? 'Inconnu'); ?>
                </h5>
                <small>Envoyé le <?php echo htmlspecialchars($notif['date_notification'] ?? 'Date inconnue'); ?></small>
                
                <a href="messagerie.php?id_conversation=<?php echo htmlspecialchars($notif['id_conversation']); ?>" class="message-link">Voir la conversation</a>
            </div>
        <?php endforeach; ?>
    <?php endif; ?>
</div>
            <div class="afficher"><h5>Afficher plus</h5><i class="fa-solid fa-angle-down"></i></div>
        </div>
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
