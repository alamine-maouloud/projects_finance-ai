<?php
session_start();

$prenom = isset($_SESSION['prenom']) ? $_SESSION['prenom'] : '';
$nom = isset($_SESSION['nom']) ? $_SESSION['nom'] : '';
$email = isset($_SESSION['email']) ? $_SESSION['email'] : '';
$statut = isset($_SESSION['statut']) ? $_SESSION['statut'] : 'étudiant'; 
?>

<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="css/style1.css">
  <title>Erreur d'inscription</title>
</head>
<body>
  <form action="inscription.php" method="POST">
    <main>
      <header><h1>EcE<span>in</span></h1></header>
      <section>
        <h2>Créer votre compte</h2>
        <p> Nous sommes ravis de vous avoir parmi nous !<br><br></p>
        <p1>L'e-mail est déjà utilisé ou les mots de passe ne correspondent pas.</p1>
        
        
        <input type="text" name="prenom" id="prenom" placeholder="Entrez votre Prénom" value="<?php echo htmlspecialchars($prenom); ?>" required>
        <input type="text" name="nom" id="nom" placeholder="Entrez votre Nom" value="<?php echo htmlspecialchars($nom); ?>" required>
        <input type="email" name="email" id="email" placeholder="Entrez votre Email" value="<?php echo htmlspecialchars($email); ?>" required>
        
        <div><div class="password"><input type="password" name="password" id="password" placeholder="Entrez votre mot de passe"><a href="#"> Afficher</a></div></div>
        <div><div class="password"><input type="password" name="confirmpassword" id="confirmpassword" placeholder="Confirmer le mot de passe"><a href="#"> Afficher</a></div></div>

        <label for="statut"> Sélectionnez votre statut : </label><br><br>
        <select name="statut" id="statut" required>
            <option value="étudiant" <?php if($statut == 'étudiant') echo 'selected'; ?>>Étudiant</option>
            <option value="employeur" <?php if($statut == 'employeur') echo 'selected'; ?>>Employeur</option>
            <option value="enseignant" <?php if($statut == 'enseignant') echo 'selected'; ?>>Enseignant</option>
        </select>
    
        <hr>
        <div id="button-container"><button type="submit">Créer votre compte</button></div>
      </section>
      <p> Déjà un compte ? <a href="connexion.html"> Connectez-vous ici </a></p>
      <p> Retour sur la page principale <a href="principale.html"> Cliquez ici </a></p>
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
    </main>
  </form>
</body>
</html>