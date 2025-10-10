<?php
session_start(); 


$host = 'localhost';
$dbname = 'ece_in';
$user = 'root';
$password = '';

try {

    $pdo = new PDO("mysql:host=$host;dbname=$dbname;charset=utf8", $user, $password);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
    die("Erreur de connexion à la base de données : " . $e->getMessage());
}

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$id_utilisateur = $_SESSION['id_utilisateur'];
$query = $pdo->prepare("SELECT * FROM utilisateurs WHERE id_utilisateur = :id_utilisateur");
$query->execute(['id_utilisateur' => $id_utilisateur]);

$user = $query->fetch();


$isEmployeur = false;


try {
    $stmtEmployeur = $pdo->prepare("SELECT statut FROM utilisateurs WHERE id_utilisateur = :id LIMIT 1");
    $stmtEmployeur->bindParam(':id', $id_utilisateur, PDO::PARAM_INT);
    $stmtEmployeur->execute();
    $statut = $stmtEmployeur->fetchColumn();
    $isEmployeur = ($statut === 'employeur');
} catch (PDOException $e) {
    die("Erreur lors de la vérification du statut : " . $e->getMessage());
}


if ($_SERVER['REQUEST_METHOD'] === 'POST' && $isEmployeur) {
    if (!isset($_POST['csrf_token']) || $_POST['csrf_token'] !== $_SESSION['csrf_token']) {
        die("Erreur CSRF : Jeton invalide.");
    }
    
    $type_emploi = $_POST['type_emploi'] ?? '';
    $description_offre = $_POST['description_offre'] ?? '';
    $lieu_emploi = $_POST['lieu_emploi'] ?? '';
    $date_offre = date('Y-m-d');
    $date_expiration = $_POST['date_expiration'] ?? '';

    
    $valid_types = ['cdd', 'cdi', 'stage', 'apprentissage'];
    if (!in_array($type_emploi, $valid_types)) {
        die("Erreur : Type d'emploi invalide.");
    }

    try {
        $stmt = $pdo->prepare("INSERT INTO offres_emploi (id_utilisateur, type_emploi, description_offre, lieu_emploi, date_offre, date_expiration) VALUES (:id_utilisateur, :type_emploi, :description_offre, :lieu_emploi, :date_offre, :date_expiration)");
        $stmt->execute([
            ':id_utilisateur' => $id_utilisateur,
            ':type_emploi' => $type_emploi,
            ':description_offre' => $description_offre,
            ':lieu_emploi' => $lieu_emploi,
            ':date_offre' => $date_offre,
            ':date_expiration' => $date_expiration
        ]);
        unset($_SESSION['csrf_token']);
        header("Location: " . $_SERVER['PHP_SELF']);
        exit;
    } catch (PDOException $e) {
        die("Erreur lors de l'ajout de l'offre : " . $e->getMessage());
    }
}


try {
    $stmt = $pdo->prepare("
        SELECT o.id_offre, o.type_emploi, o.description_offre, o.lieu_emploi, o.date_offre, o.date_expiration, u.prenom AS employeur_prenom, u.nom AS employeur_nom 
        FROM offres_emploi o
        JOIN utilisateurs u ON o.id_utilisateur = u.id_utilisateur
        ORDER BY o.date_offre DESC
    ");
    $stmt->execute();
    $offres = $stmt->fetchAll(PDO::FETCH_ASSOC);
} catch (PDOException $e) {
    die("Erreur lors de la récupération des offres : " . $e->getMessage());
}
?>

<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css">
    <title>EceIn | Emplois</title>
    <style>

        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500&display=swap');

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Poppins', sans-serif;
        }
        .offre .employeur {
            font-style: italic;
            font-size: 0.9rem;
            color: blueviolet;
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

        /* La boîte des offres */
        .offre {
            background-color: #f7eaff !important; /* Utilisation de !important pour forcer l'application */
            border: 2px solid black !important;
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
            width: 100%;
        }

        /* La grande boîte contenant tout */
        .big-container {
            width: 80%; /* Prend 80% de la largeur de l'écran */
            margin: 0 auto; /* Centré horizontalement */
            padding: 20px; /* Padding interne */
            background-color: white; /* Couleur de fond de la boîte */
            border-radius: 10px; /* Coins arrondis */
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1); /* Ombre douce */
            border: 2px solid black; /* Bordure noire */
            display: flex; /* Utilisation du flexbox pour le centrage */
            flex-direction: column; /* Organise les éléments en colonne */
            align-items: center; /* Centrer verticalement */
        }

        /* La boîte contenant le titre */
        .title-container {
            width: 50%; /* Prend toute la largeur de son conteneur */
            background-color: #f7eaff; /* Fond de la boîte */
            padding: 20px; /* Espacement interne */
            text-align: center; /* Centre le texte horizontalement */
            border-radius: 10px; /* Coins arrondis */
            margin-bottom: 20px; /* Espacement sous la boîte */
            border: 2px solid black; /* Bordure de la boîte */
        }

        /* Style du titre à l'intérieur de la boîte */
        .title-container h1 {
            font-size: 1.5rem; /* Taille du texte */
            font-weight: bold; /* Gras */
            color: black; /* Couleur du texte */
            margin: 0; /* Enlève les marges par défaut */
        }

        /* La boîte des offres */
        .offre {
            background-color: #fff; /* Fond blanc pour chaque offre */
            padding: 15px;
            border-radius: 10px;
            border: 2px solid #ddd;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
            margin-bottom: 20px;
        }

        /* Le bouton pour ajouter une offre */
        .add-button {
            background-color: #28a745;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
        }

        .add-button:hover {
            background-color: #218838; /* Couleur du bouton au survol */
        }

        /* Espace entre les différentes sections */
        .space-between {
            margin-top: 30px;
        }




        .add-button, form button {
            padding: 10px 15px;
            background-color: #28a745;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        form {
            display: none;
            margin: 20px auto;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            max-width: 500px;
            background-color: white;
        }
        form label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        form input, form textarea, form select {
            width: 100%;
            padding: 8px;
            margin-bottom: 15px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        form button {
            margin-top: 10px;
        }
        .space-between {
            margin-top: 30px;
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

        /* La boîte contenant le titre */
        .title-container {
            width: 50%; /* Limite la largeur de la boîte à 50% de la fenêtre */
            background-color: #f7eaff; /* Fond de la boîte */
            padding: 20px; /* Espacement interne */
            text-align: center; /* Centre le texte horizontalement */
            border-radius: 10px; /* Coins arrondis */
            border: 2px solid black; /* Bordure de la boîte */
            margin-bottom: 20px; /* Espacement sous la boîte */
            display: flex;
            justify-content: center;
        }

        /* Le style du titre à l'intérieur de la boîte */
        .title-container h1 {
            font-size: 1.0rem; /* Taille du texte */
            font-weight: bold; /* Gras */
            color: blueviolet; /* Couleur du texte */
            margin: 0; /* Enlève les marges par défaut */
        }


    </style>
    <script>
        function showForm() {
            document.getElementById('offerForm').style.display = 'block';
            document.getElementById('addButton').style.display = 'none';
        }
    </script>
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
    <br>
<div class="big-container"> 
    <div class="title-container">
        <h1>Liste des offres d'emploi</h1>
    </div>

    <?php if ($isEmployeur): ?>
        <button id="addButton" class="add-button" onclick="showForm()">Ajouter une offre d'emploi</button>
        <form id="offerForm" method="POST">
            <input type="hidden" name="csrf_token" value="<?php echo $_SESSION['csrf_token']; ?>">
            <label for="type_emploi">Type d'emploi :</label>
            <select name="type_emploi" required>
                <option value="">-- Choisissez un type --</option>
                <option value="cdd">CDD</option>
                <option value="cdi">CDI</option>
                <option value="stage">Stage</option>
                <option value="apprentissage">Apprentissage</option>
            </select>
            <label for="description_offre">Description :</label>
            <textarea name="description_offre" rows="4" required></textarea>
            <label for="lieu_emploi">Lieu :</label>
            <input type="text" name="lieu_emploi" required>
            <label for="date_expiration">Date d'expiration :</label>
            <input type="date" name="date_expiration" required>
            <button type="submit">Ajouter l'offre</button>
        </form>
    <?php endif; ?>

    <div class="space-between"></div>

    <?php foreach ($offres as $offre): ?>
    <div class="offre">
        <h3><?php echo ucfirst($offre['type_emploi']); ?></h3>  
        <p><?php echo nl2br(htmlspecialchars($offre['description_offre'])); ?></p>
        <p>Lieu : <?php echo htmlspecialchars($offre['lieu_emploi']); ?></p>
        <small>Publié le : <?php echo htmlspecialchars($offre['date_offre']); ?></small><br>
        <small>Expire le : <?php echo htmlspecialchars($offre['date_expiration']); ?></small><br>
        <p class="employeur">Proposé par : <?php echo htmlspecialchars($offre['employeur_prenom'] . ' ' . $offre['employeur_nom']); ?></p>
    </div>
<?php endforeach; ?>
</div>

</body>
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
</html>
