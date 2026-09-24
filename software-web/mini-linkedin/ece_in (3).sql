-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1:3306
-- Généré le : dim. 15 déc. 2024 à 22:50
-- Version du serveur : 9.1.0
-- Version de PHP : 8.3.14

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `ece_in`
--

-- --------------------------------------------------------

--
-- Structure de la table `albums`
--

DROP TABLE IF EXISTS `albums`;
CREATE TABLE IF NOT EXISTS `albums` (
  `id_album` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur` int NOT NULL,
  `nom_album` varchar(255) DEFAULT NULL,
  `date_creation` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_album`),
  KEY `id_utilisateur` (`id_utilisateur`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `connexions`
--

DROP TABLE IF EXISTS `connexions`;
CREATE TABLE IF NOT EXISTS `connexions` (
  `id_utilisateur1` int NOT NULL,
  `id_utilisateur2` int NOT NULL,
  `date_ajout` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `statut_connexion` enum('en attente','acceptée','refusée') DEFAULT 'en attente',
  PRIMARY KEY (`id_utilisateur1`,`id_utilisateur2`),
  KEY `id_utilisateur2` (`id_utilisateur2`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `connexions`
--

INSERT INTO `connexions` (`id_utilisateur1`, `id_utilisateur2`, `date_ajout`, `statut_connexion`) VALUES
(1, 2, '2024-12-13 11:32:41', 'acceptée'),
(1, 3, '2024-12-13 14:38:17', 'acceptée'),
(1, 4, '2024-12-13 15:11:38', 'acceptée'),
(2, 3, '2024-12-13 15:11:51', 'acceptée'),
(3, 4, '2024-12-13 15:12:01', 'acceptée'),
(1, 5, '2024-12-13 15:12:29', 'acceptée'),
(1, 6, '2024-12-13 15:12:38', 'acceptée'),
(5, 6, '2024-12-13 15:12:45', 'acceptée'),
(2, 5, '2024-12-13 15:12:53', 'acceptée'),
(6, 2, '2024-12-13 15:56:45', 'en attente'),
(7, 2, '2024-12-14 11:39:48', 'acceptée'),
(2, 4, '2024-12-14 11:46:38', 'en attente'),
(2, 8, '2024-12-14 14:10:35', 'acceptée'),
(9, 1, '2024-12-14 20:05:09', 'acceptée'),
(9, 2, '2024-12-14 20:05:10', 'acceptée'),
(9, 3, '2024-12-14 20:56:22', 'en attente'),
(10, 2, '2024-12-15 12:10:29', 'acceptée'),
(10, 1, '2024-12-15 12:10:30', 'en attente'),
(7, 1, '2024-12-15 12:44:20', 'en attente'),
(7, 4, '2024-12-15 12:44:21', 'en attente'),
(7, 5, '2024-12-15 12:44:23', 'en attente');

-- --------------------------------------------------------

--
-- Structure de la table `conversations`
--

DROP TABLE IF EXISTS `conversations`;
CREATE TABLE IF NOT EXISTS `conversations` (
  `id_conversation` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur1` int NOT NULL,
  `id_utilisateur2` int NOT NULL,
  `date_creation` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_conversation`),
  KEY `id_utilisateur1` (`id_utilisateur1`),
  KEY `id_utilisateur2` (`id_utilisateur2`)
) ENGINE=MyISAM AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `conversations`
--

INSERT INTO `conversations` (`id_conversation`, `id_utilisateur1`, `id_utilisateur2`, `date_creation`) VALUES
(1, 1, 2, '2024-12-14 13:37:59'),
(2, 1, 3, '2024-12-14 13:43:38'),
(3, 2, 8, '2024-12-14 14:15:22'),
(4, 9, 2, '2024-12-14 21:29:32'),
(6, 9, 1, '2024-12-15 11:51:02'),
(7, 10, 2, '2024-12-15 16:55:10');

-- --------------------------------------------------------

--
-- Structure de la table `evenements`
--

DROP TABLE IF EXISTS `evenements`;
CREATE TABLE IF NOT EXISTS `evenements` (
  `id_evenement` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur` int NOT NULL,
  `nom_evenement` varchar(255) DEFAULT NULL,
  `description` text,
  `date_evenement` datetime DEFAULT NULL,
  `lieu_evenement` varchar(255) DEFAULT NULL,
  `type_evenement` enum('conférence','séminaire','stage','autre') DEFAULT NULL,
  PRIMARY KEY (`id_evenement`),
  KEY `id_utilisateur` (`id_utilisateur`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `messages`
--

DROP TABLE IF EXISTS `messages`;
CREATE TABLE IF NOT EXISTS `messages` (
  `id_message` int NOT NULL AUTO_INCREMENT,
  `id_conversation` int NOT NULL,
  `id_utilisateur` int NOT NULL,
  `message` text,
  `date_message` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `type_message` enum('texte','fichier','vidéo') NOT NULL,
  `status_message` enum('envoyé','vu','non lu') NOT NULL DEFAULT 'non lu',
  PRIMARY KEY (`id_message`),
  KEY `id_conversation` (`id_conversation`),
  KEY `id_utilisateur` (`id_utilisateur`)
) ENGINE=MyISAM AUTO_INCREMENT=49 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
CREATE TABLE IF NOT EXISTS `notifications` (
  `id_notification` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur_envoyeur` int NOT NULL,
  `id_utilisateur_receveur` int NOT NULL,
  `type_notification` enum('événement','message','offre emploi','autre') DEFAULT NULL,
  `contenu_notification` text,
  `date_notification` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `status_notification` enum('vue','non vue') DEFAULT 'non vue',
  PRIMARY KEY (`id_notification`),
  KEY `id_utilisateur` (`id_utilisateur_envoyeur`),
  KEY `id_utilisateur_receveur` (`id_utilisateur_receveur`)
) ENGINE=MyISAM AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `notifications`
--

INSERT INTO `notifications` (`id_notification`, `id_utilisateur_envoyeur`, `id_utilisateur_receveur`, `type_notification`, `contenu_notification`, `date_notification`, `status_notification`) VALUES
(1, 1, 2, 'message', 'Vous avez reçu un nouveau message !', '2024-12-15 19:45:46', 'vue'),
(14, 2, 1, 'message', 'Vous avez un nouveau message.', '2024-12-15 19:49:12', 'vue'),
(15, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 19:49:56', 'vue'),
(16, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 19:49:59', 'vue'),
(17, 9, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 19:53:51', 'vue'),
(18, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 19:54:08', 'vue'),
(19, 2, 1, 'message', 'Vous avez un nouveau message.', '2024-12-15 19:54:50', 'vue'),
(20, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:07:40', 'vue'),
(21, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:07:43', 'vue'),
(22, 9, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:07:59', 'vue'),
(23, 2, 1, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:11:29', 'vue'),
(24, 2, 1, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:11:32', 'vue'),
(25, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:17:30', 'vue'),
(26, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:17:33', 'vue'),
(27, 2, 1, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:29:27', 'vue'),
(28, 2, 1, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:29:31', 'vue'),
(29, 1, 2, 'message', 'Vous avez un nouveau message.', '2024-12-15 20:41:12', 'vue');

-- --------------------------------------------------------

--
-- Structure de la table `offres_emploi`
--

DROP TABLE IF EXISTS `offres_emploi`;
CREATE TABLE IF NOT EXISTS `offres_emploi` (
  `id_offre` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur` int NOT NULL,
  `type_emploi` enum('stage','apprentissage','cdi','cdd') DEFAULT NULL,
  `description_offre` text,
  `lieu_emploi` varchar(255) DEFAULT NULL,
  `date_offre` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `date_expiration` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id_offre`),
  KEY `id_utilisateur` (`id_utilisateur`)
) ENGINE=MyISAM AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `offres_emploi`
--

INSERT INTO `offres_emploi` (`id_offre`, `id_utilisateur`, `type_emploi`, `description_offre`, `lieu_emploi`, `date_offre`, `date_expiration`) VALUES
(1, 5, 'stage', 'J\'offre un stage', 'Stains', '2024-12-13 17:45:41', '2025-12-08 17:45:58'),
(2, 7, 'cdd', 'J\'offre un CDD de 5 semaines !', 'Argenteuil', '2024-12-15 12:43:13', '2025-01-31 12:42:41'),
(3, 7, 'apprentissage', 'Viens en alternance !', 'Courbevoie', '2024-12-15 17:40:31', '2025-02-15 17:40:06');

-- --------------------------------------------------------

--
-- Structure de la table `photos`
--

DROP TABLE IF EXISTS `photos`;
CREATE TABLE IF NOT EXISTS `photos` (
  `id_photo` int NOT NULL AUTO_INCREMENT,
  `id_album` int NOT NULL,
  `path_image` varchar(255) DEFAULT NULL,
  `description_photo` text,
  `date_upload` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `lieu_photo` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id_photo`),
  KEY `id_album` (`id_album`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `publications`
--

DROP TABLE IF EXISTS `publications`;
CREATE TABLE IF NOT EXISTS `publications` (
  `id_publication` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur` int NOT NULL,
  `type` enum('texte','photo','vidéo','événement','cv') NOT NULL,
  `contenu` text,
  `date_publication` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `visibility` enum('public','restreint','privé') DEFAULT 'public',
  PRIMARY KEY (`id_publication`),
  KEY `id_utilisateur` (`id_utilisateur`)
) ENGINE=MyISAM AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `publications`
--

INSERT INTO `publications` (`id_publication`, `id_utilisateur`, `type`, `contenu`, `date_publication`, `visibility`) VALUES
(1, 1, 'texte', 'Première publication de EceIn !!!', '2024-12-15 21:12:02', 'public'),
(2, 2, 'texte', 'On fait des test là !', '2024-12-15 21:25:58', 'public'),
(3, 2, 'texte', 'Encore hein !!', '2024-12-15 21:27:58', 'public'),
(4, 2, 'texte', 'On s\'arrête pas ici !', '2024-12-15 21:28:10', 'public');

-- --------------------------------------------------------

--
-- Structure de la table `ressources`
--

DROP TABLE IF EXISTS `ressources`;
CREATE TABLE IF NOT EXISTS `ressources` (
  `id_ressource` int NOT NULL AUTO_INCREMENT,
  `id_utilisateur` int NOT NULL,
  `type_ressource` enum('powerpoint','vidéo','pdf','autre') NOT NULL,
  `path_ressource` varchar(255) DEFAULT NULL,
  `date_upload` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_ressource`),
  KEY `id_utilisateur` (`id_utilisateur`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- --------------------------------------------------------

--
-- Structure de la table `utilisateurs`
--

DROP TABLE IF EXISTS `utilisateurs`;
CREATE TABLE IF NOT EXISTS `utilisateurs` (
  `id_utilisateur` int NOT NULL AUTO_INCREMENT,
  `email` varchar(100) NOT NULL,
  `mot_de_passe` varchar(255) NOT NULL,
  `statut` enum('Etudiant','Employeur','Enseignant','Admin') CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `prenom` varchar(100) NOT NULL,
  `nom` varchar(100) NOT NULL,
  `photo_profil` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT 'default_avatar.png',
  `photo_fond` varchar(255) DEFAULT NULL,
  `cv` text,
  `description` text,
  `formation` text,
  `projets` text,
  `date_inscription` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id_utilisateur`),
  UNIQUE KEY `email` (`email`)
) ENGINE=MyISAM AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

--
-- Déchargement des données de la table `utilisateurs`
--

INSERT INTO `utilisateurs` (`id_utilisateur`, `email`, `mot_de_passe`, `statut`, `prenom`, `nom`, `photo_profil`, `photo_fond`, `cv`, `description`, `formation`, `projets`, `date_inscription`) VALUES
(1, 'alamine.maouloud@edu.ece.fr', '$2y$10$ZWfVD9mfQrqyBDbPFX9FYeH24a4JTrXeoV0we/vhtn0594tSy9./2', 'Etudiant', 'Alamine', 'Maouloud', 'images/photo_profil1.jpg', '', NULL, NULL, NULL, NULL, '2024-12-13 11:01:12'),
(2, 'ilyes.boukerma@edu.ece.fr', '$2y$10$BwYujqHeUiYx2TTK7obYyuHETJ.o1xMn.USix5LfLg/1r2YoT9lLq', 'Admin', 'Ilyes', 'Boukerma', 'default_avatar.png', '', NULL, 'Fiancé depuis 2 semaines !!!!!!!!!!', '', '', '2024-12-13 11:27:24'),
(3, 'jane.smith@edu.ece.fr', '$2y$10$MHdLnlP.cblElsqVy9KHHOCN70HkKaArkN/IRfRvDwjT0JktqBqK2', 'Etudiant', 'Jane', 'Smith', 'images/photo_profil2.jpg', NULL, NULL, NULL, NULL, NULL, '2024-12-13 11:31:13'),
(4, 'shiva.tilhoo@edu.ece.fr', '$2y$10$QRaaooda7uJmhUsnlka6jeUNyBFCvhlUNle7GQWJ92qq1zbyp5Z7u', 'Etudiant', 'Shiva', 'Tilhoo', 'default_avatar.png', NULL, NULL, NULL, NULL, NULL, '2024-12-13 11:36:26'),
(5, 'amine.zaidi@edu.ece.fr', '$2y$10$AhdqS.WbJD/CTkWabBTtRe1nrWFo4BnFytptXUWSgr5DfXFlBKFaG', 'Etudiant', 'Amine', 'Zaidi', 'images/photo_profil.jpg', NULL, NULL, NULL, NULL, NULL, '2024-12-13 14:21:16'),
(6, 'admin@ece.fr', '$2y$10$KtxqlQYRiOXNON8pzv.Wge0vePIHxOU.n6CKyD9rGTs.3VTDMw9Cy', 'Admin', 'Admin', '', 'default_avatar.png', NULL, NULL, NULL, NULL, NULL, '2024-12-13 14:59:50'),
(7, 'jaoued.lelogeur@edu.ece.fr', '$2y$10$A3UAutfgjCn9jBCG4TpWB.qQxPaXVGcepsUl7LIEcXpN7dsv3SbEW', 'Employeur', 'Jaoued', 'Le Logeur', 'default_avatar.png', NULL, NULL, NULL, NULL, NULL, '2024-12-13 17:33:29'),
(8, 'camelia.fixaris@edu.ece.fr', '$2y$10$jUEXsq/uARif1SQiK9NEiOcDTRUf7GlRaBPxp8IbII9h9trVwy01u', 'Etudiant', 'Camélia', 'Fixaris', 'default_avatar.png', NULL, NULL, NULL, NULL, NULL, '2024-12-14 14:09:55'),
(9, 'employeur@ece.fr', '$2y$10$mdCveMviGUWyAxKm/.uNZuZaKxTcmzu80C3pe4JE0i.AB.Z702UHO', 'Employeur', 'Sarkozy', 'Employeur', 'default_avatar.png', NULL, NULL, NULL, NULL, NULL, '2024-12-14 20:02:30'),
(10, 'sam.fechier@edu.ece.fr', '$2y$10$lIW0ZJO3UxqTX0u3H0KbGO4jBmP6aoQfRt4OtgUuTEPtHtb1ts8bO', 'Etudiant', 'Sam', 'Fechier', 'default_avatar.png', NULL, NULL, NULL, NULL, NULL, '2024-12-15 11:53:42');
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
