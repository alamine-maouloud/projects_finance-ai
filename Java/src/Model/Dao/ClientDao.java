package Modele.dao;

import Modele.Users.Client;

import java.sql.SQLException;
import java.util.List;

public interface ClientDao {

    /**
     * Crée un nouveau client dans la base de données.
     * @param client L'objet client à insérer
     * @return true si l'insertion a réussi
     */
    boolean creerCompte(Client client) throws SQLException, ClassNotFoundException;

    /**
     * Vérifie les identifiants de connexion.
     * @param email Email du client
     * @param motDePasse Mot de passe du client
     * @return true si les identifiants sont valides
     */
    boolean verifierConnexion(String email, String motDePasse) throws SQLException, ClassNotFoundException;

    /**
     * Récupère un client par son email.
     * @param email Email du client
     * @return L'objet Client trouvé ou null
     */
    Client getClientByEmail(String email) throws SQLException, ClassNotFoundException;

    /**
     * Met à jour les informations d'un client.
     * @param client L'objet client mis à jour
     * @return true si la mise à jour a réussi
     */
    boolean updateClient(Client client) throws SQLException, ClassNotFoundException;

    /**
     * Supprime un client via son ID.
     * @param id L'ID du client
     * @return true si la suppression a réussi
     */
    boolean deleteClient(int id) throws SQLException, ClassNotFoundException;

    /**
     * Récupère tous les clients de la base de données.
     * @return Liste de tous les clients
     */
    List<Client> getAllClients() throws SQLException, ClassNotFoundException;
}
