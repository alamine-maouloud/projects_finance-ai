<?php

include('db.php');


if ($_SERVER['REQUEST_METHOD'] == 'POST') {


    $email = $_POST['email'];
    $password = $_POST['password'];

 
    $query = $pdo->prepare("SELECT * FROM utilisateurs WHERE email = :email");
    $query->execute(['email' => $email]);

    $user = $query->fetch();

    if ($user && password_verify($password, $user['mot_de_passe'])) {
   
        session_start();
        $_SESSION['id_utilisateur'] = $user['id_utilisateur'];
        $_SESSION['statut'] = $user['statut']; 
        $_SESSION['email'] = $user['email'];   


        header('Location: accueil.php');  
        exit;
    } else {
        
        header('Location: erreur_connexion.html');
        exit;
    }
}
?>
