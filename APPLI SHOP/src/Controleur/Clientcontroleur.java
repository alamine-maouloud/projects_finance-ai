package Controleur;

import Modele.Users.Client;
import Modele.dao.ClientDao;
import Modele.dao.ClientDaoImpl;

import javax.swing.*;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

public class Clientcontroleur {

    private static final ClientDao clientDao = new ClientDaoImpl();

    // Inscription d'un nouveau client
    public static boolean inscrireClient(Client client) {
        try {
            return clientDao.creerCompte(client);
        } catch (SQLException | ClassNotFoundException e) {
            e.printStackTrace(); // Affiche l'exception dans la console
            JOptionPane.showMessageDialog(null, "Erreur SQL : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return false;
        }
    }

    // Connexion d'un client (vérifie email + mot de passe)
    public static boolean verifierConnexion(String email, String motDePasse) {
        try {
            return clientDao.verifierConnexion(email, motDePasse);
        } catch (SQLException | ClassNotFoundException e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "Erreur SQL : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return false;
        }
    }

    // Récupération des infos d’un client par son email
    public static Client getClientParEmail(String email) {
        try {
            return clientDao.getClientByEmail(email);
        } catch (SQLException | ClassNotFoundException e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "Erreur SQL : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return null;
        }
    }

    // Modifier les infos d’un client
    public static boolean mettreAJourClient(Client client) {
        try {
            return clientDao.updateClient(client);
        } catch (SQLException | ClassNotFoundException e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "Erreur SQL : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return false;
        }
    }

    // Supprimer un client par ID
    public static boolean supprimerClient(int id) {
        try {
            return clientDao.deleteClient(id);
        } catch (SQLException | ClassNotFoundException e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "Erreur SQL : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return false;
        }
    }

    // Historique des commandes (simulé)
    public static List<String> voirCommandesClient(int clientId) {
        try {
            // À implémenter plus tard
            return new ArrayList<>();
        } catch (Exception e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "Erreur : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return null;
        }
    }

    // Vérifie si un email est déjà utilisé
    public static boolean emailExiste(String email) {
        try {
            return clientDao.getClientByEmail(email) != null;
        } catch (SQLException | ClassNotFoundException e) {
            e.printStackTrace();
            JOptionPane.showMessageDialog(null, "Erreur SQL : " + e.getMessage(), "Erreur", JOptionPane.ERROR_MESSAGE);
            return false;
        }
    }
}
