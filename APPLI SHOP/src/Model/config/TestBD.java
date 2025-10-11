package Modele.config;
import java.sql.Connection;
public class TestBD {
    public static void main(String[] args) {
        try {
            Connection conn = DatabaseConfig.getConnection();
            if (conn != null) {
                System.out.println("Connexion à MySQL réussie ");
                conn.close();
            } else {
                System.out.println("Connexion échouée");
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}