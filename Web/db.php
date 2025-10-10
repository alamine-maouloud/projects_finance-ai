<?php

$servername = "localhost";
$username = "root";
$password = "";
$dbname = "ece_in";


$conn = new mysqli($servername, $username, $password, $dbname);


if ($conn->connect_error) {
    die("Échec de la connexion : " . $conn->connect_error);
}


$host = 'localhost'; 
$dbname = 'ece_in';  
$username = 'root';  
$password = '';     

try {
    $pdo = new PDO("mysql:host=$host;dbname=$dbname", $username, $password);

    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $e) {
 
    die("Échec de la connexion à la base de données: " . $e->getMessage());
}


?>


