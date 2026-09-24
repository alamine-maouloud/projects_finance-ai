package Modele.dao;

import Modele.Users.Client;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;

public class ClientDaoImpl implements ClientDao {

    private final String url = "jdbc:mysql://localhost:3306/shopping"; // 🔁 Remplace par le nom de ta base si besoin
    private final String username = "root";
    private final String password = "";

    private Connection getConnection() throws SQLException, ClassNotFoundException {
        Class.forName("com.mysql.cj.jdbc.Driver");
        return DriverManager.getConnection(url, username, password);
    }

    @Override
    public boolean creerCompte(Client client) throws SQLException, ClassNotFoundException {
        String query = "INSERT INTO users (last_name, first_name, email, pass_word, adress, phone, type_user) VALUES (?, ?, ?, ?, ?, ?, 'client')";
        try (Connection conn = getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {

            stmt.setString(1, client.getLastName());
            stmt.setString(2, client.getFirstName());
            stmt.setString(3, client.getEmail());
            stmt.setString(4, client.getPassWord());
            stmt.setString(5, client.getAdress());
            stmt.setString(6, client.getPhone());

            return stmt.executeUpdate() > 0;
        }
    }

    @Override
    public boolean verifierConnexion(String email, String motDePasse) throws SQLException, ClassNotFoundException {
        String query = "SELECT * FROM users WHERE email = ? AND pass_word = ?";
        try (Connection conn = getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {

            stmt.setString(1, email);
            stmt.setString(2, motDePasse);

            ResultSet rs = stmt.executeQuery();
            return rs.next();
        }
    }

    @Override
    public Client getClientByEmail(String email) throws SQLException, ClassNotFoundException {
        String query = "SELECT * FROM users WHERE email = ?";
        try (Connection conn = getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {

            stmt.setString(1, email);
            ResultSet rs = stmt.executeQuery();

            if (rs.next()) {
                return new Client(
                        rs.getInt("id_users"),
                        rs.getString("last_name"),
                        rs.getString("first_name"),
                        rs.getString("email"),
                        rs.getString("pass_word"),
                        rs.getString("adress"),
                        rs.getString("phone"),
                        rs.getString("type_user")
                );
            }
        }
        return null;
    }

    @Override
    public boolean updateClient(Client client) throws SQLException, ClassNotFoundException {
        String query = "UPDATE users SET last_name=?, first_name=?, email=?, pass_word=?, adress=?, phone=?, type_user=? WHERE id_users=?";
        try (Connection conn = getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {

            stmt.setString(1, client.getLastName());
            stmt.setString(2, client.getFirstName());
            stmt.setString(3, client.getEmail());
            stmt.setString(4, client.getPassWord());
            stmt.setString(5, client.getAdress());
            stmt.setString(6, client.getPhone());
            stmt.setString(7, client.getTypeUser());
            stmt.setInt(8, client.getIdUsers());

            return stmt.executeUpdate() > 0;
        }
    }

    @Override
    public boolean deleteClient(int id) throws SQLException, ClassNotFoundException {
        String query = "DELETE FROM users WHERE id_users=?";
        try (Connection conn = getConnection();
             PreparedStatement stmt = conn.prepareStatement(query)) {

            stmt.setInt(1, id);
            return stmt.executeUpdate() > 0;
        }
    }

    @Override
    public List<Client> getAllClients() throws SQLException, ClassNotFoundException {
        List<Client> clients = new ArrayList<>();
        String query = "SELECT * FROM users";

        try (Connection conn = getConnection();
             PreparedStatement stmt = conn.prepareStatement(query);
             ResultSet rs = stmt.executeQuery()) {

            while (rs.next()) {
                clients.add(new Client(
                        rs.getInt("id_users"),
                        rs.getString("last_name"),
                        rs.getString("first_name"),
                        rs.getString("email"),
                        rs.getString("pass_word"),
                        rs.getString("adress"),
                        rs.getString("phone"),
                        rs.getString("type_user")
                ));
            }
        }

        return clients;
    }
}
