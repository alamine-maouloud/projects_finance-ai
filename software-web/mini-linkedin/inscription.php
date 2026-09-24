<?php

include('db.php');


session_start();


if ($_SERVER['REQUEST_METHOD'] == 'POST') {

    
    $prenom = $_POST['prenom'];
    $nom = $_POST['nom'];
    $email = $_POST['email'];
    $password = $_POST['password'];
    $confirmpassword = $_POST['confirmpassword'];
    $statut = $_POST['statut']; 

    if ($password !== $confirmpassword) {
        $_SESSION['prenom'] = $prenom;
        $_SESSION['nom'] = $nom;
        $_SESSION['email'] = $email;
        $_SESSION['statut'] = $statut;
        
        header('Location: erreur_inscription.html');
        exit;
    }

    
    $query = $pdo->prepare("SELECT * FROM utilisateurs WHERE email = :email");
    $query->execute(['email' => $email]);

    if ($query->rowCount() > 0) {

    
        $_SESSION['prenom'] = $prenom;
        $_SESSION['nom'] = $nom;
        $_SESSION['email'] = $email;
        $_SESSION['statut'] = $statut;

        header('Location: erreur_inscription.php');
        exit;
    }

    
    $mot_de_passe_hache = password_hash($password, PASSWORD_DEFAULT);

    
    $stmt = $pdo->prepare("INSERT INTO utilisateurs (email, mot_de_passe, statut, prenom, nom, photo_profil, photo_fond) 
                           VALUES (:email, :mot_de_passe, :statut, :prenom, :nom, :photo_profil, :photo_fond)");
    $stmt->execute([
        'email' => $email,
        'mot_de_passe' => $mot_de_passe_hache,
        'statut' => $statut,
        'prenom' => $prenom,
        'nom' => $nom,
        'photo_profil' => 'default_avatar.png',
        'photo_fond' => NULL            
    ]);


    header('Location: connexion.html');
    exit;
}
?>
