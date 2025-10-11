<?php

session_start();


if (!isset($_SESSION['id_utilisateur'])) {
    header('Location: connexion.html');
    exit();
}

include('db.php');


$id_utilisateur = $_SESSION['id_utilisateur'];


function getPhotoProfil($photo_path) {
    return $photo_path ?: 'default_avatar.png';
}


$suggestionsQuery = $pdo->prepare("
    SELECT id_utilisateur, prenom, nom, photo_profil, statut 
    FROM utilisateurs 
    WHERE id_utilisateur != :id_utilisateur
    AND id_utilisateur NOT IN (
        SELECT id_utilisateur1 FROM connexions WHERE id_utilisateur2 = :id_utilisateur AND statut_connexion = 'acceptée'
        UNION
        SELECT id_utilisateur2 FROM connexions WHERE id_utilisateur1 = :id_utilisateur AND statut_connexion = 'acceptée'
    )
    LIMIT 5
");
$suggestionsQuery->execute(['id_utilisateur' => $id_utilisateur]);
$suggestions = $suggestionsQuery->fetchAll(PDO::FETCH_ASSOC);


$friendsQuery = $pdo->prepare("
    SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_profil, u.statut 
    FROM connexions c
    JOIN utilisateurs u ON (c.id_utilisateur2 = u.id_utilisateur OR c.id_utilisateur1 = u.id_utilisateur)
    WHERE (c.id_utilisateur1 = :id_utilisateur OR c.id_utilisateur2 = :id_utilisateur) 
    AND c.statut_connexion = 'acceptée' 
    AND u.id_utilisateur != :id_utilisateur
");
$friendsQuery->execute(['id_utilisateur' => $id_utilisateur]);
$friends = $friendsQuery->fetchAll(PDO::FETCH_ASSOC);


$demandesQuery = $pdo->prepare("
    SELECT u.id_utilisateur, u.prenom, u.nom, u.photo_profil 
    FROM connexions c
    JOIN utilisateurs u ON c.id_utilisateur1 = u.id_utilisateur
    WHERE c.id_utilisateur2 = :id_utilisateur AND c.statut_connexion = 'en attente'
");
$demandesQuery->execute(['id_utilisateur' => $id_utilisateur]);
$demandes = $demandesQuery->fetchAll(PDO::FETCH_ASSOC);


if (isset($_POST['ajouter_ami'])) {
    $id_utilisateur1 = $_SESSION['id_utilisateur']; 
    $id_utilisateur2 = $_POST['id_utilisateur2'];   

    
    $query = $pdo->prepare("SELECT * FROM connexions 
                            WHERE (id_utilisateur1 = :id_utilisateur1 AND id_utilisateur2 = :id_utilisateur2) 
                            OR (id_utilisateur1 = :id_utilisateur2 AND id_utilisateur2 = :id_utilisateur1) 
                            AND statut_connexion = 'en attente'");
    $query->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);
    $existingRequest = $query->fetch();

    
    if ($existingRequest) {
        echo "Vous avez déjà envoyé une demande à cet utilisateur.";
        exit;
    }

    
    $query = $pdo->prepare("INSERT INTO connexions (id_utilisateur1, id_utilisateur2, statut_connexion) 
                            VALUES (:id_utilisateur1, :id_utilisateur2, 'en attente')");
    $query->execute(['id_utilisateur1' => $id_utilisateur1, 'id_utilisateur2' => $id_utilisateur2]);


    header('Location: reseau.php');
    exit();
}


?>

<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EceIn | Réseau</title>
    <link rel="stylesheet" href="styles.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css">
</head>
<style>

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

    /*le bloc au milieu qui contient les blocs amis*/
    .container {
    display: grid;
    grid-template-columns: 20% 52% 28%;
    gap: 1.4rem;
    width: 85%;
    margin: 2rem auto;
    padding: 2rem;
    border-radius: 1rem;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    border: 2px solid black;
    background-color: white;
    }

    /*sugggestion d'amis*/

    aside .sidebar {
    background: #f7eaff;
    width: 100%;
    height: 60vh;
    position: relative;
    border-radius: 0.8rem;
    overflow: hidden;
    box-shadow: 1 2px 4px rgba(0, 0, 0, 0.1);
    border: 2px solid black;
    color: blueviolet;
    }

    aside .sidebar img{
    position: relative;
    left: 50%;
    transform: translate(-50%);
    top: 3%;
    border-radius: 50%;
    width: 80px;
    height: 80px;
    object-fit: cover;
    border: 2px solid black;
    }

    aside .sidebar h3 {
    font-size: 1.0rem; /* Réduit la taille du texte du titre */
    margin-bottom: 15px;
    justify-content: center;
    display: flex;
    
    }

    .sidebar .top {
    width: 20%;
    height: 8vh;
    background-color: rgb(82, 92, 105);
    position: absolute;
    }
    
    .sidebar img {
    position: relative;
    left: 0%;
    transform: translate(-50%);
    top: 3%;
    border-radius: 50%;
    width: 80px;
    height: 80px;
    object-fit: cover;
    border: 2px solid black; /*quand j'appuie sur le profil d'un ami*/
    }

    .card img {
    position: relative;
    left: 20%;
    transform: translate(-50%);
    top: 3%;
    border-radius: 50%;
    width: 80px;
    height: 80px;
    object-fit: cover;
    border: 2px solid black; /*quand j'appuie sur le profil d'un ami*/
    }

    aside .sidebar .profile {
    position: relative;
    text-align: right;
    top: 5%;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    }

    .sidebar .profile a {
    text-decoration: none;
    color: black;
    }

    .sidebar .profile a:hover {
        text-decoration: none;
    }

    .sidebar .profile small {
        font-size: 0.7rem;
        color: black;
    }

    .sidebar .vue {
    position: relative;
    display: flex;
    flex-direction: column;
    top: 6%;
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

    .sidebar .vue .vues h6 {
        color: blueviolet;
        font-weight: 100;
    }

    .sidebar .vue .vues a {
    color: rgb(39, 39, 219);
    text-decoration: none;
    font-size: 0.8rem;
    }

    .sidebar .premium {
        position: relative;
        top: 7%;
    }

    .sidebar .premium h6 {
        color: gray;
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
        color: #000;
    }

    .sidebar .premium a i {
        color: rgb(211, 211, 33);
    }

    hr#premium,
    hr#vue,
    hr#profile {
        margin: 0.5rem 0 0 0;
    }

    .items {
        position: relative;
        top: 7%;
        display: flex;
        gap: 0.5rem;
        margin: 0.4rem 0 0 1rem;
        color: gray;
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

    /* Conteneur de la sidebar (demandes d'amis) */
    .right-side .sidebar {
        background-color: #f7eaff;  /* Fond blanc pour la sidebar */
        padding: 15px;  /* Espacement autour du contenu */
        border-radius: 10px;  /* Coins arrondis */
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);  /* Ombre autour de la sidebar */
        border: 2px solid black;  /* Bordure pour la sidebar */
    }

    /* Titre de la section "Demandes d'amis" */
    .right-side .sidebar h3 {
        font-size: 1.0rem;
        font-weight: bold;
        color: blueviolet;
        text-align: center;
        margin-bottom: 30px;
    }

    /* Centrer les sections */
    .container {
        display: grid;
        grid-template-columns: 1fr 2fr 1fr;
        gap: 20px;
        width: 85%;
        margin: 20px auto;
        background-color: white;
        text-align: center;
    }

    /* la cases de mes amis */
    .card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    background: #f7eaff;
    margin-bottom: 10px;
    text-align: center;
    border: 2px solid black;
    width: 200px;
    height: auto;
    display: inline-block;

    }

    .card p {
        font-size: 0.8rem; /* Réduit la taille de la police du texte */
        color: black; /* Assurez-vous que le texte est visible */
        margin: 5px 0; /* Espacement entre le texte */
    }

    .card img {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    object-fit: cover;
    margin-bottom: 10px;
    }

    .card button {
        padding: 5px 15px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        margin-top: 10px;
        background-color: blueviolet;
    }

    card button:hover {
    opacity: 0.9;
}

    .btn-refuser {
        background-color: #e74c3c;
        color: white;
    }

    .btn-refuser:hover {
        background-color: #c0392b;
    }

    .btn-accepter {
        background-color: #0073b1;
        color: white;
    }

    .btn-accepter:hover {
        background-color: #005582;
    }

    /* Section qui conient la case des amis */
    .main-content {
        border: 2px solid black;
        border-radius: 10px;
        padding: 20px;
        background: #f7eaff;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }

    .main-content h2 {
    font-size: 1.0rem; /* Taille de la police */
    font-weight: bold; /* Gras */
    color: blueviolet; /* Couleur du texte */
    text-align: center; /* Centrer le titre */
    margin-bottom: 20px; /* Espacement sous le titre */
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
      flex-wrap: wrap; /* Permet de passer sur plusieurs lignes si la largeur est insuffisante */
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
</style>
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
        
        <aside>
            <div class="sidebar">
                <br>
                <h3>Suggestions d'amis</h3>
                <?php foreach ($suggestions as $suggestion): ?>
                    <div class="card">
                     <img src="<?php echo htmlspecialchars(getPhotoProfil($suggestion['photo_profil'])); ?>" alt="Profil de <?php echo htmlspecialchars($suggestion['prenom']); ?>">
                    <div>
            <p><?php echo htmlspecialchars($suggestion['prenom'] . ' ' . $suggestion['nom']); ?></p>
            <p><small><?php echo htmlspecialchars($suggestion['statut']); ?></small></p>
            </div>
            
                    <form method="POST" action="reseau.php">
                     <input type="hidden" name="id_utilisateur2" value="<?php echo $suggestion['id_utilisateur']; ?>">
                     <button type="submit" name="ajouter_ami">Ajouter</button>
                    </form>
            </div>
                    <?php endforeach; ?>

            </div>
        </aside>

        
        <main>
            <div class="main-content">
                <h2>Vos amis</h2>
                <div class="friends-list">
                    <?php foreach ($friends as $friend): ?>
                        <div class="card">
                            <img src="<?php echo htmlspecialchars(getPhotoProfil($friend['photo_profil'])); ?>" alt="Photo de <?php echo htmlspecialchars($friend['prenom']); ?>">
                            <div class="friend-details">
                                <a href="#"><?php echo htmlspecialchars($friend['prenom'] . ' ' . $friend['nom']); ?></a>
                                <p><?php echo htmlspecialchars($friend['statut']); ?></p>
                            </div>
                        </div>
                    <?php endforeach; ?>
                </div>
            </div>
        </main>

        
        <div class="right-side">
            <div class="sidebar">
                <h3>Demandes d'amis</h3>
                <?php foreach ($demandes as $demande): ?>
                    <div class="card">
                        <img src="<?php echo htmlspecialchars(getPhotoProfil($demande['photo_profil'])); ?>" alt="Profil de <?php echo htmlspecialchars($demande['prenom']); ?>">
                        <div>
                            <p><?php echo htmlspecialchars($demande['prenom'] . ' ' . $demande['nom']); ?></p>
                        </div>
                        <form method="POST" action="accepter_demande_ami.php" style="display: inline;">
                            <input type="hidden" name="id_utilisateur1" value="<?php echo htmlspecialchars($demande['id_utilisateur']); ?>">
                            <input type="hidden" name="id_utilisateur2" value="<?php echo $id_utilisateur; ?>">
                            <button type="submit" class="btn-accepter">Accepter</button>
                        </form>

                        <form method="POST" action="refuser_demande_ami.php" style="display: inline;">
                            <input type="hidden" name="id_utilisateur1" value="<?php echo htmlspecialchars($demande['id_utilisateur']); ?>">
                            <input type="hidden" name="id_utilisateur2" value="<?php echo $id_utilisateur; ?>">
                            <button type="submit" class="btn-refuser">Refuser</button>
                        </form>
                    </div>
                <?php endforeach; ?>
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