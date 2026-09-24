<?php

$servername = "localhost";
$username = "root";
$password = "";
$dbname = "ece_in";

$conn = new mysqli($servername, $username, $password, $dbname);

if ($conn->connect_error) {
    die("Échec de la connexion : " . $conn->connect_error);
}


session_start();


if (!isset($_SESSION['id_utilisateur'])) {
    
    header('Location: connexion.html');
    exit();
}


$user_id = $_SESSION['id_utilisateur'];


$sql = "SELECT * FROM utilisateurs WHERE id_utilisateur = $user_id";
$result = $conn->query($sql);

if ($result->num_rows > 0) {
    $user = $result->fetch_assoc();

    $user['description'] = $user['description'] ?? ''; 
    $user['projets'] = $user['projets'] ?? ''; 
    $user['photo_profil'] = $user['photo_profil'] ?? 'default_avatar.png'; 
    $user['formation'] = $user['formation'] ?? ''; 
} else {
    die("Utilisateur non trouvé");
}

if ($_SERVER['REQUEST_METHOD'] == 'POST') {
    $prenom = $_POST['prenom'];
    $nom = $_POST['nom'];
    $email = $_POST['email'];
    $description = $_POST['description'];
    $projets = $_POST['projets'];
    $statut = $_POST['statut'];
    $password = $_POST['password'];
    $new_password = $_POST['new_password'];
    $confirm_password = $_POST['confirm_password'];

    if (!empty($new_password) && $new_password === $confirm_password) {
        $hashed_password = password_hash($new_password, PASSWORD_DEFAULT);
        $updatePasswordQuery = "UPDATE utilisateurs SET mot_de_passe = '$hashed_password' WHERE id_utilisateur = $user_id";
        $conn->query($updatePasswordQuery);
    }


    $photo_profil = $user['photo_profil']; 
    if (isset($_FILES['photo_profil']) && $_FILES['photo_profil']['error'] === UPLOAD_ERR_OK) {
        $target_dir = "uploads/"; 
        $target_file = $target_dir . basename($_FILES['photo_profil']['name']);
        if (move_uploaded_file($_FILES['photo_profil']['tmp_name'], $target_file)) {
            $photo_profil = $target_file; 
        }
    }

    
    $updateUserQuery = "UPDATE utilisateurs 
        SET prenom = '$prenom', 
            nom = '$nom', 
            email = '$email', 
            description = '$description', 
            projets = '$projets', 
            statut = '$statut', 
            photo_profil = '$photo_profil', 
            cv = '$cv_name' 
        WHERE id_utilisateur = $user_id";
    if ($conn->query($updateUserQuery) === TRUE) {
        echo "Mise à jour réussie!";
        header("Location: monprofil.php"); 
        exit(); 
    } else {
        echo "Erreur lors de la mise à jour: " . $conn->error;
    }
}


    if (isset($_FILES['cv']) && $_FILES['cv']['error'] === UPLOAD_ERR_OK) {

    $target_dir = "cv_utilisateurs/"; 

    
    $cv_name = $user['prenom'] . "_" . $user['nom'] . "_" . basename($_FILES['cv']['name']);
    $target_file = $target_dir . $cv_name;

    
    $file_type = strtolower(pathinfo($target_file, PATHINFO_EXTENSION));

    if ($file_type == 'pdf' || $file_type == 'doc' || $file_type == 'docx' || $file_type == 'txt') {
        
        if (move_uploaded_file($_FILES['cv']['tmp_name'], $target_file)) {
            echo "Le CV a été téléchargé avec succès.";
        } else {
            echo "Erreur lors du téléchargement du CV.";
        }
    } else {
        echo "Désolé, seuls les fichiers PDF, DOC, DOCX et TXT sont autorisés.";
    }
} else {
    
    $cv_name = $user['cv'] ?? ''; 
}


if (isset($_FILES['cv']) && $_FILES['cv']['error'] === UPLOAD_ERR_OK) {
    
    $target_dir = "cv_utilisateurs/"; 

    
    $cv_name = $user['prenom'] . "_" . $user['nom'] . "_" . basename($_FILES['cv']['name']);
    $target_file = $target_dir . $cv_name;

    
    $file_type = strtolower(pathinfo($target_file, PATHINFO_EXTENSION));

    if ($file_type == 'pdf' || $file_type == 'doc' || $file_type == 'docx' || $file_type == 'txt') {
        
        if (move_uploaded_file($_FILES['cv']['tmp_name'], $target_file)) {
            echo "Le CV a été téléchargé avec succès.";
        } else {
            echo "Erreur lors du téléchargement du CV.";
        }
    } else {
        echo "Désolé, seuls les fichiers PDF, DOC, DOCX et TXT sont autorisés.";
    }
} else {
    
    $cv_name = $user['cv'] ?? ''; 
}

$conn->close();
?>


<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="style1.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css" />

    <title>EceIn | Mon Profil</title>
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
            width: 1200px;

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

        body {
            font-family: sans-serif;
            overflow: scroll;
            align-items: center;
            flex-direction: column;
            display: flex;
        }

        

        /*section autour*/
        section {
            max-width: 550px;
            width: 80vw;
            min-width: 100px;
            padding: 40px 50px;
            margin: 60px auto 25px;
            box-shadow: 1px 1px 6px 8px rgba(0, 0, 0, 0.1);
            border-radius: 7px;
            background: white;
            border: 2px solid black;
        }

        /* Titre de la section */
        section > h2 {
            margin: 0 0 5px 0;
            font-size: 1.6em;
            font-weight: 600;
            color: blueviolet;
            text-align: center;
        }

        section > p {
            font-size: 0.59rem;
            margin-top: 0;
            font-weight: 500;
        }

        /* Champs de saisie */
        section input {
            padding: 8px;
            width: 100%;
            margin-bottom: 10px;
            border: 1px solid rgba(0, 0, 0, 1.0);
            border-radius: 2px;
            opacity: 1;
            transition: 0.3s ease;
        }

        section input:focus {
            outline: none;
            font-size: 0.9em;
        }

        .password {
            display: flex;
            align-items: center;
            padding: 0;
            border-radius: 3px;
            margin-bottom: 10px;
            border: 1px solid rgba(0, 0, 0, 1.0);
        }

        .password input {
            border: none;
            padding: 9px;
            margin: 0;
            width: 100%;
        }

        .password input:focus {
            outline: none;
        }

        .password a {
            text-decoration: none;
            font-size: 9px;
            padding: 10px;
            color: blueviolet;
            font-weight: bold;
        }

        section a#pwd-change {
            display: block;
            color: blueviolet;
            font-size: 10px;
            font-weight: bold;
            text-decoration: none;
            margin: 9px 0 14px;
        }

        button[type="submit"] {
            padding: 10px;
            width: 100%;
            border-radius: 20px;
            border: none;
            color: rgba(255, 255, 255);
            background-color: blueviolet;
            font-size: 0.7em;
            box-shadow: 1px 1px 2px 1px rgba(0, 0, 0, 1.0);
            transition: 0.3s ease;
            cursor: pointer;
        }

        button[type="submit"]:hover {
            background-color: #5d3c8a;
        }

        #description, #projets {
            color: black; /* Changer la couleur du texte */
            font-family: 'Arial', sans-serif; /* Changer la police */
            font-size: 0.8em; /* Ajuster la taille de la police si nécessaire */
            line-height: 1.5em; /* Espacement entre les lignes */
            padding: 8px; /* Ajouter du padding si nécessaire */
            border: 1px solid #ccc; /* Ajouter une bordure claire */
            width: 100%; /* S'assurer que les champs prennent toute la largeur de leur conteneur */
            transition: all 0.3s ease; /* Ajout d'un effet de transition */
            border-color: black;
        }

        #description:focus, #projets:focus {
            outline: none; /* Enlever le contour de focus par défaut */
            box-shadow: 0 0 5px rgba(93, 60, 138, 0.8); /* Ajouter une ombre autour du champ */
        }

        /* bouton etudiant */

        select {
            display: flex;
            padding: 4px;
            width: 80%;
            margin: 0 auto;
            border-radius: 20px;
            border: none;
            color: rgba(255, 255, 255);
            background-color: blueviolet;
            font-size: 0.7em;
            box-shadow: 1px 1px 2px 1px rgba(0, 0, 0, 1.0);
            transition: 0.3s ease;
            cursor: pointer;
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
            text-align: center;
        }

        select:hover {
            background-color: #5d3c8a;
        }

        select:focus {
            outline: none;
            box-shadow: 0px 0px 5px 2px rgba(93, 60, 138, 0.8);
        }

        label {
            font-size: 0.7em;
            color: black;
        }

        #photoPreview {
            width: 100px; /* Largeur souhaitée */
            height: 100px; /* Hauteur souhaitée */
            object-fit: cover; /* Cela permet de garder l'image bien centrée sans déformation */
            border-radius: 50%; /* Pour arrondir l'image (si c'est une photo de profil ronde) */
            cursor: pointer; /* Pour indiquer que l'image peut être changée */
            margin: 0 auto;
            display: flex;

        }

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

        p {
            text-align: center; /* Centrer le texte */
            font-size: 1rem; /* Taille de la police */
            color: #333; /* Couleur du texte */
            margin-top: 20px; /* Espace au-dessus */
        }

        p a {
            color: blueviolet; /* Couleur du lien */
            text-decoration: none; /* Enlève le soulignement */
            font-weight: bold; /* Met le texte en gras */
            transition: color 0.3s ease; /* Effet de transition */
        }

        /* Enlever le trait de la ligne horizontale */
        .deconnexion-container hr {
            display: none; 
        }

        /* Centrer le texte et le lien */
        .centered-text {
            text-align: center; 
            font-size: 1rem; /* Ajuster la taille du texte */
            margin-top: 20px; /* Espace au-dessus */
        }

        .centered-text a {
            color: blueviolet; 
            font-weight: bold; 
            text-decoration: none; 
            transition: color 0.3s ease;
        }

        .centered-text a:hover {
            color: darkviolet; 
            text-decoration: none; /
        }
        
    </style>
    <script>
        function previewImage(event) {
            const reader = new FileReader();
            reader.onload = function () {
                const output = document.getElementById('photoPreview');
                output.src = reader.result;
            };
            reader.readAsDataURL(event.target.files[0]);
        }

        
        document.querySelector('form').addEventListener('submit', function(event) {
            const newPassword = document.getElementById('new_password').value;
            const confirmPassword = document.getElementById('confirm_password').value;

            if (newPassword !== confirmPassword) {
                event.preventDefault(); 
                alert("Les mots de passe ne correspondent pas !");
            }
        });
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
    <main>
        <section>
            <h2>Profil de <?php echo htmlspecialchars($user['prenom'] . ' ' . $user['nom']); ?></h2><br>

            <form method="post" enctype="multipart/form-data">
                <label for="photo_profil">
                    <img src="<?php echo htmlspecialchars($user['photo_profil']); ?>" alt="Photo de profil" id="photoPreview" class="photo-profil" title="Cliquez pour changer">
                </label><br>
                <input type="file" id="photo_profil" name="photo_profil" accept="image/*" style="display: none;" onchange="previewImage(event)"><br><br>

                <input type="text" name="prenom" id="prenom" placeholder="Entrez votre Prénom" value="<?php echo htmlspecialchars($user['prenom']); ?>" required><br><br>
                <input type="text" name="nom" id="nom" placeholder="Entrez votre Nom" value="<?php echo htmlspecialchars($user['nom']); ?>" required><br><br>
                <input type="email" name="email" id="email" placeholder="Entrez votre Email" value="<?php echo htmlspecialchars($user['email']); ?>" required><br><br>

                <textarea id="description" name="description" placeholder="Description" rows="5" cols="47"><?php echo htmlspecialchars($user['description']); ?></textarea><br><br>
                <textarea id="projets" name="projets" placeholder="Projets" rows="5" cols="47"><?php echo htmlspecialchars($user['projets']); ?></textarea><br><br>

                <label for="cv">Télécharger votre CV :</label><br><br>
                <input type="file" name="cv" id="cv" accept=".pdf,.doc,.docx,.txt" /><br><br>


                <label for="statut">Sélectionnez votre nouveau statut :</label>
                <br><br>
                <select name="statut" id="statut" required>
                    <option value="étudiant" <?php echo $user['statut'] == 'étudiant' ? 'selected' : ''; ?>>Étudiant</option>
                    <option value="employeur" <?php echo $user['statut'] == 'employeur' ? 'selected' : ''; ?>>Employeur</option>
                    <option value="enseignant" <?php echo $user['statut'] == 'enseignant' ? 'selected' : ''; ?>>Enseignant</option>
                </select><br><br>

                <div class="password"><input type="password" name="password" id="password" placeholder="Ancien mot de passe"></div>
                <div class="password"><input type="password" name="new_password" id="new_password" placeholder="Nouveau mot de passe"></div>
                <div class="password"><input type="password" name="confirm_password" id="confirm_password" placeholder="Confirmer mot de passe"></div><br><br>

                <div id="button-container"><button type="submit">Mettre à jour</button></div>
                <div class="flex"><div class="hor-line"></div>
                <div class="deconnexion-container">
                    <p class="centered-text">Souhaitez-vous vous déconnecter ? <a href="acceuil.html" class="deconnexion-link">Déconnexion</a></p>
                </div>
            </form>

        </section>
    </main>
</body>
</html>
